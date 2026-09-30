import sys
sys.path.append("./")

from sqlalchemy import Column, Integer, String, DateTime, JSON, func,Boolean

from server.db.base import Base
from datetime import datetime

class AppTypeModel(Base):
    """
    知识库模型
    """
    __tablename__ = 'app_type'
    id = Column(Integer, primary_key=True, autoincrement=True,comment='主键')
    name = Column(String(256), comment='')
    desc = Column(String(2048), comment='')
    f_config = Column(JSON, default={})
    b_config = Column(JSON, default={})

    def __repr__(self):
        return f"<AppTypeModel(id='{self.id}', type_id='{self.type_id}',name='{self.name} desc='{self.desc}', f_config='{self.f_config}',b_config='{self.b_config}')>"

    def to_out_dict(self):
        return {"id":self.id,
                "name":self.name,
                "desc":self.desc,
                "f_config":self.f_config,
                "b_config":self.b_config 
                } 


# if __name__ == "__main__":
#     xx = func.now()
#     print(xx)
#     __pw_salt ="lb@cc"
#     import uuid
#     import base64
#     userid = uuid.uuid4()
    
#     print(userid)
#     password ="abc"
#     password = __pw_salt+password
#     password = base64.b64encode(password.encode("utf-8"))

#     print(password)