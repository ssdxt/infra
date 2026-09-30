from schemas.error import ErrorCode
from exceptions.base_errors import AppException


class TaskNotExisted(AppException):
    """任务不存在"""
    code: int = ErrorCode.TASK_NOT_EXISTED_ERROR

    def __init__(self, task_id: str):
        super().__init__(message=f"任务ID: {task_id} 不存在或已过期")


class TaskSubmissionError(AppException):
    """任务提交失败"""
    code: int = ErrorCode.TASK_SUBMISSION_ERROR

    def __init__(self, reason: str = None):
        message = f"任务提交失败: {reason}" if reason else "任务提交失败，出现未知原因错误"
        super().__init__(message=message)

class MilvusDeletionError(AppException):
    """Milvus 删除失败"""
    code: int = ErrorCode.MILVUS_DELETION_ERROR

    def __init__(self, reason: str = None):
        message = f"Milvus 删除失败: {reason}" if reason else "Milvus 删除失败，出现未知原因错误"
        super().__init__(message=message)