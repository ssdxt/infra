import asyncio

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.dependencies import RequestContext, authorize
from schemas.public import ResponseModel
from schemas.task import TaskStatusQuerySchema
from services.task import TaskService
from db.session import get_session, async_session
from ext.redis_client import get_redis
from utils import logger

router = APIRouter()


def _verify_callback_token(x_callback_token: str | None = Header(None)) -> None:
    """
    验证 Worker 回调鉴权 Token。
    若 ENV_CALLBACK_SECRET 未配置则跳过验证（兼容未启用鉴权的部署）。
    """
    expected = settings.parser.callback_secret
    if expected and x_callback_token != expected:
        raise HTTPException(status_code=401, detail="无效的回调 Token")


async def _run_complete_callback(task_id: str):
    """后台协程：使用独立 session 处理完成回调"""
    async with async_session() as session:
        redis = get_redis(1, True)
        try:
            task = TaskService(redis, session)
            await task.task_complete_callback(task_id)
        except Exception as e:
            logger.error(f"任务 {task_id} 后台回调处理异常: {e}")
        finally:
            await redis.aclose()


@router.post("/tasks/{task_id}/complete")
async def task_complete_callback(
    task_id: str,
    _: None = Depends(_verify_callback_token),
):
    """
    任务完成回调接口（由 Celery Worker 在解析成功后调用）。

    立即返回 202 Accepted，在后台协程中处理 OSS 上传与 DB 写入，
    避免 Worker 因等待超时而重复回调。
    """
    asyncio.create_task(_run_complete_callback(task_id))
    return JSONResponse(
        status_code=202,
        content=ResponseModel.success(message="回调已接收，正在后台处理"),
    )


@router.post("/tasks/{task_id}/fail")
async def task_fail_callback(
    task_id: str,
    reason: str = "",
    session: AsyncSession = Depends(get_session),
    _: None = Depends(_verify_callback_token),
):
    """任务失败回调接口（由 Celery Worker 在解析失败后调用）"""
    redis = get_redis(1, True)
    try:
        task = TaskService(redis, session)
        res = await task.task_fail_callback(task_id, reason)
        return ResponseModel.success(res)
    finally:
        await redis.aclose()


@router.post("/tasks/status")
async def task_status_check(
    request: TaskStatusQuerySchema,
    ctx: RequestContext = Depends(authorize("public")),
):
    """任务状态查询接口（面向前端用户）"""
    redis = get_redis(1, True)
    try:
        task = TaskService(redis, ctx.db)
        res = await task.get_task_progress(request, ctx.user)
        return ResponseModel.success(res)
    finally:
        await redis.aclose()
