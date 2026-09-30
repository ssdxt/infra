from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from db.session import get_session
from ext.redis_client import get_redis

from schemas.user import UserLoginRequest, UserRegisterSchema, UserSelfRegisterSchema
from schemas.public import ResponseModel
from services import AuthService


router = APIRouter()


@router.post("/login")
async def user_login_auth(
        request: Request,
        login_info: UserLoginRequest,
        db: AsyncSession = Depends(get_session),
        redis: Redis = Depends(get_redis)
) -> ResponseModel:
    auth_service = AuthService(db, redis, request)
    res = await auth_service.check_user_certificate(login_info)
    return ResponseModel.success(res)


@router.put("/share/register")
async def user_register(
        request: Request,
        user: UserRegisterSchema,
        db: AsyncSession = Depends(get_session),
        redis: Redis = Depends(get_redis)
) -> ResponseModel:
    """
    用户使用共享链接进行注册
    """
    auth_service = AuthService(db, redis, request)
    res = await auth_service.share_register(user)
    return ResponseModel.success(res)


@router.post("/register")
async def user_self_register(
        request: Request,
        reg: UserSelfRegisterSchema,
        db: AsyncSession = Depends(get_session),
        redis: Redis = Depends(get_redis)
) -> ResponseModel:
    """
    独立注册（无需 Space 邀请码），自动创建个人空间
    """
    auth_service = AuthService(db, redis, request)
    raise NotImplementedError
    res = await auth_service.self_register(reg)
    return ResponseModel.success(res)


@router.get("/users/exist")
async def check_user_exist(
        account: str,
        db: AsyncSession = Depends(get_session),
        redis: Redis = Depends(get_redis)
) -> ResponseModel:
    """
    检查用户是否存在
    """
    auth_service = AuthService(db, redis)
    res = await auth_service.check_user_exist(account)
    return ResponseModel.success(res)


# @router.post("/oauth/login")
# async def oauth_login(
#         request: Request,
#         provider: str,
#         token: str,
#         db: AsyncSession = Depends(get_session),
#         redis: Redis = Depends(get_redis)
# ) -> ResponseModel:
#     """
#     第三方 OAuth 登录
#     """
#     auth_service = AuthService(db, redis, request)
#     res = await auth_service.oauth_login(provider, token)
#     return ResponseModel.success(res)