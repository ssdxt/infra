from sqlalchemy import Column, String, Text, Uuid, JSON, Index

from db.models.public import BaseModel


class ActivityLog(BaseModel):
    """用户操作审计日志（通用）"""
    __tablename__ = 'user_activity_logs'

    space_id = Column(Uuid, nullable=True, index=True, comment="所属空间ID")
    user_id = Column(Uuid, nullable=True, comment="操作用户ID")
    action = Column(String(50), nullable=False, comment="操作类型")
    target_type = Column(String(50), nullable=True, comment="目标类型：user/space/member")
    target_id = Column(Uuid, nullable=True, comment="目标ID")
    detail = Column(JSON, nullable=True, comment="操作详情")
    ip_address = Column(String(45), nullable=True, comment="IP地址")
    user_agent = Column(Text, nullable=True, comment="User Agent")
