# 恢复使用与日报闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让现场重新能用系统，并让日报缺口持续缩小，达到适用字段自动取得率 ≥ 80%、关键字段真实来源覆盖 100%。

**Architecture:** 不新增服务和页面。复用已有的 `DailyFactBundle`、缺口事件（`agent_events.daily_fact_gap`）、通知路由（`daily_fact_notification_routing`）和字段合同（`app/domain/daily_report_field_contract.py`）。设计见 `docs/superpowers/specs/2026-11-08-system-overhaul-design.md`。

**Tech Stack:** Python 3、FastAPI、SQLAlchemy、PostgreSQL、pytest。

**测试命令：** 下文的 `PY` 指 `/d/codex-task-temp/xt-system-audit-20261030/venv/Scripts/python.exe`，在 `backend/` 目录运行。全量测试外面包 `timeout 1500`，运行时不切分支。

**生产只读查询：** 下文 `prod-sql` 指：

```bash
ssh -F "$HOME/.ssh/config" xt-prod 'U=$(grep -h "^DATABASE_URL=" /srv/aluminum-bypass/backend/.env | cut -d= -f2-); U=${U/postgresql+psycopg2/postgresql}; U=${U/postgresql+asyncpg/postgresql}; PGOPTIONS="-c default_transaction_read_only=on" psql "$U" -X -tA -f -' < query.sql
```

**硬边界：** 127 分母不变；MES 只读；写生产库前备份并留 trace；`gh pr merge` 必须有负责人明确批准；第一次真实发钉钉前内容先给负责人过目；不修复 Hermes 定时任务的模型。

---

## 编写计划时已确认的事实

- 追缺通知已经存在：`sync_daily_fact_gap_events` 按责任人路由并去重，只是真实外发被演练模式拦住。所以本计划不新写通知逻辑。
- 字段责任已在 `DAILY_REPORT_GAP_ACTIONS` 中，只是没有写进字段合同文档。
- 11/07 的 99 个缺口：人工要补 24 项，系统自动复查 16 项，等依赖（主要是吨耗和成本等能耗数据）59 项。

---

### Task 1: 迟到数据重写日报记录

**Files:**
- Modify: `backend/app/tasks/daily_fact_closure.py`
- Test: `backend/tests/test_daily_fact_closure_task.py`

代码和 5 个新测试已写在分支 `fix/late-data-refreshes-report-row`。生产只读预演：11/05 从 97 变 89，10/31 从 106 变 89。

- [ ] **Step 1: 全量测试通过后提交**

```bash
git add backend/app/tasks/daily_fact_closure.py backend/tests/test_daily_fact_closure_task.py
git commit -m "fix: 晚到的事实补进被拦下的日报记录，不触发投递"
```

- [ ] **Step 2: 推送并开 PR，请负责人批准合并**

```bash
git push -u origin fix/late-data-refreshes-report-row
gh pr create --base main --head fix/late-data-refreshes-report-row --title "fix: 晚到的事实补进被拦下的日报记录，不触发投递"
```

- [ ] **Step 3: 批准后合并，并按现有流程部署**

Run: 在生产机 `/srv/aluminum-bypass` 运行 `deploy_ff.sh`
Expected: readyz 返回 200，HEAD 等于合并提交。

- [ ] **Step 4: 上线后第一个 10:15 核对**

查询：

```sql
select r.report_date,
       jsonb_array_length(coalesce(r.report_data->'template_daily_report'->'missing_fields','[]'::jsonb)),
       r.report_data->>'gap_refresh_open_gaps',
       (select count(*) from agent_events e where e.business_date=r.report_date and e.event_type='daily_fact_gap' and e.status='open')
from daily_reports r
where r.report_type='production' and r.report_date>=current_date-7
order by 1;
```

Expected: 第 2 列和第 4 列一致。`agent_outbox_messages` 没有因此新增消息。

---

### Task 2: 恢复现场扫码并每天观察

**Files:** 无代码改动。

- [ ] **Step 1: 请负责人完成现场动作**

