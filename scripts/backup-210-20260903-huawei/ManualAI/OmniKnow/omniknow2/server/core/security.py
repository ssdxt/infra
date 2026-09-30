from fastapi import Depends, HTTPException, Security, Request, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from core.config import settings
from schemas.user import CurrentUser
from ext.redis_client import get_redis
from utils import logger

import os
import uuid
import hmac
import hashlib
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode


security = HTTPBearer(auto_error=False)

SECRET = settings.env.secret_key

def decode_jwt(token: str):
    try:
        payload = jwt.decode(
            token,
            SECRET,
            algorithms=[settings.env.algorithm],
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录凭证无效或已过期，请重新登录",
        )

# async def authenticate(api_key: str, api_secret: str):
#     key = settings.api.key
#     secret = settings.api.secret
#
#     secret_b64 = hashlib.sha512(secret.encode()).hexdigest()
#
#     if api_key == key and api_secret == secret_b64:
#         token = await create_token({'sub': key})
#         logger.debug(f"{api_key} 登录成功")
#         return token
#     else:
#         logger.warning(f"{api_key} 登录失败")
#         raise HTTPException(status_code=401, detail="Token获取失败，请检查配置！")

async def create_token(data: dict) -> tuple[str, str]:
    """创建 JWT token，返回 (token, jti)"""
    to_encode = data.copy()
    jti = str(uuid.uuid4())
    expires_delta = timedelta(days=settings.env.expire_time)
    to_encode.update({
        "exp": datetime.now() + expires_delta,
        "jti": jti,
    })
    token = jwt.encode(to_encode, SECRET, algorithm=settings.env.algorithm)
    return token, jti


async def check_auth_credentials(
    credentials: HTTPAuthorizationCredentials = Security(security),
    redis=Depends(get_redis),
):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET, algorithms=[settings.env.algorithm])

        # 检查 token 是否已被加入黑名单
        jti = payload.get("jti")
        if jti:
            is_blacklisted = await redis.exists(f"token_blacklist:{jti}")
            if is_blacklisted:
                raise HTTPException(status_code=401, detail="Token已失效，请重新登录")

        user = CurrentUser(**payload)
        return user
    except HTTPException:
        raise
    except JWTError as e:
        logger.error(f"Token校验失败：{e}")
        raise HTTPException(status_code=401, detail="Token无效或已过期")
    except AttributeError as e:
        logger.error(f"Token校验失败：{e}")
        raise HTTPException(status_code=401, detail="Token无效或已过期")


async def verify_signature_smart(
        request: Request,
        x_signature: str = Header(...),
        x_timestamp: str = Header(...),
        # 假设文件上传时，客户端必须传文件的 hash
        x_file_hash: str = Header(None)
):
    content_type = request.headers.get("content-type", "")

    # --- 1. 确定用于签名的 Body 字符串 ---
    signed_body = ""

    if "application/json" in content_type:
        # JSON: 直接读原文 (去除多余空格通常由前端处理，这里假设是 Raw String)
        body_bytes = await request.body()
        signed_body = body_bytes.decode("utf-8")

        # 重置 body 供后续读取
        async def receive():
            return {"type": "http.request", "body": body_bytes}

        request._receive = receive

    elif "application/x-www-form-urlencoded" in content_type:
        # 表单: 解析并排序
        body_bytes = await request.body()
        params = parse_qsl(body_bytes.decode("utf-8"))
        params.sort(key=lambda x: x[0])
        signed_body = urlencode(params)

        # 重置 body
        async def receive():
            return {"type": "http.request", "body": body_bytes}

        request._receive = receive

    elif "multipart/form-data" in content_type:
        # 文件上传: 必须依赖 Header 中的文件哈希，不能读 Body
        if not x_file_hash:
            raise HTTPException(400, "File upload requires X-File-Hash header")
        signed_body = x_file_hash

    # --- 2. 拼接 Message ---
    # 格式：METHOD|PATH|TIMESTAMP|BODY_OR_HASH
    message = f"{request.method}|{request.url.path}|{x_timestamp}|{signed_body}"

    api_secret = settings.api.secret
    # --- 3. 校验 ---
    expected_sig = hmac.new(
        api_secret.encode(), message.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, x_signature):
        raise HTTPException(403, "Invalid signature")