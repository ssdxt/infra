from exceptions.base_errors import AppException
from schemas.error import ErrorCode

from uuid import UUID

class ReportNotExistedError(AppException):
    code = ErrorCode.REPORT_NOT_EXISTED_ERROR

    def __init__(self, report_id: UUID):
        message = f"报告ID: {report_id}不存在"
        super().__init__(message=message)