张贴 `D:\鑫泰智能车间\二维码-公网IP-20261102.pdf`（先试扫一张，再撤旧码）；把钉钉后台应用首页改成 `https://8.140.218.13`；询问现场 8 月下旬使用量下滑的原因，答案记入 `docs/deploy/current-state.md`。

- [ ] **Step 2: 每天 10:30 查一次使用情况**

```sql
select to_char(a.created_at,'MM-DD'), u.role, count(*), count(distinct a.user_id)
from audit_logs a left join users u on u.id=a.user_id
where a.action ilike '%login%' and a.created_at>now()-interval '7 days'
group by 1,2 order by 1,3 desc;
select to_char(created_at,'MM-DD'), count(*) from work_order_entries
where created_at>now()-interval '7 days' group by 1 order by 1;
```

Expected（子项目 0 验收）：连续 3 个工作日有真实扫码登录，且覆盖 `machine_operator`、`energy_stat`、`planning_owner`、`quality_owner`。

---

### Task 3: 接入能耗表

**Files:** 无代码改动，使用已合并的 `backend/scripts/register_energy_file_sender.py`。

- [ ] **Step 1: 请负责人安排能源统计员每天发两张表**

《X月份各车间电耗统计表》《X月份各车间天然气用量统计表》，私聊发给负责人，08:00 以后发。

- [ ] **Step 2: 每天查是否收到**

```sql
select id, to_char(created_at,'MM-DD HH24:MI'), payload->>'file_name'
from multimodal_evidence
where created_at>timestamp '2026-11-08' and payload::text ~ '电耗统计表|天然气用量统计表'
order by id;
```

Expected: 收到前为空，不做登记。

- [ ] **Step 3: 首份到达后先备份，再只读列出**

```bash
ssh -F "$HOME/.ssh/config" xt-prod 'cd /srv/aluminum-bypass/backend && .venv/bin/python scripts/register_energy_file_sender.py --since 2026-11-08'
```

Expected: 列出刚到的文件和发送人。发送人不能是负责人本人转发（证据 110、111 那种）。

- [ ] **Step 4: 登记并补入库**

```bash
ssh -F "$HOME/.ssh/config" xt-prod 'cd /srv/aluminum-bypass/backend && .venv/bin/python scripts/register_energy_file_sender.py --since 2026-11-08 --apply --evidence-id <证据id> --owner <姓名> --owner-key <拼音>'
```

- [ ] **Step 5: 验收**

Run: 下一个 15 分钟复查后查 Task 1 Step 4 的语句。
Expected: 用电和用气共 18 个用量字段不再缺失，当天缺口明显下降。把高压合计和原表逐项核对一致。

---

### Task 4: 把字段责任写进字段合同

**Files:**
- Modify: `backend/scripts/render_daily_report_field_contract.py`
- Modify: `backend/tests/test_daily_report_field_contract_scripts.py`
- Regenerate: `docs/hermes/daily-report-field-contract.md`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_daily_report_field_contract_scripts.py`：

```python
def test_contract_document_lists_owner_and_fill_path_for_every_field() -> None:
    payload = renderer.build_contract_payload()

    assert len(payload["fields"]) == 127
    for field in payload["fields"]:
        assert field["owner_role"]
        assert field["fill_strategy"]
        assert field["entry_route"]

    markdown = renderer.render_contract_markdown(payload)
    assert "| 责任角色 | 补齐方式 | 补录入口 |" in markdown
```

- [ ] **Step 2: 运行确认失败**

Run: `$PY -m pytest -q tests/test_daily_report_field_contract_scripts.py::test_contract_document_lists_owner_and_fill_path_for_every_field`
Expected: FAIL，`KeyError: 'owner_role'`。

- [ ] **Step 3: 实现**

在 `build_contract_payload` 的循环里取责任信息：

```python
        contract = contract_module.daily_report_field_contract_for(field_name)
        action = contract_module.daily_report_gap_action_for(field_name)
        fields.append(
            {
                "field_name": contract.field_name,
                "group": contract.group,
                "unit": contract.unit,
                "business_time_scope": contract.business_time_scope,
                "business_time_start": contract_module.BUSINESS_TIME_STARTS[contract.business_time_scope],
                "tolerance": contract.tolerance,
                "reference_role": contract.reference_role,
                "owner_role": action.owner_role,
                "fill_strategy": action.fill_strategy,
                "entry_route": action.entry_route,
            }
        )
