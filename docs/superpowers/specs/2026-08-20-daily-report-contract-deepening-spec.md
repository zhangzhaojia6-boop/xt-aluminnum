# 日报 127 字段合同深化 SPEC

日期：2026-08-20

状态：批准执行

适用项目：`鑫泰铝业 数据中枢`

## 1. 生产事实

当前系统结构和运行链路正常：

- 数据中枢和 Hermes 生产服务为 `active`。
- MES SQL Server 只读同步为 `fresh/success`。
- 钉钉 Stream 为 `connected`。
- 127 字段规范分母门禁存在且不可缩减。

真实生产库同时显示：

- 历史开放 `daily_fact_gap` 事件 `2725` 个。
- 最近 7 日新增缺项事件 `667` 个。
- 其中 `111` 个需要人工行动，`556` 个等待依赖或自动复查。
- 最近 7 日事实闭环 Outbox 已成功外发 `22` 条。

所以当前问题不是“没有主动闭环”，而是字段静态规则分散：

```text
字段、单位、业务时间、容差
  -> daily_report_field_contract.py

来源证据合同
  -> metric_contracts.py

责任角色、补录路径、填报字段、下一步
  -> daily_report_gap_analysis.py

真实表单控件
  -> workshop_templates.py + mobile.py
```

同一个日报字段需要跨多个模块才能回答“是什么、从哪来、谁负责、何时截止、怎么补”。这使后续 Hermes 主动追缺、行动批次聚合和 `/entry/fill` 容易产生规则漂移。

## 2. 本轮目标

建立一个深的 `日报字段合同` 模块：调用者只需要一个字段名，就能获得该字段完整、稳定、可审计的静态合同。

本轮完成后：

1. 127 个规范字段保持不变。
2. 每个字段具有完整静态元数据。
3. 缺项分类只读取合同，不再维护第二套 `GROUP_ACTIONS/FIELD_ACTIONS`。
4. `DailyFactBundle`、缺项事件和精准补录路由引用同一合同版本。
5. 现有表单引擎继续使用，只通过 Entry adapter 校验合同里的补录字段。

## 3. 领域语言

### 3.1 规范日报字段

属于固定 127 分母的字段。字段不能为了门禁通过而删除、重命名或改成全局不适用。

### 3.2 日报字段合同

一个规范日报字段的静态业务定义，包含：

- 字段标识。
- 分组和单位。
- 业务时间范围。
- 容差。
- 来源计划。
- 责任角色。
- 截止时间。
- 缺项处理策略。
- 补录入口及现有表单字段映射。
- 校验规则。
- 合同版本。

### 3.3 字段事实

某个业务日、某个字段的实际值、来源、状态和 trace。字段事实不是字段合同；合同不能提供或猜测某日数值。

### 3.4 明确不适用声明

只对某个具体业务日期生效的、可审计的 `declared_na_fields`。合同只能说明声明规则，不能把字段全局标记为 N/A。

### 3.5 Entry adapter

把规范日报字段映射到现有 `/entry/fill` 表单字段的适配层。它不创建第二套通用表单，也不拥有字段业务定义。

## 4. 深模块接口

外部 seam 保持很小：

```python
daily_report_field_contract_for(field_name: str) -> DailyReportFieldContract
daily_report_gap_action_for(field_name: str) -> DailyReportGapAction
validate_daily_report_contract() -> DailyReportContractValidation
```

`DailyReportFieldContract` 至少包含：

```python
field_name: str
group: str
unit: str
business_time_scope: str
tolerance: float
source_lanes: tuple[str, ...]
owner_role: str
deadline: str
fill_strategy: str
entry_route: str
entry_fields: tuple[str, ...]
validation_kind: str
minimum: float | None
applicability_policy: str
contract_version: str
```

`DailyReportGapAction` 是合同面向缺项闭环的只读投影，包含：

```python
field: str
group: str
source_lane: str
entry_route: str
fill_strategy: str
owner_role: str
deadline: str
entry_fields: tuple[str, ...]
next_step: str
contract_version: str
```

调用者不得再自行推断责任角色、截止时间、容差或补录字段。

## 5. 内部实现

### 5.1 默认值与字段覆盖

避免手写 127 份完全重复的字典：

- 分组默认值负责相同来源计划、责任角色、截止时间和基础策略。
- 字段覆盖只记录真正不同的字段。
- `_build_contract(field_name)` 合并默认值与字段覆盖，生成不可变合同。

生成结果仍必须逐字段校验，不能因为使用默认值而降低完整性要求。

### 5.2 Metric adapter

`metric_contracts.py` 继续拥有来源证据条件、同业务窗口要求和数值种类等证据实现。

它必须从字段合同读取：

- 单位。
- 容差。
- 字段合同版本。

