from exceptions.base_errors import AppException
from schemas.error import ErrorCode


class UserRegisterError(AppException):
    """用户注册失败"""
    code = ErrorCode.USER_REGISTER_ERROR
    message = "用户注册失败"


class UserBannedError(AppException):
    """用户被封禁"""
    code: int = ErrorCode.USER_BANNED_ERROR
    message: str = "该用户已被禁用，请联系管理员"


class UserLoginBannedError(AppException):
    """用户登录被封禁"""
    code: int = ErrorCode.USER_LOGIN_BANNED_ERROR

    def __init__(self, seconds: int):
        message = f"该用户因密码错误次数太多已被禁用，还剩余 {seconds} 秒"
        super().__init__(message=message)


class UserExistedError(AppException):
    """用户已存在"""
    code = ErrorCode.USER_NOT_EXISTED_ERROR

    def __init__(self, account):
        message = f"账户「{account}」已存在，请修改后重试"
        super().__init__(message=message)


class UserNotExistedError(AppException):
    """用户不存在"""
    code: int = ErrorCode.USER_NOT_EXISTED_ERROR,

    def __init__(self, account):
        message = f"账户「{account}」不存在，请检查后重试"
        super().__init__(message=message)


class LoginError(AppException):
    """登录失败"""
    code: int = ErrorCode.LOGIN_ERROR
    message: str = "账号名或登录密码不正确!请检查后重试。"
