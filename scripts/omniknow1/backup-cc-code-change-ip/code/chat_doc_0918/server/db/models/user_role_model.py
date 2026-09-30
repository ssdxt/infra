import sys
sys.path.append("./")

from sqlalchemy import Column, Integer, String, DateTime, JSON, func

from server.db.base import Base
from datetime import datetime

class UserRoleModel(Base):
    """
    知识库模型
    """
    __tablename__ = 'role_info'
    id = Column(Integer, primary_key=True, autoincrement=True,comment='主键')
    name = Column(String(128), comment='用户email')
    role = Column(String(128), comment='用户密码')
    info = Column(JSON, default={}, comment='权限其他信息')

    def __repr__(self):
        return f"<UserRoleoModel(id='{self.id}', name='{self.name}',role='{self.id}  info='{self.info}')>"

    def to_out_dict(self):
        return {"name":self.name,"role":self.id,"info":self.info} 