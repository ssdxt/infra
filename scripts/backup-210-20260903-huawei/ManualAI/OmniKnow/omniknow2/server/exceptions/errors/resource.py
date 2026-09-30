from uuid import UUID

from schemas.error import ErrorCode
from exceptions.base_errors import AppException


class ResourcePermissionError(AppException):
    """资源权限不足"""
    code: int = ErrorCode.RESOURCE_PERMISSION_ERROR
    message: str = "资源权限不足，操作失败"

    def __init__(self, resource_type: str = None, resource_id: UUID = None, action: str = None):
        if resource_type and resource_id and action:
            message = f"没有对{resource_type}（ID: {resource_id}）执行{action}操作的权限"
            super().__init__(message=message)
        else:
            super().__init__()

class ResourceNotExistedError(AppException):
    """资源不存在"""
    code: int = ErrorCode.RESOURCE_NOT_EXISTED_ERROR
    message: str = "访问的资源不存在，请检查后重试"


class ResourceNotChunks(AppException):
    """资源的chunks不存在"""
    code: int = ErrorCode.RESOURCE_NOT_CHUNKS_ERROR
    message: str = "访问的资源不存在分片"

class SpaceNotExistedError(AppException):
    """空间不存在"""
    code: int = ErrorCode.SPACE_NOT_EXISTED_ERROR,
    message: str = "访问的空间不存在，请检查后重试"


class SpaceExistedError(AppException):
    """同名空间已存在"""
    code: int = ErrorCode.SPACE_EXISTED_ERROR
    def __init__(self, space_name: str = None):
        if space_name is None:
            message = "指定空间空间已存在"
        else:
            message = f"空间「{space_name}」已存在"
        super().__init__(message=message)


class SpaceAccessError(AppException):
    """空间访问权限不足"""
    code: int = ErrorCode.SPACE_ACCESS_ERROR
    message: str = "您没有操作该空间的权限，请联系空间管理员"


class SpaceMemberNotFoundError(AppException):
    """空间成员不存在"""
    code: int = ErrorCode.SPACE_MEMBER_NOT_FOUND_ERROR
    message: str = "指定成员不在该空间中"


class SpaceOwnerCannotBeRemovedError(AppException):
    """不可移除空间所有者"""
    code: int = ErrorCode.SPACE_OWNER_CANNOT_BE_REMOVED_ERROR
    message: str = "不可移除空间所有者"


class KBaseExistedError(AppException):
    """知识库已存在"""
    code: int = ErrorCode.KBASE_EXISTED_ERROR

    def __init__(
            self,
            kbase_name: str,
    ):
        super().__init__(message=f"知识库「{kbase_name}」已存在，请重新输入。")


class CollectionNameExistedError(AppException):
    """向量库名称已存在"""
    code: int = ErrorCode.KBASE_EXISTED_ERROR

    def __init__(
            self,
            collection_name: str,
    ):
        super().__init__(message=f"向量库「{collection_name}」已存在，请重新输入。")


class KBaseNotExistedError(AppException):
    """知识库不存在"""
    code: int = ErrorCode.KBASE_NOT_EXISTED_ERROR

    def __init__(
            self,
            kbase_id: UUID,
    ):
        super().__init__(message=f"ID为「{kbase_id}」的知识库不存在")


class KBaseAccessError(AppException):
    code: int = ErrorCode.KBASE_ACCESS_ERROR
    message: str = "您没有操作该知识库的权限，请联系知识库管理员"


class FileUploadError(AppException):
    """文件上传失败"""
    code: int = ErrorCode.FILE_UPLOAD_ERROR
    def __init__(self, message: str = "文件上传失败"):
        super().__init__(message=message)

class FileDeleteError(AppException):
    """文件删除失败"""
    code: int = ErrorCode.FILE_DELETE_ERROR
    def __init__(self, message: str = "文件删除失败"):
        super().__init__(message=message)


class DocNotExistedError(AppException):
    """文档不存在"""
    code: int = ErrorCode.DOC_NOT_EXISTED_ERROR

    def __init__(self, doc_id: UUID):
        super().__init__(message=f"文档ID: {doc_id} 不存在或已过期")


class DocNotParsedError(AppException):
    """文档未解析成功"""
    code: int = ErrorCode.DOC_NOT_PARSED_ERROR

    def __init__(self, doc_id: UUID):
        super().__init__(message=f"文档ID: {doc_id} 未解析成功或解析失败，无法获取文档块信息，请稍后重试")


class ChunkNotExistedError(AppException):
    """文档块不存在"""
    code: int = ErrorCode.CHUNK_NOT_EXISTED_ERROR

    def __init__(self, chunk_id: UUID):
        super().__init__(message=f"文档块ID: {chunk_id} 不存在或已过期")


class ChunkIndexNotExistedError(AppException):
    """文档块索引不存在"""
    code: int = ErrorCode.CHUNK_INDEX_NOT_EXISTED_ERROR

    def __init__(self, chunk_index: int):
        super().__init__(message=f"文档块索引: {chunk_index} 不存在或已过期")


class FileTypeNotSupportedError(AppException):
    """文件类型不支持"""
    code: int = ErrorCode.FILE_TYPE_NOT_SUPPORTED_ERROR

    def __init__(self, file_type: str):
        super().__init__(message=f"文件类型 {file_type} 不支持上传，请检查后重试。")


class ImageUploadError(AppException):
    """图片上传失败"""
    code: int = ErrorCode.IMAGE_UPLOAD_ERROR
    message: str = "图片上传失败，存储服务器连接失败，请检查配置后重试"


class MessageNotExistedError(AppException):
    """消息不存在"""
    code: int = ErrorCode.MESSAGE_NOT_EXISTED_ERROR

    def __init__(self, message_id: str):
        super().__init__(message=f"消息ID {message_id} 不存在或已过期。")


class ConversationNotExistedError(AppException):
    """会话不存在"""
    code: int = ErrorCode.CONVERSATION_NOT_EXISTED_ERROR

    def __init__(self, conversation_id: UUID):
        super().__init__(message=f"会话ID: {conversation_id} 不存在或已过期")