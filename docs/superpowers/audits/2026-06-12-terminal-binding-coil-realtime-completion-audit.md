# 鑫泰铝业 数据中枢：终端绑定、卷级线索、实时大屏完成审计

日期：2026-06-12

状态：完成前审计。目标不是宣布完成，而是逐项确认哪些已有证据、哪些仍缺外部条件。

## 1. 审计目标

原目标：

```text
按 TDD 模式执行 .omx/plans/2026-06-11-terminal-binding-coil-realtime-screen.md。
前端添加 taste skill 标准。
最终验收要确保完美。
清理本线程无用子智能体。
```

## 2. 已有强证据

| 要求 | 当前证据 | 判断 |
| --- | --- | --- |
| PC/一体机终端绑定 | 后端模型、迁移、接口、前端页面和测试已存在 | 已完成本地实现 |
| 卷级线索页 | `/manage/coils` 页面、路由、导航、后端接口和 E2E 已验证 | 已完成本地实现 |
| 自动废料线索 | 卷级线索页展示 MES 上机、下机和自动废料；异常状态有测试 | 已完成本地实现 |
| 物联网能耗影子链路 | 适配器、同步服务、影子表、调度、健康检查、预检工具已存在 | 本地链路完成 |
| 实时大屏 | `/manage/live` 已有流转模块、事件流、快照兜底和底部能耗状态 | 已完成本地实现 |
| taste 标准 | 前端 taste 测试覆盖页面动效、工业蓝、无重型光效、无横向溢出等 | 已完成本地门禁 |
| 30 分钟稳定性 | Playwright 长稳压测 `1 passed (30.5m)` | 已完成 |

## 3. 最新验证结果

```text
后端关键回归：112 passed
前端 taste/页面逻辑回归：88 passed
浏览器 E2E：14 passed
正式 /manage/live 30 分钟稳定性：1 passed (30.5m)
物联网预检增强单测：3 passed
物联网能耗相关回归：48 passed
前端能耗/大屏/taste 回归：37 passed
```

## 4. 仍未完成的唯一硬门槛

真实物联网数据库只读对账还不能完成。

当前预检输出：

```text
adapter=null
configured=false
connection.reason=missing_config
readiness.ready=false
readiness.required_env=IOT_ENERGY_ADAPTER
readiness.next_actions=配置物联网能耗只读连接
```

这说明当前不是代码连接失败，而是现场还没有配置物联网库连接和点位映射。

要完成这个门槛，现场还需要提供：

1. 物联网 SQL Server 地址、端口、库名。
2. 只读账号和密码。
3. 读数表或视图。
4. 采集时间、电量、气量、水量字段。
5. 表计/点位到车间、机列的映射。

## 5. 无用子智能体清理结果

检查范围：

1. 本地运行进程。
2. gstack 会话标记。
3. 本轮是否启动新的子智能体。

发现：

1. 当前 `Codex.exe`、`codex.exe`、`node_repl.exe` 是 Codex 桌面和当前会话必需进程。
2. `codegraph` 和 `context7` 是当前代码索引/文档工具服务，不属于无用子智能体。
3. 本轮没有启动 `team`、`subagent`、`omx team` 等独立工作子智能体。
4. 发现一个 2026-05-28 的零字节 `~/.gstack/sessions/1` 过期会话标记，已清理。

判断：

```text
当前没有可安全关闭的无用子智能体。
已清理过期 gstack 空会话标记。
```

## 6. 为什么现在不能标记整个目标完成

如果把目标标记完成，就等于声明“真实物联网能耗对账已经通过”。但当前没有外部物联网库配置，也没有真实点位样本，所以这项没有证据。

能证明的是：

1. 本地代码实现和测试门禁已经达标。
2. 大屏稳定性已经达标。
3. 预检工具已经准备好，拿到现场配置后能先只读验证。

不能证明的是：

1. 真实物联网库能连接。
2. 真实表计能全部映射到车间/机列。
3. 真实读数与电工填报能对账通过。

## 7. 下一步

如果继续推进，需要现场提供物联网库配置。拿到后执行：

```powershell
python scripts/check_iot_energy_preflight.py --json --business-date 2026-06-12 --limit 5
```

通过标准：

```text
connection.status=success
readings.count > 0
readings.meters_missing_mapping=[]
readiness.ready=true
```

只有这一步通过后，才建议开启后台同步任务。
