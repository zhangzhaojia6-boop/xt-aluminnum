"""企业微信账号映射服务。

用于替代手工逐个排查企业微信账号与系统账号关系，
统一提供登录映射和批量试点检查能力。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.system import User


@dataclass(frozen=True)
class WecomMappingResult:
    """企业微信账号映射结果。"""

    status: str
    wecom_userid: str
    user: User | None
    matched_by: str | None
    conflicts: list[User]


def _normalize_userid(value: str) -> str:
    """清理企业微信账号文本。"""

    return (value or "").strip()


def resolve_wecom_user(db: Session, *, wecom_userid: str) -> WecomMappingResult:
    """解析企业微信账号与系统用户的映射关系。"""

    normalized = _normalize_userid(wecom_userid)
    if not normalized:
        return WecomMappingResult(
            status="invalid",
            wecom_userid=normalized,
            user=None,
            matched_by=None,
            conflicts=[],
        )

    exact_matches = (
        db.query(User)
        .filter(
            or_(
                User.username == normalized,
                User.dingtalk_user_id == normalized,
            )
        )
        .order_by(User.id.asc())
        .all()
    )
    unique_exact = {item.id: item for item in exact_matches}
    if len(unique_exact) > 1:
        return WecomMappingResult(
            status="ambiguous",
            wecom_userid=normalized,
            user=None,
            matched_by="exact",
            conflicts=list(unique_exact.values()),
        )
    if len(unique_exact) == 1:
        user = list(unique_exact.values())[0]
        if not user.is_active:
            return WecomMappingResult(
                status="inactive",
                wecom_userid=normalized,
                user=user,
                matched_by="exact",
                conflicts=[],
            )
        return WecomMappingResult(
            status="matched",
            wecom_userid=normalized,
            user=user,
            matched_by="exact",
            conflicts=[],
        )

    lowered = normalized.lower()
    insensitive_matches = (
        db.query(User)
        .filter(
            or_(
                func.lower(User.username) == lowered,
                func.lower(User.dingtalk_user_id) == lowered,
            )
        )
        .order_by(User.id.asc())
        .all()
    )
    unique_insensitive = {item.id: item for item in insensitive_matches}
    if len(unique_insensitive) > 1:
        return WecomMappingResult(
            status="ambiguous",
            wecom_userid=normalized,
            user=None,
            matched_by="case_insensitive",
            conflicts=list(unique_insensitive.values()),
        )
    if len(unique_insensitive) == 1:
        user = list(unique_insensitive.values())[0]
        if not user.is_active:
            return WecomMappingResult(
                status="inactive",
                wecom_userid=normalized,
                user=user,
                matched_by="case_insensitive",
                conflicts=[],
            )
        return WecomMappingResult(
            status="matched",
            wecom_userid=normalized,
            user=user,
            matched_by="case_insensitive",
            conflicts=[],
        )

    return WecomMappingResult(
        status="not_found",
        wecom_userid=normalized,
        user=None,
        matched_by=None,
        conflicts=[],
    )
