# 鑫泰 MES 数据接口缺口对照表

**日期：** 2026-05-21
**用途：** 跟 MES 厂商沟通时的清单，标清楚我们要什么、现在拿到什么、差距是什么

## 当前真相（生产实测）

- 快照总数：494 条
- `coil_id="fallback:..."` 占比：**100%**（494/494）
- `machine_code` 有值占比：**0%**
- `current_workshop` / `current_process` 有值占比：87.9%

## 字段对照表

| 字段 | 业务含义 | 我们要什么 | MES 现在给什么 | 缺口 | 影响 |
|---|---|---|---|---|---|
| `coil_id` | 卷的真实业务 ID | MES 内部唯一 ID 字符串 | **null** → 我们用 `fallback:跟踪卡:物料号` 拼 | 100% 缺失 | 跨表关联只能用复合键，统计精度受影响 |
| `tracking_card_no` | 跟踪卡号 | 字符串 | ✅ 87.9% 有值 | 12.1% 缺失 | 工人扫码兜底失败 |
| `qr_code` | 二维码内容 | 字符串 | ✅ 87.9% 有值 | 12.1% 缺失 | 扫码命中率受影响 |
| `material_code` | 物料编号 | 字符串 | ✅ 大部分有 | 偶发空 | 统计聚合可用 |
| `batch_no` | 批次号 | 字符串 | 部分给 | 不完整 | 影响批次追溯 |
| `contract_no` | 合同号 | 字符串 | 部分给 | 不完整 | 影响合同维度统计 |
| `workshop_code` | 当前所在车间编码 | 内部代号（如 `2050`） | ✅ 给中文名（如 `2050车间`） | 名称对得上别名表，能用 | 别名维护成本 |
| `process_code` | 当前工序代号 | 内部代号 | ✅ 给中文名（如 `冷轧`） | 同上 | 同上 |
| **`machine_code`** | **当前机列代号** | **如 `LZ2050-1`** | **null** | **100% 缺失** | **机列归属只能靠车间+工艺推断；多候选时无法绑定** |
| `shift_code` | 班次代号 | `morning`/`afternoon`/`night` | 部分 | 不完整 | 影响班次维度统计 |
| `event_time` | 事件发生时间 | ISO datetime | ✅ 大部分有 | 偶发缺失 | 实时性受影响 |
| `next_workshop` / `next_process` | 下一道工序去向 | 字符串 | ✅ 给中文名 | OK | 用于流转预测 |

## 优先级（厂商沟通用）

### P0 必须给

1. **`machine_code`** — 这是最核心缺口。MES 系统应当知道这一卷正在哪台机上加工，但当前接口完全不返回。如果给了，我们的"机列归属"问题立刻解决，工人扫码后系统直接对应到机器，不再需要"车间+工艺推断"逻辑。
2. **`coil_id`** — MES 内部唯一 ID。现在我们用 `fallback:` 拼复合键凑唯一性，这是临时方案。给了真 ID，我们可以删除 fallback 逻辑，跨表关联更稳。

### P1 完整度提升

3. `tracking_card_no` / `qr_code` 的剩余 12.1% — 为什么这部分卷子没有？是 MES 端漏了还是接口过滤了？
4. `batch_no` / `contract_no` 完整化 — 影响批次/合同维度统计

### P2 增强

5. `shift_code` 标准化为枚举值（`morning`/`afternoon`/`night`），不要给中文
6. `event_time` 全字段填齐

## 我们这边的承诺

- 一旦 P0 两个字段给齐，我们删除 fallback 兜底逻辑，简化 6 处代码
- 字段名按上面对照表保持一致（不另起 alias）
- 接口契约变更前 7 天告知，给我们留迁移时间

## 回退方案

如果 P0 短期推不动：

- **`machine_code` 缺失** → 保留现有"车间+工艺唯一"推断（commit `b6b925b` 已落地），覆盖单机工艺；多候选保持工人手选
- **`coil_id` 缺失** → 保留 fallback 复合键拼接（adapter line 155）

这两条都已实测稳定，**短期不阻塞生产**，但长期数据质量有损。

## 关联文件

- `backend/app/adapters/xintai_mes_adapter.py:148-168` — 字段映射点
- `backend/app/services/mes_sync_service.py:128-138` — fallback 逻辑
- `backend/app/services/scan_lookup_service.py` — 推断兜底逻辑
- `docs/audits/2026-05-12-live-fill-mes-binding-audit.md` — 5-12 现网实测
- `backend/scripts/check_mes_data_health.py` — 数据健康度监控（每周一跑）