```

在 `render_contract_markdown` 里替换字段表：

```python
            "| # | 字段 | 分组 | 单位 | 业务时间 | 允许误差 | 答案钥匙角色 | 责任角色 | 补齐方式 | 补录入口 |",
            "|---:|---|---|---|---|---:|---|---|---|---|",
        ]
    )
    for index, field in enumerate(data["fields"], start=1):
        lines.append(
            "| {index} | `{field_name}` | `{group}` | {unit} | `{scope}` ({start}) | {tolerance} | `{role}` | `{owner}` | `{strategy}` | `{route}` |".format(
                index=index,
                field_name=_cell(field["field_name"]),
                group=_cell(field["group"]),
                unit=_cell(field["unit"]),
                scope=_cell(field["business_time_scope"]),
                start=_cell(field["business_time_start"]),
                tolerance=_display_number(field["tolerance"]),
                role=_cell(field["reference_role"]),
                owner=_cell(field["owner_role"]),
                strategy=_cell(field["fill_strategy"]),
                route=_cell(field["entry_route"]),
            )
        )
```

- [ ] **Step 4: 测试并重新生成文档**

Run: `$PY -m pytest -q tests/test_daily_report_field_contract_scripts.py`
Expected: 全部 PASS。
Run: `$PY scripts/render_daily_report_field_contract.py`
Expected: 只有 `docs/hermes/daily-report-field-contract.md` 变化。

- [ ] **Step 5: 核对责任人空缺并提交**

Run: 在新文档里数 `owner_role` 为 `factory_dispatch` 的字段，逐项判断是真依赖（吨耗、成本）还是没人负责。没人负责的列给负责人指定，不自行填写。

```bash
git add backend/scripts/render_daily_report_field_contract.py backend/tests/test_daily_report_field_contract_scripts.py docs/hermes/daily-report-field-contract.md
git commit -m "docs: 字段合同写明每个字段的责任角色和补录入口"
```

---

### Task 5: 追缺消息样稿与第一位真实责任人

**Files:** 无代码改动。改生产配置前备份。

- [ ] **Step 1: 导出最近一份演练样稿**

```sql
select c.id, c.name, c.dry_run, c.metadata_payload->>'daily_fact_owner_roles', c.metadata_payload->>'daily_fact_notification'
from communication_channels c where c.channel_type='dingtalk_work_notice' order by c.id;
select m.id, c.name, m.content from agent_outbox_messages m
join communication_channels c on c.id=m.channel_id
where m.title like '%事实闭环%' and m.status='dry_run'
order by m.id desc limit 3;
```

Expected: 样稿里的补录链接以 `https://8.140.218.13` 开头。若仍是旧域名，先修 `PUBLIC_APP_BASE_URL` 的取值，不继续。

- [ ] **Step 2: 把样稿交给负责人过目**

只展示内容，不发送。负责人明确同意后才进入下一步，并由负责人指定第一位责任人。

- [ ] **Step 3: 只为这一位开启真实发送**

备份 `.env` 和该渠道行，把这一个渠道的 `dry_run` 改为 false。`DINGTALK_NOTIFY_DRY_RUN` 是全局开关，是否调整要和负责人一起决定，并写入 `backups/ops-<日期>-first-real-send.md`。

- [ ] **Step 4: 验收**

Expected: 对方收到一条合并消息，链接能打开，同样的缺口第二天不重复提醒。出问题就恢复备份。

---

### Task 6: 合同消息归属日期（有证据才做）

**前置条件：** 11/08 08:08 的合同消息被算到 11/08，而 11/07 没有消息。只有当 11/08 晚些时候又收到一条当天消息，才证明早上那条属于 11/07。否则跳过本任务，改问发送人。

**Files:**
- Modify: `backend/app/services/hermes_dingtalk_sampling_service.py`
- Test: `backend/tests/test_hermes_dingtalk_sampling_service.py`

