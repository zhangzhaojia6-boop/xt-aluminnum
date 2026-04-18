# 试点上线前 QA / Readiness Checklist

> 目标：在现场放量前，用同一份清单确认“能填、能退、能汇总、能降级、能回滚”。

## Phase 1 上线口径（2026-04-17）

- [ ] 主操手工直录可独立跑通，不依赖 MES 返回数据
- [ ] 班次提交后 5 分钟内可在驾驶舱看到自动汇总结果
- [ ] 异常数据可自动退回并给出中文修改指引
- [ ] 催报消息可在班次结束后 30 分钟触发
- [ ] Phase 1 不以 MES 联调为上线前提，MES 仅保留后端接口缝

## 1. 放量门槛（必须全部满足）

### Gate A：基础可用性
```bash
cd backend
python -m pytest tests/test_health.py tests/test_config_readiness_service.py -q
python scripts/check_pilot_config.py --date 2026-04-06 --json
```
- 通过标准：
  - `/readyz` 语义对应的测试通过。
  - `check_pilot_config.py` 输出中 `hard_gate_passed=true`。
- 阻断条件：存在 `hard_issues`，不得上线。
- 可接受项：`warning_issues` 可带着上线，但必须记录责任人与修复时间。

### Gate B：移动填报主链路
```bash
cd backend
python -m pytest \
  tests/test_validator_agent.py \
  tests/test_mobile_status_consistency.py \
  tests/test_mobile_scope_isolation.py \
  tests/test_reminder_agent.py -q
```
- 通过标准：
  - 企业微信或浏览器进入后统一落到 `/mobile` 主入口，不依赖并列工人端入口。
  - 自动确认链路通过，最终状态保持为：
    - `MobileShiftReport.report_status=approved`
    - `ShiftProductionData.data_status=confirmed`
  - 自动退回链路通过，`returned_reason` 为可直接执行的中文修改说明。
  - 权限范围测试通过，不能串看/串改其他班组数据。
  - 催报兼容旧状态 `auto_confirmed`，不会误催已就绪班次。

### Gate C：日报范围与发布链路
```bash
cd backend
python -m pytest \
  tests/test_aggregator_agent.py \
  tests/test_report_generation.py \
  tests/test_report_publish_flow.py \
  tests/test_reporter_agent.py \
  tests/test_pilot_metrics_service.py -q
```
- 通过标准：
  - 汇总与老板摘要统一使用 canonical `auto_confirmed` 口径。
  - 兼容入参仍可接受 `confirmed_only`，但自动汇总后 `generated_scope=auto_confirmed`。
  - 自动发布/自动推送开关可分别关闭，不影响数据留痕。

## 2. 现场 smoke checklist（建议逐项打勾）
- [ ] 从企业微信或浏览器进入后，现场人员统一从 `/mobile` 开始，不需要跳转到其他工人端入口。
- [ ] 企业微信账号能登录；失败时提示是“未绑定 / 停用 / 冲突 / 账号无效”中的一种。
- [ ] 提交一条正常数据，系统自动进入 `approved`。
- [ ] 提交一条“产出 > 投入”的测试数据，系统自动退回，且页面能看到 `returned_reason`。
- [ ] 同班次修正后重新提交，确认可从 `returned` 回到 `approved`。
- [ ] 驾驶舱/日报生成后，摘要口径只统计 canonical `auto_confirmed` 数据。
- [ ] `AUTO_PUBLISH_ENABLED=false` 时，仅停自动发布，不影响填报与自动校验。
- [ ] `AUTO_PUSH_ENABLED=false` 时，仅停消息推送，不影响填报、校验、汇总。

## 3. 每日复盘命令
```bash
cd backend
python scripts/check_pilot_metrics.py --date 2026-04-06 --json
python scripts/check_pilot_anomalies.py --date 2026-04-06 --json
python scripts/check_pilot_config.py --date 2026-04-06 --json
```
重点看：
- 上报率 `reporting_rate`
- 退回率 `return_rate`
- 差异率 `difference_rate`
- 异常摘要 `summary.digest`
- 配置硬阻断 `hard_issues`

## 4. 发现问题时的降级/回滚
```env
AUTO_PUBLISH_ENABLED=false
AUTO_PUSH_ENABLED=false
```
- 用途：保留“填报 + 自动校验 + 汇总留痕”，暂停对外发布和消息触达。
- 若 `hard_gate_passed=false`：先修配置，不做现场放量。
- 若连续出现退回原因不可读、跨班组可见、日报口径不一致：立即停止放量，回到只读/人工值守。

## 5. 结论记录模板
- 检查日期：2026-04-06
- 检查人：
- Gate A：通过 / 不通过
- Gate B：通过 / 不通过
- Gate C：通过 / 不通过
- warning_issues：
- 是否允许试点放量：是 / 否
- 降级预案责任人：
