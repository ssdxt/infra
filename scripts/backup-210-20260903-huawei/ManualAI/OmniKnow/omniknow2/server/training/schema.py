from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from uuid import UUID


class QusetionType(str, Enum):
    # "single_choice", "multiple_choice", "true_false", "short_answer"
    single_choice = "single_choice"
    multiple_choice = "multiple_choice"
    true_false = "true_false"
    short_answer = "short_answer"


class CreateCourseRequest(BaseModel):
    name: str = Field(..., min_length=1, description="课程名称")
    description: Optional[str] = Field(default=None, description="课程描述")
    kbase_id: UUID = Field(..., description="知识库ID")
    doc_id: UUID = Field(..., description="文档ID")
    question_number: int = Field(..., ge=0, description="考题总数")


class GeneratePaperRequest(BaseModel):
    title: str = Field(default="考试试卷", description="试卷标题")
    description: Optional[str] = Field(default=None, description="试卷描述")
    duration_minutes: Optional[int] = Field(default=None, gt=0, description="考试时长(分钟)")
    single_choice: Optional[int] = Field(default=None, gt=0, description="单选题数量")
    multiple_choice: Optional[int] = Field(default=None, gt=0, description="多选题数量")
    true_false: Optional[int] = Field(default=None, gt=0, description="判断题数量")
    short_answer: Optional[int] = Field(default=None, gt=0, description="简答题数量")
    question_ids: Optional[list[str]] = Field(default=None, description="指定题目ID列表")

    @property
    def type_counts(self) -> dict[str, int]:
        """返回各题型的请求数量（仅包含非 None 的题型）"""
        counts = {}
        if self.single_choice is not None:
            counts["single_choice"] = self.single_choice
        if self.multiple_choice is not None:
            counts["multiple_choice"] = self.multiple_choice
        if self.true_false is not None:
            counts["true_false"] = self.true_false
        if self.short_answer is not None:
            counts["short_answer"] = self.short_answer
        return counts


class AnswerItem(BaseModel):
    question_id: str = Field(..., description="题目ID")
    answer: str = Field(default="", description="答案")


class SubmitExamRequest(BaseModel):
    paper_id: UUID = Field(..., description="试卷ID")
    answers: list[AnswerItem] = Field(default_factory=list, description="答案列表")
