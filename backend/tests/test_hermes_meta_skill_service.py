from app.services.hermes_meta_skill_service import plan_meta_skill_package


def test_meta_skill_package_uses_standard_skill_layout() -> None:
    plan = plan_meta_skill_package(
        skill_name='factory-normalization',
        reason='统一鑫泰车间、指标、单位和数据源优先级',
    )

    assert plan.skill_name == 'factory-normalization'
    assert plan.files == ['SKILL.md', 'scripts/normalize.py']
    assert plan.references == [
        'references/github_skill_research.md',
        'references/xintaily_business_rules.md',
    ]
    assert plan.tests == ['tests/test_factory_normalization_skill.py']
