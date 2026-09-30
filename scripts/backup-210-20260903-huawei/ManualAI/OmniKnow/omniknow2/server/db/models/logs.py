from db.models.public import BaseModel

from sqlalchemy import Column, Integer, Text, Uuid


class UploadEvent(BaseModel):
    __tablename__ = 'image_upload_log'

    space_id = Column(Uuid, nullable=False, comment="空间ID")
    user_id = Column(Uuid, nullable=False, comment="用户ID")
    filename= Column(Text, nullable=False, comment="文件名")
    resource_type = Column(Text, comment="文件类型（MIME类型）")
    oss_path = Column(Text, nullable=False, comment="OSS存储路径")
    signed_url = Column(Text, nullable=False, comment="签发URL")
    expiry_time = Column(Integer, comment="图片过期时间（秒）")
    status = Column(Integer, nullable=False, default=0, comment="上传状态：1-上传成功，2-上传失败")
    meta = Column(Integer, comment="文件元数据")

