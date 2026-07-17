# Phase 1 钉钉真实证据闭环报告

## 结论

2026-07-18 00:07（北京时间），验收批次 `XT-P1-20260717-120813` 通过生产 PRE、重放去重、Hermes Gateway 重启和 POST 四段门禁。

本阶段已经证明：钉钉应用授权范围内的真实群聊、单聊和文件事件能够进入生产 Hermes 链路，形成可追踪的 `chat_inbox` 与 `multimodal_evidence` 记录；重复事件不会重复入库或重复下载；网关重启后仍能重新连接并接收新消息。

该结论只覆盖 Phase 1 钉钉真实证据闭环，不代表 Hermes 20 问、日报 127 字段对齐或后续投产阶段已经完成。

## 版本与证据

- 数据中枢版本：`d4eb882594c5e0d9708e3d3980fc9b6906995b84`
- Hermes 版本：`d21e9c247738d9d8029761534aea24668dc12119`
- 时间戳修复 CI：[GitHub Actions #29591333916](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29591333916)
- 时间戳修复生产部署：[GitHub Actions #29592002443](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29592002443)
- 钉钉生产凭据配置应用：[GitHub Actions #29593606628](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29593606628)
- 正式验收：[GitHub Actions #29594668906](https://github.com/zhangzhaojia6-boop/xt-aluminnum/actions/runs/29594668906)

所有普通日志和本文只记录状态、数量、哈希摘要及任务编号，不记录应用密钥、聊天原文或文件正文。

## PRE 门禁

正式工作流在重启前得到 `PASS`，无 blocker：

| 指标 | 结果 |
|---|---:|
| 候选 trace / 关联 trace / callback 台账 | 16 / 16 / 16 |
| 文本 / 文件 | 10 / 6 |
| 群聊 / 单聊 | 9 / 7 |
| 图片 / XLSX / PDF | 2 / 1 / 1 |
| 成功提取文字的文件 | 3 |
| U1 / U2 归一化样本 | 1 / 1 |
| 事件时间回退 | 0 |

文件文字只来自真实可解析内容：TXT、XLSX、CSV 共 3 份。2 份图片和 1 份 PDF 被如实标记为当前不支持提取，没有由模型补写文字。

## 去重与重启

- 文本重放返回 `duplicate`。
- 文件响应和文件证据均返回重复。
- 重放前后证据数量不变。
- 重放触发的额外下载次数为 0。
- Hermes Gateway 主进程从 `2983158` 切换为 `2985931`，进程启动时间同时改变。
- 新进程状态为 `running`，钉钉 Stream 状态为 `connected` 且状态时间新鲜。

重启后只发送了一次 R1。钉钉返回成功任务回执，生产工作流随后找到该事件并完成持久化，没有补发。

## POST 门禁

R1 入库后正式工作流再次得到 `PASS`，无 blocker：

| 指标 | 结果 |
|---|---:|
| 候选 trace / 关联 trace / callback 台账 | 17 / 17 / 17 |
| 文本 / 文件 | 11 / 6 |
| 群聊 / 单聊 | 10 / 7 |
| 成功提取文字的文件 | 3 |
| 事件时间回退 | 0 |

最终持久化计数为 `chat_inbox=17`、`multimodal_evidence=17`。前端产物和 Hermes journal 均未扫描到密钥内容；密钥只存在于受控生产环境配置中。

## 故障与修复

最初 6 份文件证据均出现 `download_failed`。根因不是消息没收到，而是 GitHub `production` 环境级钉钉 Secret 覆盖了仓库级 Secret，生产值已经落后于 DWS 当前启用凭据。

处理过程：

1. 只比较 AppKey、Secret 长度和不可逆摘要，确认环境级凭据漂移，没有输出明文。
2. 将 `production` 环境级凭据更新为 DWS 当前启用凭据，并通过受控工作流重新应用。
3. 验证生产凭据摘要一致，旧版和新版 token 接口都能正常取得令牌。
4. 通过已授权 DWS 历史消息和 DingDrive 下载原始 6 份文件，按原 `openMessageId` 对应，不使用答案钥匙或模型生成内容。
5. 本地与生产逐份比对 SHA-256 完全一致后，在事务中只修复这 6 条证据的真实哈希、大小、解析状态和可提取文字。

修复前已生成并验证可读的 PostgreSQL 备份：`aluminum-bypass-dingtalk-stream-20260717T154825Z.dump`，大小 18,647,517 字节，`pg_restore -l` 检查通过。

## 生产健康

正式工作流结束时：

- `/readyz` 为 `ready`。
- 数据库、设备绑定、排产、上传和 pipeline 检查正常。
- 外部 MES SQL Server 只读同步为 `fresh/success`，本轮读取 50 条并投影 50 条。
- Hermes 钉钉 Stream 为 `connected/fresh`。
- 能耗数据库仍为 `unconfigured`，这是已知待接入项，不伪装为已完成。

## 下一阶段

Phase 1 可以封档。下一步进入 Phase 2：以纯真实来源运行最近三个已完成业务日的 127 字段日报对齐，`D:\输出skill` 只用于 compare-only 判分，禁止拿答案钥匙回填事实。
