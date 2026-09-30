import json
import traceback

from core.config import settings
from repository import UserRepository, SpaceRepository, RoleRepository
from audit.repository import AuditRepository
from schemas import UserRegisterSchema, UserLoginRequest
from schemas.user import UserSelfRegisterSchema
from exceptions.errors.resource import SpaceNotExistedError
from exceptions.errors.users import UserRegisterError, UserBannedError, UserLoginBannedError, UserExistedError, \
    LoginError
from core.security import create_token
from core.permission_cache import refresh_user_permissions
from utils import base64_to_str, encode_password, hash_md5, hash_sha512
from utils import logger
from utils.password_validator import validate_password_strength

from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

import os


from datetime import datetime
from fastapi import Request


class AuthService:
    def __init__(self, db: AsyncSession, redis: Redis, request: Request = None):
        self.session = db
        self.user_repo = UserRepository(db)
        self.space_repo = SpaceRepository(db)
        self.role_repo = RoleRepository(db)
        self.activity_log = AuditRepository(db)
        self.redis = redis
        self.request = request

        self.MAX_ATTEMPTS = 5  # 最大尝试次数
        self.LOCK_TIME = 300  # 锁定时间（秒）
        self.WINDOW_TIME = 600  # 统计窗口时间（秒）

    async def check_user_certificate(self, login_info: UserLoginRequest) -> dict:
        """检查用户登录凭证"""
        login_user, password = login_info.username, login_info.password
        lock_key, attempt_key = f"lock:{login_user}", f"attempts:{login_user}"

        # 检查是否已被锁定
        if await self.redis.exists(lock_key):
            lock_time = await self.redis.ttl(lock_key)
            raise LoginError(f"账户已被锁定，请在 {lock_time} 秒后重试。")

        user = await self.user_repo.get_user_by_account(login_user)
        if not user:
            # 登录失败审计（用户不存在）
            await self.activity_log.create_log_from_request(
                request=self.request,
                user_id=None,
                action="login_failed",
                detail={"reason": "user_not_found", "account": login_user},
            )
            raise LoginError

        # 验证密码
        password_decoded = base64_to_str(password)
        if hash_sha512(f"{password_decoded}{user.salt}") != user.password:
            current_attempts = await self.redis.incr(attempt_key)
            if current_attempts == 1:
                await self.redis.expire(attempt_key, self.WINDOW_TIME)

            # 登录失败审计
            await self.activity_log.create_log_from_request(
                request=self.request,
                user_id=user.uuid,
                action="login_failed",
                space_id=user.space_id,
                detail={"reason": "wrong_password", "attempts": current_attempts},
            )

            if current_attempts >= self.MAX_ATTEMPTS:
                await self.redis.setex(lock_key, self.LOCK_TIME, "locked")
                await self.redis.delete(attempt_key)
                raise UserLoginBannedError(self.LOCK_TIME)
            raise LoginError

        # 清除错误缓存
        await self.redis.delete(attempt_key)

        # 检查用户是否可用
        if user.status != 1:
            raise UserBannedError

        # 加载权限到 Redis 缓存
        await refresh_user_permissions(self.redis, user.uuid, self.session)

        token, jti = await create_token({
            "source": str(user.source),
            "uuid": str(user.uuid),
        })

        # 记录会话信息到 Redis
        session_info = json.dumps({
            "jti": jti,
            "ip": self.request.client.host if self.request and self.request.client else None,
            "user_agent": self.request.headers.get("user-agent") if self.request else None,
            "login_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        expire_seconds = settings.env.expire_time * 24 * 60 * 60
        await self.redis.sadd(f"user_sessions:{user.uuid}", session_info)
        await self.redis.expire(f"user_sessions:{user.uuid}", expire_seconds)

        # 登录成功审计
        await self.activity_log.create_log_from_request(
            request=self.request,
            user_id=user.uuid,
            action="login_success",
            space_id=user.space_id,
        )

        return {"token": token}

    async def share_register(self, user: UserRegisterSchema):
        """使用共享链接进行注册"""
        password = base64_to_str(user.password)
        validate_password_strength(password)
        salt = os.urandom(32).hex()
        try:
            async with self.session.begin():
                # 检查注册code是否正确
                space = await self.space_repo.get_by_code(user.code)
                if not space:
                    raise SpaceNotExistedError

                # 检查账号是否已存在
                if await self.user_repo.exists_by_account(user.account):
                    raise UserExistedError(user.account)

                logger.info(f"用户使用共享链接注册，账号：{user.account}，所属空间：{space.uuid}")

                password_hash = await encode_password(password, salt)

                user = await self.user_repo.create(
                    space_id=space.uuid,
                    account=user.account,
                    name=user.name,
                    source="本地注册",
                    salt=salt,
                    password_hash=password_hash,
                )
                # 注册成功则添加详细信息
                await self.user_repo.update_deatil(user, {})
                await self.space_repo.add_user_to_space(space, user)
                await self.user_repo.add_default_role_to_user(user)
                logger.info(f"用户注册成功，账号：{user.account}，所属空间：{space.uuid}")
                return {
                    "uuid": str(user.uuid),
                    "account": user.account,
                    "name": user.name,
                    "source": user.source
                }
        except Exception as e:
            traceback.print_exc()
            logger.error(f"用户注册失败，事务已回滚，\n账号：{user.account}，错误信息：{str(e)}")
            raise UserRegisterError(user.account)


    async def self_register(self, reg: UserSelfRegisterSchema):
        """独立注册（无需 Space 邀请码），自动创建个人空间"""
        password = base64_to_str(reg.password)
        validate_password_strength(password)
        salt = os.urandom(32).hex()

        try:
            async with self.session.begin():
                if await self.user_repo.exists_by_account(reg.account):
                    raise UserExistedError(reg.account)

                logger.info(f"用户独立注册，账号：{reg.account}")

                password_hash = await encode_password(password, salt)
                user = await self.user_repo.create(
                    account=reg.account,
                    name=reg.name,
                    source="本地注册",
                    salt=salt,
                    password_hash=password_hash,
                )
                await self.user_repo.update_deatil(user, {})
                await self.user_repo.add_default_role_to_user(user)

                # 自动创建个人默认 Space
                from db.models.rag import Space

                code = hash_md5(str(reg.account) + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                space = Space(
                    name=f"{reg.name}的空间",
                    description="个人默认空间",
                    owner=user.uuid,
                    code=code,
                )
                self.session.add(space)
                await self.session.flush()

                # 绑定用户到空间
                user.space_id = space.uuid
                user.space_role = "owner"

                # 审计日志
                await self.activity_log.create_log_from_request(
                    request=self.request,
                    user_id=user.uuid,
                    action="register",
                    space_id=space.uuid,
                    target_type="user",
                    target_id=user.uuid,
                    detail={"method": "self_register"},
                )

                logger.info(f"用户独立注册成功，账号：{user.account}，空间：{space.uuid}")
                return {
                    "uuid": str(user.uuid),
                    "account": user.account,
                    "name": user.name,
                    "source": user.source,
                    "space_uuid": str(space.uuid),
                }
        except (UserExistedError, Exception) as e:
            if isinstance(e, UserExistedError):
                raise
            traceback.print_exc()
            logger.error(f"用户独立注册失败，事务已回滚，账号：{reg.account}，错误：{str(e)}")
            raise UserRegisterError(reg.account)

    async def check_user_exist(self, account: str):
        """
        检查用户是否存在
        """
        return await self.user_repo.exists_by_account(account)