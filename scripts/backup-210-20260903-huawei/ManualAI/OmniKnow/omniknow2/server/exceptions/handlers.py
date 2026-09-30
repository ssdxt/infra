# exceptions/handlers.py
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from utils.notifier import Notifier
from core.config import settings
from exceptions.base_errors import AppException
from utils.log import logger


project_name = settings.env.project_name


def register_exception_handlers(app: FastAPI):
    #捕获 Starlette 的 HTTP 异常（如404、401等）
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        if_notify = True
        if exc.status_code in [401, 404]:
            if_notify = False
        message = f"### 错误详情: \n- 错误详情{exc.detail}\n- 路由: {request.url.path}"
        if if_notify:
            notifier = Notifier()
            await notifier.send(project_name, message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": exc.detail, "code": exc.status_code, "data": None}
        )

    # 捕获请求验证错误
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        message = f"\n请求验证错误:\n- 错误详情: {exc.errors()}\n- 路由: {request.url.path}"
        logger.error(message)
        # notifier = Notifier()
        # await notifier.send(project_name, message)
        if request.headers.get("X-Message-List") == "list":
            err_msg = [err['msg'] for err in exc.errors()]  # 展示所有错误信息
        else:
            err_msg = exc.errors()[0]["msg"]  # 仅展示第一个错误信息
        return JSONResponse(
            status_code=422,
            content={"message": err_msg, "code": 422, "data": None}
        )

    # 捕获自定义的异常
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        # message = f"### 出现已捕获的异常:\n- 错误详情: {exc.message}\n- 路由: {request.url.path}"
        # notifier = Notifier()
        # await notifier.send(project_name, message)
        return JSONResponse(
            status_code=200,
            content={"message": exc.message, "code": exc.code, "data": None}
        )

    # 捕获其他所有未处理的异常
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        if "lost connection to MySQL server during query" in str(exc):
            res_msg = "服务器繁忙，请重试"
            message = f"### 数据库连接终端:\n - 错误详情: {str(exc)}\n - 路由: {request.url.path}"
        else:
            res_msg = "出现意料之外的错误，请联系管理员。"
            message = f"### 出现意料之外的错误:\n - 错误详情: \n```\n{str(exc)}\n```\n - 路由: \n```\n{request.url.path}\n```\n"
        notifier = Notifier()
        res = await notifier.send(project_name, message)
        logger.error(f"出现意料之外的错误: {str(exc)}")
        return JSONResponse(
            status_code=200,
            content={"message": res_msg, "code": 500, "data": {"is_notified": res}}
        )
