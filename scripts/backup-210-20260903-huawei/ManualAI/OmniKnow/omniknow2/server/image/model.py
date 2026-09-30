from db.models.public import BaseModel

from sqlalchemy  import Column, Uuid, Text, Integer


class Image(BaseModel):
    __tablename__ = 'images'

    space_id = Column(Uuid, nullable=False, comment="空间ID")
    path = Column(Text, nullable=False, comment="图片路径")
    status = Column(Integer, nullable=False, default=1, comment="图片状态，1-有效，0-无效")