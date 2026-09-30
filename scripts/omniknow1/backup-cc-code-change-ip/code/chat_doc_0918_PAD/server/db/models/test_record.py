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
                              
class TestRecord(Base):
    """
    培训建议记录
    """
    __tablename__ = 'test_record'
    id = Column(Integer, primary_key=True, autoincrement=True,comment='主键')
    user_email = Column(String(256), default={},comment='培训用户')
    suggestion = Column(String(2048), comment='培训建议')
    reference = Column(String(2048), comment='参考资料')
    create_time = Column(DateTime(timezone=True), default=beijing_time, comment='创建时间')

    def __repr__(self):
        return f"<TestCase(id='{self.id}', user_email='{self.user_email}',suggestion='{self.suggestion}', reference='{self.reference}', create_time='{self.create_time}')>"

    def to_out_dict(self):
        return {"id":self.id,
                "user_email":self.user_email,
                "suggestion":self.suggestion,
                "reference":self.reference,
                "create_time":self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",   
                } 
