from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class BusinessException(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code


class NotFoundException(BusinessException):
    def __init__(self, message: str = "记录不存在"):
        super().__init__(message, 404)


class PermissionException(BusinessException):
    def __init__(self, message: str = "权限不足"):
        super().__init__(message, 403)


async def business_exception_handler(_: Request, exc: BusinessException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={'detail': exc.message})


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={'detail': exc.detail})
