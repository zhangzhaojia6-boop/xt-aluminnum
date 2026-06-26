from __future__ import annotations


def classify_feedback_learning(feedback_text: str, *, is_root_owner: bool) -> dict[str, str]:
    clean = str(feedback_text or '').strip()
    if any(token in clean for token in ('Codex', '改', '新增接口', 'SQL', '补测试')):
        if not is_root_owner:
            return {
                'learning_type': 'construction_request',
                'status': 'denied',
                'reason': '只有 root_owner 可以提交施工任务',
            }
        return {
            'learning_type': 'construction_request',
            'status': 'needs_codex',
            'reason': '涉及系统施工',
        }
    if any(token in clean for token in ('口径', '按同一', '归一', '车间', '指标')):
        return {
            'learning_type': 'candidate_knowledge',
            'status': 'needs_verification',
            'reason': '涉及业务口径或数据映射',
        }
    return {
        'learning_type': 'auto_memory',
        'status': 'accepted',
        'reason': '低风险表达偏好',
    }
