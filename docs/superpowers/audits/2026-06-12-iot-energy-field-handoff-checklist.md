# 鑫泰铝业 数据中枢：物联网能耗库现场联调清单

日期：2026-06-12

状态：现场联调用。只读，不要求改生产数据。

## 1. 现场需要提供的信息

请物联网模块或数据库负责人提供以下信息：

1. 数据库类型：SQL Server。
2. 数据库地址和端口。
3. 数据库名。
4. 只读账号。
5. 只读密码。
6. 读数表名或视图名。
7. 表计/点位编码字段。
8. 表计/点位名称字段。
9. 采集时间字段。
10. 电量字段，单位最好是 kWh。
11. 气量字段，单位最好是 m3。
12. 水量字段，单位最好是 m3。
13. 查询一天数据的时间字段口径。
14. 每个表计/点位对应的车间和机列。

## 2. 本系统需要配置的环境变量

```text
IOT_ENERGY_ADAPTER=sqlserver
IOT_ENERGY_SQLSERVER_HOST=数据库地址
IOT_ENERGY_SQLSERVER_PORT=1433
IOT_ENERGY_SQLSERVER_DATABASE=数据库名
IOT_ENERGY_SQLSERVER_USERNAME=只读账号
IOT_ENERGY_SQLSERVER_PASSWORD=只读密码
IOT_ENERGY_SQLSERVER_QUERY=只读查询 SQL
IOT_ENERGY_METER_MAP=表计到车间/机列的映射 JSON
```

注意：

1. 前端不能配置数据库账号。
2. 数据库账号只能放在后端环境变量里。
3. 查询 SQL 只允许读，不允许写、删、改。
4. 先跑预检，不要直接开同步任务。

## 3. 预检命令

在后端目录执行：

```powershell
python scripts/check_iot_energy_preflight.py --json --business-date 2026-06-12 --limit 5
```

如果还没配置，预期会看到：

```text
readiness.ready=false
readiness.required_env=IOT_ENERGY_ADAPTER
readiness.next_actions=配置物联网能耗只读连接
```

如果 SQL Server 信息没配全，预期会看到：

```text
connection.reason=missing_sqlserver_config
readiness.required_env=缺少的配置项
```

如果能读到数据但有表计没映射，预期会看到：

```text
readings.meters_missing_mapping=未映射表计列表
```

## 4. 通过标准

必须同时满足：

1. `connection.status=success`。
2. `readings.count > 0`。
3. `readings.meters_missing_mapping` 为空。
4. `readiness.ready=true`。
5. 输出里不出现数据库密码或敏感连接串。

## 5. 通过后才能做什么

通过预检后，才能开启后台同步，把读数写入本系统的 `iot_energy_snapshots` 影子表。

管理端页面仍然只读取本系统接口，不直接读取物联网数据库。
