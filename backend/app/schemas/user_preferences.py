from typing import Literal, Optional

from pydantic import BaseModel


ThemeValue = Optional[Literal['hud']]


class UserPreferencesIn(BaseModel):
    theme: ThemeValue = None


class UserPreferencesOut(BaseModel):
    theme: ThemeValue = None
