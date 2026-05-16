from pydantic import BaseModel


class ErrorReport(BaseModel):
    message: str
    stack: str | None = None
    url: str
    info: str | None = None
    user_agent: str | None = None


class PerfReport(BaseModel):
    route: str
    metric: str
    value: float
    user_agent: str | None = None
