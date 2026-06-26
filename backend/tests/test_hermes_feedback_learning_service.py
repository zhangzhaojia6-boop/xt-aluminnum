from app.services.hermes_feedback_learning_service import classify_feedback_learning


def test_low_risk_preference_becomes_auto_memory() -> None:
    result = classify_feedback_learning('以后日报先给简版', is_root_owner=True)

    assert result == {
        'learning_type': 'auto_memory',
        'status': 'accepted',
        'reason': '低风险表达偏好',
    }


def test_business_definition_becomes_candidate_knowledge() -> None:
    result = classify_feedback_learning('1650冷轧和1650车间按同一口径算', is_root_owner=True)

    assert result['learning_type'] == 'candidate_knowledge'
    assert result['status'] == 'needs_verification'


def test_non_owner_cannot_submit_construction_candidate() -> None:
    result = classify_feedback_learning('让 Codex 改日报 SQL', is_root_owner=False)

    assert result == {
        'learning_type': 'construction_request',
        'status': 'denied',
        'reason': '只有 root_owner 可以提交施工任务',
    }
