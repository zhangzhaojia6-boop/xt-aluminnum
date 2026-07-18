# Phase 2 事实合同生产失败基线

日期：2026-07-18

状态：Phase 2 开工证据，预期失败

## 运行边界

- 数据中枢生产版本：`d4eb882594c5e0d9708e3d3980fc9b6906995b84`
- 对齐模式：`compare-only`
- 生产事实来源：生产 PostgreSQL、MES/WMS SQL Server 只读投影、数据中枢填报与投影
- 答案钥匙：`D:\输出skill` 中 2026-07-15、2026-07-16、2026-07-17 三份日报正文，只参与比较，不参与事实生成
- 正式失败基线：[GitHub Actions #29627768799](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29627768799)
- 完整机器证据：该工作流 artifact `daily-report-alignment-production-29627768799`

工作流 `#29627718022` 因 Windows stdin 编码导致参考包 Base64 无效，未进入业务代码，不作为日报失败基线。

## 当前结果

| 业务日 | 已出现字段匹配 | 旧分母 | 旧匹配率 | 事实闭环 | 数据中枢缺字段 |
|---|---:|---:|---:|---|---:|
| 2026-07-15 | 9 | 124 | 7.26% | blocked | 79 |
| 2026-07-16 | 11 | 124 | 8.87% | blocked | 65 |
| 2026-07-17 | 12 | 124 | 9.68% | blocked | 65 |

这三个结果证明 compare-only 没有拿答案钥匙填数，但旧门禁还有一个关键盲点：它只把答案钥匙已经解析出的 124 个字段作为分母，没有把规范合同中另外 3 个“未出现且未声明 N/A”的字段标记为 `reference_absent`。

当前 `template_daily_field_contract.FIELD_GROUPS` 实际列出 130 个模板字段；历史 127 字段口径隐含排除了 `recovery_daily`、`recovery_month`、`remaining_contract_delta` 三个模板附加字段，却没有机器可读合同说明。Phase 2 必须把“130 个模板展示字段”和“127 个投产判分字段”明确分开，不能继续靠历史报告人工推算。

## 五个关键事实

| 业务日 | 总产量 | 成品入库 | 在制 | 总用电 | 成品率 |
|---|---|---|---|---|---|
| 2026-07-15 | confirmed | needs_evidence | missing | mismatch | mismatch |
| 2026-07-16 | mismatch | confirmed | mismatch | mismatch | mismatch |
| 2026-07-17 | needs_evidence | needs_evidence | mismatch | mismatch | mismatch |

当前事实值示例只用于定位链路，不在本文复述答案钥匙数值。总产量和成品入库已有 MES/WMS 投影 trace；在制存在日期/单位口径问题；总用电来自人工能耗汇总但缺完整证据锚；成品率来自投影且尚未保留可确认的完整分子分母。

## Phase 2 只解决什么

本阶段先让系统明确回答：

1. 127 个判分字段分别是什么、单位是什么、用哪个业务时间、允许哪些来源、容差是多少。
2. 钉钉、授权纠错、MES/WMS、扫码补录、数据中枢投影、历史和 RAG 谁先谁后。
3. 答案钥匙少写字段时，哪些是明确 N/A，哪些是阻塞门禁的 `reference_absent`。
4. 已出现字段匹配率和 127 字段规范覆盖率怎样同时计算。

本阶段不伪装完成 Phase 4。把 7.26% 至 9.68% 提高到 90% 以上，以及关闭五个关键事实缺口，仍属于后续 MES 连续可靠性和日报事实对齐阶段。
