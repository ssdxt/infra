from uuid import UUID

from schemas.error import ErrorCode
from exceptions.base_errors import AppException


class EntExistedError(AppException):
    """企业已存在"""
    code: int = ErrorCode.ENT_EXISTED_ERROR

    def __init__(
            self,
            ent_name: str,
    ):
        super().__init__(message=f"企业「{ent_name}」已存在，请重新输入。")


class EntNotExistedError(AppException):
    """企业不存在"""
    code: int = ErrorCode.ENT_NOT_EXISTED_ERROR

    def __init__(
            self,
            ent_id: UUID,
    ):
        super().__init__(message=f"ID为「{ent_id}」的企业不存在")
