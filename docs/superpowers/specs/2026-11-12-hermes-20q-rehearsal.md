# 20 问验收演练模式

## 问题

`backend/scripts/hermes_20_question_acceptance.py` 只能带 `--real-delivery` 运行：每题都会真实发钉钉工作通知，并把 chat_inbox、agent_runs、outbox 写进生产库。所以没法在生产上随时复测智能体，只能先恢复备份到临时库再跑。

## 目标

在生产机上直接跑 20 问，得到和真实验收一致的答案与判定，同时不发任何消息、不在生产库留下记录。

## 做法

脚本加 `--rehearsal`：

- 与 `--real-delivery`、`--target` 互斥。
- 会话绑定到一个开着外层事务的连接（`join_transaction_mode="create_savepoint"`），编排器里的 `commit()` 只提交保存点，结束时整体回滚。
- 运行期间把 `agent_communication_service.dispatch_outbox_message` 换成不发送的版本，返回状态 `rehearsal`。
- 判定、取数、回答生成不改。报告只打印到标准输出；退出码只看 `core_passed`。

## 不做

- 不新增服务或配置项，不改编排器和运行器。
- 不覆盖交付门禁：演练模式下交付必然不通过，报告里如实显示。

## 评审结论（plan-eng-review，11/12）

- 架构：编排器通过模块属性调用 `dispatch_outbox_message`，用 `unittest.mock.patch.object` 替换即可生效。已核对取数链路（编排器、证据、派生事实、事实包、MES 读取、回复通道、运行器）都只用传入的会话，没有另开会话或对外写入，外层事务能兜住全部写入。
- 精简：演练模式不写报告文件，只打印到标准输出。生产机仓库是部署用的工作区，往 `docs/superpowers/reports` 写文件会弄脏它，影响下次 ff-only 部署。演练也不和 `--require-daily-report-gate` 组合（那会写比对产物）。
- 代码：会话和替换放进脚本里一个 `contextmanager`，不新增模块。
- 测试：一个测试即可。用 sqlite 引擎跑这个 contextmanager，在里面写一行并 `commit()`，退出后行不存在，且替换后的发送函数被调用而真实发送没被调用。
- 性能：无新增开销。
- 不在范围：给交付门禁做演练；演练结果入库或推送。

## 验收

- 单测：演练运行后，数据库里没有新增 chat_inbox / agent_runs / outbox 记录，也没有调用真实发送。
- 生产：对最近一个业务日跑一次，确认运行前后这三张表的行数不变，拿到 20 题的当前成绩。