不在本轮把来源证据实现塞进字段合同，以免形成一个无边界巨型模块。

### 5.3 Gap adapter

`daily_report_gap_analysis.py` 保留：

- URL 构建。
- 批次签名。
- 人类可读摘要。

删除：

- `GROUP_ACTIONS`。
- `FIELD_ACTIONS`。
- `_is_computed_field` 中重复的责任和填报策略推断。

`classify_daily_report_field_gap()` 暂时保留为兼容接口，但实现只委托 `daily_report_gap_action_for()`，防止一次大范围改动。

### 5.4 Entry adapter

本轮不重写 `/mobile/entry-fields`。

新增合同校验：

- 合同声明的每个 `entry_field` 必须存在于当前既有表单模板定义。
- `/entry/fill` 行动必须至少有一个可填写字段。
- 依赖型或自动复查型字段必须进入 `/manage/alerts`，不能伪造人工输入控件。

后续迁移 `/mobile/entry-fields` 时复用该 adapter。

### 5.5 管理端现有异常队列

本轮不新建页面，只增强现有 `/manage/alerts`：

- 事实缺项 surface 返回 `deadline` 和 `contract_version`。
- 前端事件标准化保留这两个字段。
- 人工补录事项显示截止时间。
- 自动复查或依赖型事项不伪造人工截止提示。

## 6. 业务时间与截止

保持现有业务时间事实：

- 普通生产字段使用现有生产业务日窗口。
- 铸锭相关字段使用现有铸锭业务日窗口。
- 责任人日报截止继续使用现有 `OWNER_DAILY_LATE_CUTOFF`。
- 正式日报判断时间继续为 `10:00`。

合同存储业务规则标识和截止时间，不在多个调用者重复硬编码。

## 7. 权限与事实边界

- 合同是静态规则，不是事实源。
- 钉钉、MES/WMS、扫码补录、数据中枢投影的事实优先级不变。
- `D:\输出skill` 继续只做 compare-only 答案钥匙。
- MES 继续只读。
- 合同不能让模型补数、猜数或将缺失改成 `0`。
- 权限策略不在本轮修改。

## 8. 迁移要求

迁移前后必须保持：

- 127 字段集合完全相同。
- 每个字段原有单位和容差相同。
- `classify_daily_report_field_gap()` 对现有字段的可观察结果保持兼容，并新增合同版本和截止时间。
- 当前事实来源排序不变。
- 当前 `/entry/fill` URL 参数行为不变。

允许改变：

- 缺项事件 payload 新增合同版本和截止时间。
- 现有异常队列显示人工事项截止时间。
- 调用者改为读取合同。
- 重复规则表删除。

## 9. 验收标准

### 9.1 结构门禁

1. 规范字段数量固定为 `127`。
2. 每个字段所有必需元数据非空。
3. 每个容差不超过 `20`，比率和单位字段保持更严格容差。
4. 所有合同补录字段都能映射到既有表单字段。
5. `GROUP_ACTIONS`、`FIELD_ACTIONS` 不再存在。
6. Gap adapter 不再自行推断 owner、deadline 或 entry fields。

### 9.2 行为门禁

1. 迁移前后的缺项行动兼容快照一致。
2. 关键字段 `total_output_daily`、`finished_inbound_daily`、`wip_total`、`total_electricity_kwh`、`daily_yield_rate` 的责任和补录路径正确。
3. 依赖型字段不生成错误的 `/entry/fill`。
4. 新建或更新的 `daily_fact_gap` payload 带合同版本和截止时间。
5. 日报 compare-only、MES 只读和钉钉证据测试不回归。
6. `/manage/alerts` 的人工事项显示合同截止时间，自动事项不显示虚假截止。

### 9.3 生产门禁

1. 对最近一个已完成业务日运行 compare-only 事实闭环，不采用答案钥匙填数。
2. 127 分母不变。
3. 生产缺项总数不得因迁移增加。
4. 需要人工的开放缺项全部具有 owner、entry route、deadline 和 contract version。
5. 自动复查缺项不产生新的人工提醒。
6. `/readyz`、MES sync、Hermes Stream 和日报 Outbox 保持健康。

## 10. 不做什么

- 不自动关闭历史 2725 个开放事件。
- 不在本轮聚合行动批次。
- 不新增提醒频率。
- 不新增升级角色或升级提醒；它们在主动追缺阶段与真实消费者一起设计。
- 不新增页面。
- 不重写表单引擎。
- 不接入尚未提供的能耗数据库。
- 不减少测试分母或日报字段分母。

## 11. 回滚

- 代码按单提交回滚。
- 无数据库 migration。
- 无生产事实改写。
- 若生产闭环门禁出现字段集合、来源优先级或缺项数量回归，恢复上一精确 SHA 并重新运行 compare-only 门禁。
