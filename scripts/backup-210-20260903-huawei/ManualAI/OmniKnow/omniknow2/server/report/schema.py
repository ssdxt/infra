from enum import Enum

from pydantic import BaseModel, Field


class ReportType(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    custom = "custom"


class ReportCreateSchema(BaseModel):
    title: str = Field(..., description="报告标题")
    type: ReportType = Field(..., description="报告类型")
    content: str = Field(..., description="报告内容")
    extra: dict | None = Field(None, description="额外信息")


class ReportUpdateSchema(BaseModel):
    title: str | None = Field(None, description="报告标题")
    content: str | None = Field(None, description="报告内容")
    extra: dict | None = Field(None, description="额外信息")