- [ ] **Step 1: 写失败测试**

追加：

```python
def test_morning_message_fills_previous_day_when_that_day_has_no_message() -> None:
    db = _db()
    db.add(_registered_contract_rule())
    evidence = _machine_only_message_evidence(event_time='2026-11-08 08:08:00')
    db.add(evidence)
    db.flush()

    adopt_registered_message_evidence(db, evidence_id=evidence.id)

    assert evidence.payload['business_date'] == '2026-11-07'


def test_morning_message_stays_on_its_day_when_previous_day_already_reported() -> None:
    db = _db()
    db.add(_registered_contract_rule())
    previous = _machine_only_message_evidence(event_time='2026-11-07 17:20:00', trace_id='msg-plan-a')
    morning = _machine_only_message_evidence(event_time='2026-11-08 08:08:00', trace_id='msg-plan-b')
    db.add_all([previous, morning])
    db.flush()

    adopt_registered_message_evidence(db, evidence_id=previous.id)
    adopt_registered_message_evidence(db, evidence_id=morning.id)

    assert previous.payload['business_date'] == '2026-11-07'
    assert morning.payload['business_date'] == '2026-11-08'
```

- [ ] **Step 2: 运行确认失败**

Run: `$PY -m pytest -q tests/test_hermes_dingtalk_sampling_service.py -k morning_message`
Expected: 第一个 FAIL，实际为 `2026-11-08`。

- [ ] **Step 3: 实现**

在 `adopt_registered_message_evidence` 里把 `business_date = resolve_production_business_date(message_time)` 换成 `business_date = _registered_message_business_date(db, rule_key=rule.rule_key, message_time=message_time)`，并新增（文件顶部补 `from datetime import time, timedelta`，已有的不重复）：

```python
MORNING_LATE_REPORT_UNTIL = time(12, 0)


def _registered_message_business_date(db: Session, *, rule_key: str, message_time: datetime) -> date:
    business_date = resolve_production_business_date(message_time)
    if message_time.time() >= MORNING_LATE_REPORT_UNTIL:
        return business_date
    previous = (business_date - timedelta(days=1)).isoformat()
    already_reported = any(
        (other.payload or {}).get('sampling_rule_key') == rule_key
        and (other.payload or {}).get('business_date') == previous
        for other in db.query(MultimodalEvidence).filter(MultimodalEvidence.confirmation_status == 'specialist_sampled').all()
    )
    return business_date if already_reported else business_date - timedelta(days=1)
```

- [ ] **Step 4: 运行并提交**

Run: `$PY -m pytest -q tests/test_hermes_dingtalk_sampling_service.py`
Expected: 全部 PASS。

```bash
git add backend/app/services/hermes_dingtalk_sampling_service.py backend/tests/test_hermes_dingtalk_sampling_service.py
git commit -m "fix: 上午补发的合同消息归到还没上报的前一天"
```

---

### Task 7: 收集车间产量口径

**Files:** 确认后写 `docs/adr/` 新 ADR 并更新 `CONTEXT.md`；每个车间的接入单独写计划。

- [ ] **Step 1: 把问题交给负责人转问各车间统计员**

1. 2050、1650：同一卷轧两次算几次？2050 转 1650 的卷算哪台？
2. 拉矫：算不算包装工序？
3. 精整、园区剪切、冷轧 1850、彩涂、热轧、铸轧：MES 对不上或没有记录，产量以谁的数据为准？每天怎么报？

- [ ] **Step 2: 只接确认过口径的车间**

口径未定的字段保持缺失，不估算，不调整分母。

---

### Task 8: 第一阶段验收

- [ ] **Step 1: 连续 7 个业务日统计自动取得率**

```sql
select business_date,
       (select count(*) from jsonb_each(facts) e(k,v) where coalesce(v->>'value','')<>'') as with_value
from daily_fact_bundle_snapshots
where business_date>=current_date-7 order by 1;
```

Expected: 按 127 项合同计算的自动取得率 ≥ 80%，关键字段（`CORE_FIELD_LABELS` 中 5 项）全部有真实来源。达标后再开始子项目 2。
