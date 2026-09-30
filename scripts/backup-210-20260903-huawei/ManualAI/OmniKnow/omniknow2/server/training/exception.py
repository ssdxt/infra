from exceptions.base_errors import AppException

from uuid import UUID

from schemas.error import ErrorCode


class CourseNotFoundError(AppException):
    code = ErrorCode.COURSE_NOT_FOUND_ERROR
    def __init__(self, course_id: UUID):
        super().__init__(f"课程 {course_id} 未找到")


class QusetionsNotExisted(AppException):
    code = ErrorCode.QUESTIONS_NOT_EXISTED_ERROR
    def __init__(self, messages: str = "题目不存在"):
        super().__init__(messages)


class PaperNotFoundError(AppException):
    code = ErrorCode.PAPER_NOT_FOUND_ERROR
    def __init__(self, paper_id: UUID):
        super().__init__(f"试卷 {paper_id} 未找到或已失效")