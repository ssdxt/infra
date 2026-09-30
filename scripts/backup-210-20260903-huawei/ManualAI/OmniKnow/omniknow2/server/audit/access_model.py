from sqlalchemy import Column, Integer, String, Text, Uuid

from db.models.public import BaseModel


class AccessLog(BaseModel):
    """HTTP 访问日志（粗粒度，所有认证请求自动留痕）"""
    __tablename__ = 'access_logs'

    user_id = Column(Uuid, nullable=True, index=True, comment="请求用户ID")
    space_id = Column(Uuid, nullable=True, index=True, comment="请求路径中的 space_id")
    method = Column(String(10), nullable=False, comment="HTTP 方法")
    path = Column(String(255), nullable=False, index=True, comment="请求路径")
    status_code = Column(Integer, nullable=True, comment="响应状态码")
    duration_ms = Column(Integer, nullable=True, comment="处理耗时(毫秒)")
    ip_address = Column(String(45), nullable=True, comment="客户端 IP")
    user_agent = Column(Text, nullable=True, comment="User Agent")
