from sqlalchemy import Column, Integer, String, DateTime, func,JSON

from server.db.base import Base
from datetime import datetime, timezone, timedelta
from server.db.repository.user_info_repository import get_user

def beijing_time():
    """
    返回当前北京时间
    """
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)

class KnowledgeBaseModel(Base):
    """
    知识库模型
    """
    __tablename__ = 'knowledge_base'
    id = Column(Integer, primary_key=True, autoincrement=True, comment='知识库ID')
    kb_name = Column(String(50), comment='知识库名称')
    kb_type = Column(String(50), comment='知识库类型')
    kb_info = Column(String(2048), comment='知识库简介')
    file_count = Column(Integer, default=0, comment='文件数量')
    create_time = Column(DateTime(timezone=True), default=beijing_time, comment='创建时间')
    create_user_email= Column(String(256), comment='' )
    dep_id= Column(Integer, default=0, comment='部门id')
    activate = Column(String(10), comment='知识库状态')
    embedding_name = Column(String(50), comment='embedding模型名称')

    def __repr__(self):
        return f"<KnowledgeBase(id='{self.id}', kb_name='{self.kb_name}', kb_type='{self.kb_type}',kb_info='{self.kb_info}' , file_count='{self.file_count}', create_time='{self.create_time}', create_user_email='{self.create_user_email}', dep_id='{self.dep_id}', activate='{self.activate}', embedding_name='{self.embedding_name}')>"

    def to_out_dict(self,is_detail=True):
        
        create_username =""
        if is_detail:
            if self.create_user_email:
                user_db = get_user(self.create_user_email,is_detail=False)
                create_username = user_db["data"].get("username")
            
        from server.db.repository.department_repository import department_detail
        dep_name =""
        if is_detail:
            if self.dep_id:
                dep = department_detail(id=self.dep_id,is_detail=False)
                dep_name = dep["data"].get("name")

        result =  {
            "id":self.id,
                "kb_name":self.kb_name,
                "kb_type":self.kb_type,
                "kb_info":self.kb_info,
                "file_count":self.file_count,
                "create_time":self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
                "create_user_email":self.create_user_email,
                "create_username":create_username,
                "dep_id":self.dep_id,
                "dep_name":dep_name,
                "activate":self.activate,
                "embedding_name":self.embedding_name
                }
        return result