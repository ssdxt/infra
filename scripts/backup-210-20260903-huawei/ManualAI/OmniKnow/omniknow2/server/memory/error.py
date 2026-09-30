from exceptions.base_errors import AppException
from schemas.error import ErrorCode

from pydantic import UUID4


class MessageRoleError(AppException):
    code = ErrorCode.MESSAGE_ROLE_ERROR

    def __init__(self, role: str):
        super().__init__(f"消息角色 {role} 不合法，必须为 system 或 agent")


class MemoryExistedError(AppException):
    code = ErrorCode.MEMORY_EXISTED_ERROR

    def __init__(self, memory_id: UUID4):
        super().__init__(f"已存在相似的记忆记录，记忆ID：{memory_id}")


class MemoryNotExistedError(AppException):
    code = ErrorCode.MEMORY_NOT_EXISTED_ERROR

    def __init__(self, memory_id: UUID4):
        super().__init__(f"记忆记录 {memory_id} 不存在")