from __future__ import annotations

from app.services.hermes_factory_brain_types import FactoryBrainSkillPackagePlan


def plan_meta_skill_package(skill_name: str, reason: str) -> FactoryBrainSkillPackagePlan:
    clean_name = str(skill_name or '').strip()
    clean_reason = str(reason or '').strip()
    return FactoryBrainSkillPackagePlan(
        skill_name=clean_name,
        reason=clean_reason,
        files=['SKILL.md', 'scripts/normalize.py'],
        references=['references/github_skill_research.md', 'references/xintaily_business_rules.md'],
        tests=[f'tests/test_{clean_name.replace("-", "_")}_skill.py'],
    )
