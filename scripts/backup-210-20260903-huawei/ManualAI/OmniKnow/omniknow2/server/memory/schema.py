from pydantic import BaseModel, Field, UUID7


class MemoryCreateSchema(BaseModel):
    message_id: UUID7 = Field(..., description="消息ID")
    feedback: int = Field(..., description="反馈好坏, -1:差评, 1:好评")
    comment: str | None = Field(None, description="评论内容")
