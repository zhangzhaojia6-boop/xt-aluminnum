from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.system import User
from app.models.user_preferences import UserPreferences
from app.schemas.user_preferences import UserPreferencesIn, UserPreferencesOut


router = APIRouter(tags=['user-preferences'])


def _is_missing_preferences_table(error: OperationalError) -> bool:
    return 'no such table: user_preferences' in str(error.orig).lower()


@router.get('/preferences', response_model=UserPreferencesOut)
def read_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserPreferencesOut:
    try:
        prefs = (
            db.query(UserPreferences)
            .filter(UserPreferences.user_id == current_user.id)
            .one_or_none()
        )
    except OperationalError as error:
        db.rollback()
        if _is_missing_preferences_table(error):
            return UserPreferencesOut(theme=None)
        raise
    return UserPreferencesOut(theme=prefs.theme if prefs else None)


@router.put('/preferences', response_model=UserPreferencesOut)
def upsert_preferences(
    payload: UserPreferencesIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserPreferencesOut:
    prefs = (
        db.query(UserPreferences)
        .filter(UserPreferences.user_id == current_user.id)
        .one_or_none()
    )
    if prefs is None:
        prefs = UserPreferences(user_id=current_user.id, theme=payload.theme)
        db.add(prefs)
    else:
        prefs.theme = payload.theme
    db.commit()
    db.refresh(prefs)
    return UserPreferencesOut(theme=prefs.theme)
