from __future__ import annotations

from app.services.hermes_factory_brain_types import FactoryBrainCapability


def list_factory_capabilities() -> list[FactoryBrainCapability]:
    return [
        FactoryBrainCapability('sql-api-file', 'structured_data', 10, True, '优先读取 SQL、API、表格、文档解析结果'),
        FactoryBrainCapability('dingtalk-context-ingestion', 'dingtalk', 20, True, '读取授权群聊文本和专项责任人文件'),
        FactoryBrainCapability('rag-retriever', 'rag', 60, True, '解释知识、路由知识和工艺知识，不当数字事实源'),
        FactoryBrainCapability('browse-research', 'browse', 70, True, '网页资料或内部页面没有 API 时使用'),
        FactoryBrainCapability('computer-use-operator', 'computer_use', 90, True, '没有 API 且必须像人一样操作页面时使用'),
        FactoryBrainCapability('image-generation', 'image', 100, True, '生成培训、汇报和知识卡片图片，不当现场照片'),
    ]
