# MES API 联调对接清单

> 适用阶段：Phase 1
> 目标：在 `MES` 保持卷级流转唯一真源、不改现场扫码流程的前提下，让 `aluminum-bypass` 完成 API 拉取、投影、驾驶舱展示的联调准备。

## 1. 这份清单解决什么

这份清单不是讲代码怎么写。

它解决的是：

- 跟 `MES` 对接前，双方要把哪些事情说死
- 哪些字段必须明确
- 哪些接口必须先给样例
- 哪些问题不问清楚，后面一定返工

一句话：

> 先把联调边界讲清楚，再开始接接口，不要一边联调一边猜字段。

## 2. 当前已知前提

- `MES` 继续做卷级流转唯一真源
- 现场一体机扫码流程不改
- `aluminum-bypass` 只做下游拉取、投影、估算、展示
- 管理层要求看到卷级变化的目标时效是 `5 分钟内`
- 当前系统已经支持：
  - `REST API MES adapter`
  - `MES 卷级投影`
  - `sync lag` 检查脚本
  - 管理层经营估算驾驶舱落点

## 3. 联调前必须确认的 10 件事

### 3.1 真源边界

必须确认：

- `MES` 是唯一卷级真源
- `aluminum-bypass` 不会回写或覆盖卷级主状态
- 联调阶段若两边数据冲突，以 `MES` 为准

### 3.2 接口地址与认证方式

必须拿到：

- `MES_API_BASE`
- 认证方式
  - API Key
  - 或 OAuth2
  - 或其他网关认证
- 测试环境地址
- 生产环境地址

必须确认：

- 是否区分测试环境和正式环境
- 是否有 IP 白名单
- 是否有请求频率限制

### 3.3 Tracking Card Info 接口

必须确认接口是否存在：

- `GET /tracking-cards/{card_no}`

这个接口在现场真实流程中的作用，不只是“查卡”。

它实际上承担：

- 手机扫码后
- 帮一线录入页自动带出 MES 头信息
- 并把这些头信息锁定，避免人工乱改

必须确认字段：

- `card_no`
- `process_route_code`
- `alloy_grade`
- `batch_no`
- `qr_code`
- `metadata`

最好同时确认是否还能返回：

- `product_type`
- `status`
- `finished_spec`
- `production_schedule`

必须问清：

- `batch_no` 到底是不是稳定业务字段
- `qr_code` 返回的是原始二维码内容，还是 MES 内部编码值
- 手机扫码页里哪些字段应该视为“MES 锁定字段”

### 3.4 Coil Snapshot 接口

必须确认接口是否存在：

- `GET /coil-snapshots`

必须确认字段：

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

如可能，也确认：

- `product_type`
- `finished_spec`
- `production_schedule`

### 3.5 游标与增量拉取规则

必须确认：

- 是按 `cursor` 拉，还是按 `updated_after` 拉
- `next_cursor` 为空时表示什么
- 重复返回旧数据是否正常
- 同一卷多次变更时，应该按哪个时间字段判新旧

### 3.6 时间字段口径

必须确认：

- 时间格式是否固定为 ISO8601
- 时区是 `+08:00` 还是 UTC
- `event_time` 和 `updated_at` 的含义区别

### 3.7 状态枚举

必须确认：

- 卷级 `status` 有哪些合法值
- 哪些表示“还在做”
- 哪些表示“已经完成”
- 哪些表示“停滞/异常/取消”

不要只拿一两个样例就开始写映射，必须让对方给完整枚举表。

### 3.8 合同关联规则

必须确认：

- `contract_no` 是卷级直接字段，还是需要从别的表推
- 一卷是否只归属一个合同
- 合同剩余量 / 在制量是否能直接从 MES 推，还是要我们侧自己汇总

### 3.9 错误与限流

必须确认：

- 认证失败返回什么
- 限流返回什么
- 服务端异常返回什么
- 是否允许重试
- 最大请求频率是多少

### 3.10 测试样例

联调前至少让对方提供这 3 套样例：

1. 正常卷级样例
2. 空数据 / 无结果样例
3. 异常 / 限流 / 错误样例

## 4. 我方需要准备的内容

### 4.1 环境变量

需要准备并填值：

- `MES_ADAPTER=rest_api`
- `MES_API_BASE=...`
- `MES_API_KEY=...`
- `MES_API_TIMEOUT_SECONDS=...`
- `MES_API_TRACKING_CARD_INFO_PATH=...`
- `MES_API_COIL_SNAPSHOTS_PATH=...`
- `MES_SYNC_LIMIT=...`
- `MES_SYNC_WINDOW_MINUTES=...`
- `MES_SYNC_POLL_MINUTES=...`
- `MES_SYNC_RETRY_LIMIT=...`
- `MES_SYNC_BACKOFF_SECONDS=...`

### 4.2 验证命令

联调时至少跑：

```bash
docker compose run --rm backend sh -lc "cd /workspace/backend && pytest tests/test_rest_api_mes_adapter.py tests/test_mes_api_contract.py tests/test_mes_sync_service.py tests/test_mes_sync_lag.py -q"
docker compose run --rm backend sh -lc "cd /workspace/backend && alembic upgrade head"
docker compose run --rm backend sh -lc "cd /workspace/backend && python scripts/check_mes_sync_lag.py --json"
cd frontend && npm run build
```

### 4.3 联调观察点

必须看：

- 是否真的拉到卷级数据
- `lag_seconds` 是否小于 `300`
- 驾驶舱是否出现合同推进/卷级变化
- `LiveDashboard` 是否从 `work_order_runtime` 切到 `mes_projection`
- 手机扫码后，MES 头字段是否自动带出并锁定
- 页面是否只要求主操填写“本工序补充字段”

## 5. 和 MES 方沟通时建议直接发的问题

你可以直接把下面这段发给对方：

```text
我们现在不改 MES 现场扫码流程，只需要做下游拉取和管理驾驶舱。

请协助确认以下内容：

1. 是否能提供 tracking card info 接口和 coil snapshots 接口
2. 接口地址、认证方式、测试环境地址
3. coil snapshot 的完整字段定义和状态枚举
4. cursor / updated_after 的增量拉取规则
5. 时间字段格式及时区
6. 限流规则、错误码、重试建议
7. 至少提供 3 套样例响应：正常、空数据、异常
8. 手机扫码后需要自动带出的头字段，哪些可以由 MES 直接返回
9. 这些自动带出的字段里，哪些应被视为锁定字段，不允许现场改写
```

## 6. 联调完成的最小标准

以下 4 条至少满足，才算“MES API 联调可进入实战阶段”：

1. 能成功拉到真实卷级数据
2. `coil_id / tracking_card_no / status / updated_at` 这些核心字段已稳定
3. 本地 `mes_coil_snapshots` 可以正确 upsert
4. `check_mes_sync_lag.py --json` 能返回有意义的同步状态

## 7. 当前阻塞判断

如果 `MES API` 还没搭好，不要停工。

当前最合理做法是：

- 先锁死契约
- 先拿样例
- 先做 mock 联调
- 等接口就绪后再切真实地址
