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

class TestHistory(Base):
    """
    试题做题记录
    """
    __tablename__ = 'test_history'
    id = Column(Integer, primary_key=True, autoincrement=True,comment='主键')
    test_case_id = Column(Integer, comment='测试题id')
    result = Column(String(2048), comment='测试结果,txt')
    score = Column(Integer, default='', comment='测试结果分数')
    consume_time = Column(Integer, default='', comment='耗时')
    create_time = Column(DateTime(timezone=True), default=beijing_time, comment='测试时间')
    user_email = Column(String(256), default={},comment='测试人员')
    eval_id = Column(Integer,comment='考试记录id')
    eval_index = Column(Integer,comment='试题的序列号')

    def __repr__(self):
        return f"<TestHistory(id='{self.id}', test_case_id='{self.test_case_id}',result='{self.result} score='{self.score}', consume_time='{self.consume_time}',create_time='{self.create_time},user_email='{self.user_email},eval_id='{self.eval_id},eval_index='{self.eval_index})>"

    def to_out_dict(self,is_detail=True):
        username = ""
        test_case = {}
        if is_detail:
            if self.user_email:
                from server.db.repository.user_info_repository import get_user
                username = get_user(email=self.user_email,is_detail=False)["data"].get("username")
            from server.db.repository.test_case_repository import test_case_detail
            test_case = test_case_detail(id=self.test_case_id,is_detail=False)["data"]
                
        return {"id":self.id,
                "test_case_id":self.test_case_id,
                "test_case":test_case,
                "result":self.result,
                "score":self.score,
                "consume_time":self.consume_time,
                "create_time":self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
                "user_email":self.user_email,
                "username":username, 
                "eval_id":self.eval_id,
                "eval_index":self.eval_index
                } 
