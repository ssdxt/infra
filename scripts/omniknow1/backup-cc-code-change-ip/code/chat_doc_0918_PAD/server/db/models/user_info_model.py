import sys
sys.path.append("./")

from sqlalchemy import Column, Integer, String, DateTime, JSON, func,Boolean

from server.db.base import Base
from datetime import datetime, timezone, timedelta
from server.db.repository.department_repository import department_detail

def beijing_time():
    """
    返回当前北京时间
    """
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)

class UserInfoModel(Base):
    """
    知识库模型
    """
    __tablename__ = 'user_info'
    id = Column(Integer, primary_key=True, autoincrement=True,comment='主键')
    email = Column(String(256), comment='用户email')
    username = Column(String(256), comment='用户名')
    password = Column(String(256), comment='用户密码')
    create_time = Column(DateTime(timezone=True), default=beijing_time, comment='创建时间')
    activate= Column(Boolean, default=True, comment='用户状态')
    dep_id = Column(Integer, default=-1, comment='用户权限')
    role = Column(Integer, default=3, comment='用户权限') #1,2,3
    sex = Column(String(128), default=True, comment='用户性别')
    phone_num = Column(String(128), default=True, comment='手机号')
    job_title = Column(String(256), default=True, comment='岗位')
    app_ids = Column(JSON, default=[])
    
    # info = Column(JSON, default={})

    def __repr__(self):
        return f"<UserInfoModel(id='{self.id}', user_id='{self.email}',nickname='{self.nickname} role='{self.role}', create_time='{self.create_time}',sex='{self.sex},phone_num='{self.phone_num},job_title='{self.job_title}, app_ids='{self.app_ids}, activate='{self.activate},info='{self.info},')>"

    def to_out_dict(self,is_detail=True):
        
        dep_name = ""
        if is_detail:
             dep_name = department_detail(id=self.dep_id,is_detail=False)["data"].get("name")
       
        apps =[]
        if is_detail:
            from server.db.repository.app_repository import _app_name_list
            if self.app_ids:
                apps = _app_name_list(ids=self.app_ids)["data"]
            
        return {"id":self.id,
                "email":self.email,
                "username":self.username,
                "create_time":self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
                "activate":self.activate,   
                "dep_id":self.dep_id,
                "dep_name":dep_name,
                "role":self.role,
                "sex":self.sex,
                "phone_num":self.phone_num,
                "job_title":self.job_title,
                "apps":apps,
                # "info":self.info 
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