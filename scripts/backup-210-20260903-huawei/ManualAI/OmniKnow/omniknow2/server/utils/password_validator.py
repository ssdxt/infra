import re

from exceptions.base_errors import AppException
from schemas.error import ErrorCode


class PasswordTooWeakError(AppException):
    code = ErrorCode.PASSWORD_TOO_WEAK_ERROR
    message = "密码强度不足"


def validate_password_strength(password: str) -> None:
    """
    密码策略校验：
    - 最少 8 个字符
    - 至少包含一个大写字母
    - 至少包含一个小写字母
    - 至少包含一个数字
    """
    errors = []
    if len(password) < 8:
        errors.append("密码长度至少为8个字符")
    # if not re.search(r'[A-Z]', password):
    #     errors.append("密码需包含至少一个大写字母")
    if not re.search(r'[A-z]', password):
        errors.append("密码需包含至少一个字母")
    if not re.search(r'[0-9]', password):
        errors.append("密码需包含至少一个数字")
    if errors:
        raise PasswordTooWeakError(message="；".join(errors))
