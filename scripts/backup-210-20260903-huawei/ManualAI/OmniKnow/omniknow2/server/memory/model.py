from uuid import uuid4

from sqlalchemy import (
    BigInteger, String, DateTime, UniqueConstraint, Index, Uuid, Column, Text, JSON, Integer
)
from sqlalchemy.sql import func

from db.models.public import BaseModel


class Memory(BaseModel):
    __tablename__ = "memory"

    space_id = Column(Uuid, nullable=False, comment="空间ID")
    kbase_id = Column(JSON, nullable=False, comment="知识库ID")
    conversation_id = Column(Uuid, nullable=False, comment="对话ID")
    message_id = Column(Uuid, nullable=False, comment="消息ID")
    user_id = Column(Uuid, nullable=False, comment="用户ID")
    messages = Column(JSON, nullable=False, comment="记忆内容")
    feedback = Column(Integer, nullable=True, comment="反馈好坏, -1:差评, 0:中立, 1:好评")
    comment = Column(Text, nullable=True, comment="评论内容")
