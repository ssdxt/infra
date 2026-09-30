import json

from fastapi import APIRouter, Depends, Body
from redis.asyncio import Redis

from core.dependencies import RequestContext, get_request_context, authorize
from core.config import settings
from ext.redis_client import get_redis
from services import UserService, SpaceService
from schemas import ResponseModel, UserProfileRequest

router = APIRouter()


@router.get("/me/profile")
async def get_personal_profile(
        ctx: RequestContext = Depends(
            authorize("public")
        )
) -> ResponseModel:
    """
    获取登录用户的个人信息
    """
    profile = await UserService(ctx).get_personal_profile()
    return ResponseModel.success(profile)


@router.patch("/me/profile")
async def update_personal_profile(
        profile: UserProfileRequest,
        ctx: RequestContext = Depends(get_request_context)
) -> ResponseModel:
    """
    更新登录用户的个人信息
    """
    await UserService(ctx).update_person_profile(profile)
    return ResponseModel.success()


@router.patch("/me/password")
async def update_personal_password(
        data: dict = Body(..., example={"password": "base64_encoded_new_password"}),
        ctx: RequestContext = Depends(get_request_context)
) -> ResponseModel:
    """
    更新登录用户的密码
    """
    # 假设 UserService 有一个方法 update_person_password
    await UserService(ctx).update_person_password(data.get('password'))
    return ResponseModel.success()


@router.get("/me/sessions")
async def get_active_sessions(
        ctx: RequestContext = Depends(get_request_context)
) -> ResponseModel:
    """查看当前用户的活跃会话列表"""
    key = f"user_sessions:{ctx.user.uuid}"
    sessions_raw = await ctx.redis.smembers(key)
    sessions = []
    for s in sessions_raw:
        try:
            data = json.loads(s)
            sessions.append(data)
        except (json.JSONDecodeError, TypeError):
            continue
    # 按登录时间倒序
    sessions.sort(key=lambda x: x.get("login_time", ""), reverse=True)
    return ResponseModel.success({"sessions": sessions})


@router.delete("/me/sessions/{session_jti}")
async def revoke_session(
        session_jti: str,
        ctx: RequestContext = Depends(get_request_context)
) -> ResponseModel:
    """踢出指定会话（将 token 加入黑名单）"""
    # 将 jti 加入黑名单
    expire_seconds = settings.env.expire_time * 24 * 60 * 60
    await ctx.redis.setex(f"token_blacklist:{session_jti}", expire_seconds, "revoked")

    # 从会话列表中移除
    key = f"user_sessions:{ctx.user.uuid}"
    sessions_raw = await ctx.redis.smembers(key)
    for s in sessions_raw:
        try:
            data = json.loads(s)
            if data.get("jti") == session_jti:
                await ctx.redis.srem(key, s)
                break
        except (json.JSONDecodeError, TypeError):
            continue

    return ResponseModel.success()


@router.get("/me/spaces")
async def get_space_by_user(
        ctx: RequestContext = Depends(get_request_context)
) -> ResponseModel:
    """
    获取用户空间列表
    """
    space = SpaceService(ctx)
    res = await space.get_space_list_by_user()
    return ResponseModel.success(res)

