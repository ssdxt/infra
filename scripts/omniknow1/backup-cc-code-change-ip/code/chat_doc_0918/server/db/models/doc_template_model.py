import sys
sys.path.append("./")

from sqlalchemy import Column, Integer, String, DateTime, JSON, func


from server.db.base import Base
from datetime import datetime, timezone, timedelta

def beijing_time():
    """
    返回当前北京时间
    """
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)

class DocTemplateModel(Base):
    """
    知识库模型
    """
    __tablename__ = 'doc_template'
    id = Column(Integer, primary_key=True, autoincrement=True,comment='主键')
    name = Column(String(256), comment='名称')
    desc = Column(String(2048), comment='描述信息')
    role = Column(String(256), comment='角色')
    fromat_req = Column(String(2048), comment='材料要求')
    user_email= Column(String(128), comment='用户email', default=None)
    create_time = Column(DateTime(timezone=True), default=beijing_time, comment='创建时间')
    count = Column(Integer, default=0, comment='使用数量')
    generate_info = Column(JSON, default={}, comment='权限其他信息')
    info = Column(JSON, default={}, comment='权限其他信息')
    dep_id = Column(Integer,comment='部门Id')

    def __repr__(self):
        return f"<DocTemplateModel(id='{self.id}', name='{self.name}',desc='{self.desc},role='{self.role}',fromat_req='{self.fromat_req}',user_email='{self.user_email},create_time='{self.create_time},count='{self.count} ,generate_info='{self.generate_info},info='{self.info},dep_id='{self.dep_id}')>"

    def to_out_dict(self,is_detail=True):
        
        return {"id":self.id,
                "name":self.name,
                "desc":self.desc,
                "role": self.role,
                "fromat_req": self.fromat_req,
                "user_email":self.user_email,
                "create_time":self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                "count":self.count,
                "generate_info":self.generate_info,
                "info":self.info,
                "dep_id":self.dep_id
                } 
