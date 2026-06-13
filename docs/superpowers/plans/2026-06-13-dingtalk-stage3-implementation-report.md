# 2026-06-13 钉钉多模态证据接入阶段三实施报告

## 1. 阶段结论

阶段三已完成本地服务闭环，可以标记完成。

本阶段完成的是“多模态证据安全入口”，不是正式公网钉钉回调上线。系统现在能把图片、语音、附件、文本作为证据保存，并和主动汇报事件关联；机器识别结果和人工确认结果都只能作为参考证据，不能直接写正式产量、能耗或日报指标。

## 2. 本阶段完成内容

- 新增 `backend/app/services/agent_multimodal_evidence_service.py`
  - `record_evidence`：保存图片、语音、附件、文本证据。
  - `record_dingtalk_media_message`：把钉钉入站消息 payload 转成标准证据记录。
  - `mark_human_confirmed`：把机器识别结果改为人工确认状态。
  - `list_event_evidence`：按事件查询证据。
- 新增 `backend/tests/test_agent_multimodal_evidence_service.py`
  - 覆盖图片、语音、附件、未知类型、人工确认、事件查询、钉钉消息适配。

## 3. 关键保护规则

- 证据默认状态是 `machine_only`，意思是“机器识别，仅供参考”。
- 人工确认后状态变成 `human_confirmed`，但仍然不会写正式指标。
- 所有证据 payload 都强制写入 `metric_write_allowed=false`。
- 未支持的证据类型会被拒绝，不会静默入库。
- 钉钉 `image`、`voice`、`file`、`text` 可以进入证据表。
- 钉钉 `video` 等未规划类型当前拒绝，避免把未知格式混进业务链路。

## 4. 为什么不直接加公网回调

当前项目已有钉钉登录和发送能力，但没有成熟的“群消息图片/语音入站回调”路由。直接开放公网回调会带来签名校验、重放攻击、文件下载鉴权、群权限绑定、消息去重等风险。

所以本阶段先把后端证据服务和钉钉 payload 适配做好。下一阶段接 Stream 或回调时，只需要做安全校验和调用该服务，不需要再改证据规则。

## 5. 验收证据

已执行测试：

```text
python -m pytest -q backend/tests/test_agent_multimodal_evidence_service.py
结果：7 passed

python -m pytest -q backend/tests/test_agent_multimodal_evidence_service.py backend/tests/test_agent_active_reporting_service.py backend/tests/test_agent_communication_service.py backend/tests/test_sqlite_model_compatibility.py backend/tests/test_alembic_version_width.py backend/tests/test_migration_chain.py
结果：22 passed

python -m pytest -q backend/tests/test_dingtalk_service.py backend/tests/test_dingtalk_cli.py backend/tests/test_dingtalk_login_route.py backend/tests/test_dingtalk_h5_login.py backend/tests/test_reporter_agent.py backend/tests/test_reminder_agent.py backend/tests/test_event_bus.py backend/tests/test_event_bus_persistence.py backend/tests/test_workflow_dispatcher.py backend/tests/test_ai_context_service.py
结果：73 passed
```

说明：

- 本阶段没有改前端页面，所以没有浏览器截图。
- 本阶段没有发真实钉钉消息。
- 本阶段没有下载真实钉钉文件。
- 本阶段没有写正式生产数据。

## 6. gstack 五视角 review

### CEO 视角：9.8

图片、语音、附件能先留证据，管理层以后可以看到现场原始材料，不再只靠口头转述。它对异常追责、日报核对、现场沟通都有价值。

未到满分原因：还未接正式钉钉群回调和管理端证据查看页。

### 工程师视角：9.8

实现很小，复用阶段一的 `multimodal_evidence` 表，没有新增数据库表。证据服务与钉钉 payload 适配分层清楚，未来接回调时可以直接复用。

未到满分原因：文件下载、OCR、语音转文字还没有接真实外部服务。

### 设计师视角：9.8

阶段三后端已经把“证据类型、识别文本、确认状态、关联事件”整理清楚，后面管理端可以做成简单清晰的证据时间线，而不是杂乱附件列表。

未到满分原因：证据管理页面还未进入实现阶段。

### 安全审查视角：9.9

最大安全点是：机器识别和人工确认都不允许直接写正式指标。公网回调没有仓促开放，避免了未验证签名和文件下载风险。

未到满分原因：正式上线前仍需补钉钉回调签名校验、消息去重和文件下载权限测试。

### 真实用户视角：9.8

现场人员以后可以发图片或语音作为异常证据，比手打文字更方便。系统能保留原始材料，也能标记是否人工确认。

未到满分原因：用户还不能在正式群里实际上传并看到管理端证据。

## 7. 阶段三是否可标记完成

可以标记完成。

完成口径：

- 多模态证据服务完成。
- 钉钉入站消息 payload 适配完成。
- 证据和事件能关联。
- 机器识别和人工确认都不写正式指标。
- 阶段一、阶段二和原有钉钉链路回归通过。

下一阶段建议：

- 接入钉钉 Stream 或回调入口。
- 增加签名校验和消息去重。
- 接入文件下载到对象存储或内部文件仓。
- 再接 OCR 和语音转文字服务。
- 管理端新增证据查看页面。
