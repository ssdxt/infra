from typing import Any, Literal

from pydantic import BaseModel, Field, UUID7, UUID4


class MessageRecordSchema(BaseModel):
    message_id: UUID7 | None = Field(None, description="消息ID")
    content: str = Field(..., description="消息内容")
    text: str | None = Field(..., description="消息文本内容")
    role: Literal["user", "agent"] = Field(..., description="消息角色")
    metadata: dict[str, Any] | None = Field(None, description="消息元数据")


class ConversationCreateSchema(BaseModel):
    kbase_ids: list[UUID4] = Field(..., description="会话关联的知识库ID列表")


class ConversationTitleUpdateSchema(BaseModel):
    title: str = Field(..., description="新会话标题")
