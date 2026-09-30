from db.models.public import BaseModel
from report.schema import ReportType

from sqlalchemy import Column, Integer, Text, Uuid, JSON, Enum


class Report(BaseModel):
    __tablename__ = 'reports'

    space_id = Column(Uuid, nullable=False, comment="空间ID")
    title = Column(Text, nullable=False, comment="报告标题")
    content = Column(Text, comment="报告内容")
    type = Column(Enum(ReportType), comment="报告类型")
    author_id = Column(Uuid, comment="作者用户ID")
    status = Column(Integer, nullable=False, default=1, comment="状态，1-有效，0-已删除")
    extra = Column(JSON, comment="额外信息")
