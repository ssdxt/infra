from uuid import UUID

from exceptions.base_errors import AppException
from schemas.error import ErrorCode


class ImageNotExistedError(AppException):
    code = ErrorCode.RESOURCE_NOT_EXISTED_ERROR

    def __init__(self, image_id: UUID):
        super().__init__(message=f"图片ID: {image_id} 不存在或已失效")
