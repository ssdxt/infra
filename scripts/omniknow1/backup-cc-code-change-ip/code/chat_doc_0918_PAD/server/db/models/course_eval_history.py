import sys
sys.path.append("./")

from sqlalchemy import Column, Integer, String, DateTime, JSON, func,Boolean

from server.db.base import Base
from datetime import datetime, timezone, timedelta
from server.db.repository.app_type_repository import app_type_detail

from server.db.repository.department_repository import department_detail

def beijing_time():
    """
    返回当前北京时间
    """
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)

class EvalHistory(Base):
    """
    课程考核历史记录
    """
    __tablename__ = 'eval_history'
    id = Column(Integer, primary_key=True, autoincrement=True,comment='主键')
    user_email = Column(String(256), default={},comment='创建者')
    course_id = Column(Integer, comment='名称')
    create_time = Column(DateTime(timezone=True), default=beijing_time, comment='创建时间')
    score = Column(Integer, comment='分数')
    dep_id = Column(Integer, comment='部门id')
    eval_type = Column(String(10),comment='考核类型')

    def __repr__(self):
        return f"<EvalHistory(id='{self.id}', user_email='{self.user_email}',course_id='{self.course_id} create_time='{self.create_time}', score='{self.score}', dep_id='{self.dep_id}', eval_type='{self.eval_type}')>"

    def to_out_dict(self,is_detail=True):
        username = ""
        course_name =""
        kb_id = ""
        kb_name = ""
        if is_detail:
            if self.course_id:
                from server.db.repository.course_repository import course_detail
                course = course_detail(id=self.course_id,is_detail=False)
                course_name = course["data"].get("name")
                kb_id = course["data"].get("kb_id")
                kb_name = course["data"].get("kb_id")
            if self.user_email:
                from server.db.repository.user_info_repository import get_user
                username = get_user(email=self.user_email,is_detail=False)["data"].get("username")
                
        return {"id":self.id,
                "user_email":self.user_email,
                "username":username,
                "course_id":self.course_id,
                "kb_id":kb_id,
                "course_name":course_name,
                "create_time":self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
                "score":self.score,
                "dep_id":self.dep_id,
                "eval_type":self.eval_type,
                } 
