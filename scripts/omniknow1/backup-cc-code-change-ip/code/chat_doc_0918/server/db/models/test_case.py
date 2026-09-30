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

class TestCase(Base):
    """
    试题
    """
    __tablename__ = 'test_case'
    id = Column(Integer, primary_key=True, autoincrement=True,comment='主键')
    question = Column(String(2048), comment='问题')
    answer = Column(String(2048), comment='问题答案')
    vs_id = Column(String(256), default='', comment='vs的id')
    create_time = Column(DateTime(timezone=True), default=beijing_time, comment='创建时间')
    user_email = Column(String(256), default={},comment='创建者')
    test_case_type = Column(String(256), comment='试题的种类')
    course_id = Column(Integer, default=-1,comment='课程id')
    question_type = Column(String(10), comment='题目类型')
    


    def __repr__(self):
        return f"<TestCase(id='{self.id}', question='{self.question}',answer='{self.answer} vs_id='{self.vs_id}', create_time='{self.create_time}',user_email='{self.user_email},test_case_type='{self.test_case_type}',course_id='{self.course_id}',question_type='{self.question_type}')>"

    def to_out_dict(self,is_detail=True):
        username = ""
        if is_detail:
            if self.user_email:
                from server.db.repository.user_info_repository import get_user
                username = get_user(email=self.user_email,is_detail=False)["data"].get("username")

        return {"id":self.id,
                "question":str(self.question),
                "answer":str(self.answer),
                "vs_id":self.vs_id,
                "create_time":self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
                "user_email":self.user_email,
                "username":username,
                "test_case_type":self.test_case_type, 
                "course_id":self.course_id,
                "question_type":self.question_type
                } 
