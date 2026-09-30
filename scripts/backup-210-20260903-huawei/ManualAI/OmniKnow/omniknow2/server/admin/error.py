from schemas.error import ErrorCode
from exceptions.base_errors import AppException


class ResourceGroupNotFoundError(AppException):
    code = ErrorCode.RESOURCE_GROUP_NOT_FOUND_ERROR
    message = "资源用户组不存在"


class ResourceGroupNameExistedError(AppException):
    code = ErrorCode.RESOURCE_GROUP_NAME_EXISTED_ERROR
    message = "同名资源用户组已存在"


class ResourceGroupMemberExistedError(AppException):
    code = ErrorCode.RESOURCE_GROUP_MEMBER_EXISTED_ERROR
    message = "用户已在该资源组中"


class RoleNotFoundError(AppException):
    code = ErrorCode.ROLE_NOT_FOUND_ERROR
    message = "角色不存在"


class RoleCodeExistedError(AppException):
    code = ErrorCode.ROLE_CODE_EXISTED_ERROR
    message = "角色编码已存在"


class BuiltinRoleProtectedError(AppException):
    code = ErrorCode.BUILTIN_ROLE_PROTECTED_ERROR
    message = "内置角色不可删除或修改编码"


class PermissionNotFoundError(AppException):
    code = ErrorCode.PERMISSION_NOT_FOUND_ERROR
    message = "权限不存在"


class PermissionCodeExistedError(AppException):
    code = ErrorCode.PERMISSION_CODE_EXISTED_ERROR
    message = "权限编码已存在"


class BuiltinPermissionProtectedError(AppException):
    code = ErrorCode.BUILTIN_PERMISSION_PROTECTED_ERROR
    message = "系统内置权限不可删除或修改编码"
