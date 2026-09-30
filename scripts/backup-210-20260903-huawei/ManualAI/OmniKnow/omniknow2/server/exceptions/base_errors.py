from schemas.error import ErrorCode


class AppException(Exception):
    """所有自定义业务异常的基类"""
    code: int
    message: str

    def __init__(self, message: str | None = None):
        self.code = self.code
        self.message = message or self.message
        super().__init__(self.message)


class UnknowError(AppException):
    """未知异常"""
    code = ErrorCode.UNKNOW_ERROR
    message = "未知异常"


class UuidInvalidError(AppException):
    """UUID格式错误"""
    code = ErrorCode.UUID_INVALID_ERROR

    def __init__(self, params: str):
        message = f"{params} 不是一个有效的UUID"
        super().__init__(message=message)


