# MES API 未就绪期间的两周施工计划

> 适用前提：`MES API` 预计还需要约 2 周才会搭好。
> 当前日期基准：`2026-04-11`
> 目标：在接口未就绪期间，把后续真实联调前 80% 的准备工作先做完，避免空等。

## 1. 这两周不要干什么

明确不建议把时间花在这些地方：

- 空等 MES 接口
- 一边没有契约，一边猜字段去写临时代码
- 过早做财务级真实利润
- 过早重做现场扫码流程

## 2. 这两周真正要达成什么

等 `MES API` 准备好时，我们希望已经提前完成：

1. API 契约说清楚
2. mock 数据准备好
3. 字段映射表准备好
4. 驾驶舱口径先校对好
5. 经营估算系数可配置
6. 联调命令、验收清单、排错路径都写好

一句话：

> 接口一到，直接联调，不再回头补文档、补字段、补口径。

## 3. 两周计划总览

### 第 1 周：把“联调前准备”做完

目标：

- 锁死契约
- 准备 mock
- 校对字段
- 把驾驶舱口径先跑通

### 第 2 周：把“联调执行面”做完

目标：

- 做 mock 联调演练
- 补 smoke 脚本
- 补联调 checklist
- 准备真实联调切换动作

## 4. 第 1 周详细计划

### Day 1

目标：

- 和 MES 方确认对接方式
- 明确测试环境和认证方式

要产出：

- 对接联系人
- 接口基地址
- 认证方式
- 预计接口就绪日期

### Day 2

目标：

- 把接口契约问清楚

要产出：

- `tracking card info` 字段清单
- `coil snapshots` 字段清单
- 状态枚举
- 时间字段说明
- 游标/分页/重试规则

参考文档：

- [mes-api-sync-contract-phase1.md](/mnt/d/zzj%20Claude%20code/aluminum-bypass/docs/mes-api-sync-contract-phase1.md)
- [mes-api-integration-checklist.md](/mnt/d/zzj%20Claude%20code/aluminum-bypass/docs/mes-api-integration-checklist.md)

### Day 3

目标：

- 准备 mock 响应样例

要产出：

- 正常样例
- 空数据样例
- 错误样例

建议放到：

- `docs/` 下新增 `mock_mes_payloads/` 或放在你自己的联调资料目录中

### Day 4

目标：

- 先校对卷级字段映射
- 先校对“手机扫码预填 + 锁定字段”规则

要确认：

- `coil_id`
- `tracking_card_no`
- `qr_code`
- `batch_no`
- `contract_no`
- `workshop_code`
- `process_code`
- `machine_code`
- `shift_code`
- `status`
- `event_time`
- `updated_at`
- `product_type`
- `finished_spec`
- `production_schedule`

另外要明确分组：

#### 扫码后自动带出并锁定

- 批号
- 产品类型
- 合金
- 状态
- 成品规格
- 生产安排

#### 扫码后仍由现场补充

- 上机重量
- 道次
- 工艺补充项
- 后台自定义字段

### Day 5

目标：

- 校对驾驶舱口径

重点看：

- 什么叫活跃合同
- 什么叫停滞合同
- 什么叫活跃卷数
- 在制料怎么算
- 估算收入/成本/毛差用什么系数

## 5. 第 2 周详细计划

### Day 6

目标：

- 用 mock 数据跑一次本地同步链路

要验证：

- `RestApiMesAdapter`
- `mes_sync_service`
- `MesCoilSnapshot` upsert
- `check_mes_sync_lag.py`

### Day 7

目标：

- 用 mock 数据跑一次管理驾驶舱
- 顺手跑一次“手机扫码自动预填”演练

要验证：

- `FactoryDirector`
- `Statistics`
- `LiveDashboard`

重点看：

- 有没有活跃合同
- 有没有停滞合同
- 有没有卷级变化
- `data_source` 是否正确
- 扫码后头字段是否自动带出
- 锁定字段是否不能被误改

### Day 8

目标：

- 准备联调排错清单

要覆盖：

- 认证失败怎么查
- 字段缺失怎么查
- lag 太大怎么查
- 数据空白怎么查
- 状态不对怎么查

### Day 9

目标：

- 准备真实联调 smoke 流程

最小 smoke：

1. 拉一次 tracking card info
2. 拉一次 coil snapshots
3. 同步写入本地投影
4. 驾驶舱看到变化
5. `lag_seconds <= 300`

### Day 10

目标：

- 做联调前总检查

检查项：

- 环境变量是否齐
- 契约是否齐
- mock 是否齐
- smoke 命令是否齐
- 口径说明是否齐

## 6. 两周期间你让我继续做什么最划算

如果你这两周还想继续推进，我建议优先顺序是：

1. 帮你做 `mock MES 响应样例包`
2. 帮你做 `驾驶舱口径校对表`
3. 帮你做 `真实联调 smoke 手册`

## 7. 两周后接口到了，第一天该做什么

接口一到，不要先随便试。

正确顺序是：

1. 先配置真实 `MES_API_*`
2. 先打 `tracking card info`
3. 再打 `coil snapshots`
4. 再跑 `mes_sync_service`
5. 再看驾驶舱
6. 最后再谈“为什么这个数不对”

## 8. 最小交付标准

如果这两周准备做得好，那么接口一到后的 1 天内，应该至少做到：

1. 真实接口可连通
2. 数据可拉取
3. 投影可写入
4. 驾驶舱可见
5. lag 可观测
