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

class AppModel(Base):
    """
    应用模型
    """
    __tablename__ = 'app'
    id = Column(Integer, primary_key=True, autoincrement=True,comment='应用id')
    type_id = Column(Integer, comment='应用类型')
    name = Column(String(256), comment='应用名称')
    desc = Column(String(2048), comment='应用描述')
    create_time = Column(DateTime(timezone=True), default=beijing_time, comment='创建时间')
    kb_ids= Column(JSON, default=0, comment='知识库')
    assistant_type = Column(String(256), default='', comment='助手类型')
    hi = Column(String(1024), default='', comment='助手回复词')
    questions = Column(JSON, default={}, comment='问题')
    dep_id = Column(Integer, comment='部门id')
    update_time = Column(DateTime(timezone=True), default=beijing_time, comment='更新时间')
    llm_model = Column(String(1024), default='')
    digital_human = Column(String(256), default='', comment='数字人')
    url = Column(String(1024), default='')
    activate = Column(Boolean, default=True)
    info = Column(JSON, default={})
    job_titles = Column(JSON, default=[], comment='应用配置岗位列表')

    def __repr__(self):
        return f"<AppModel(id='{self.id}', type_id='{self.type_id}',name='{self.name}', desc='{self.desc}', create_time='{self.create_time}',kb_ids='{self.kb_ids}',assistant_type='{self.assistant_type}',hi='{self.hi}',questions='{self.questions}', dep_id='{self.dep_id}', update_time='{self.update_time}',llm_model='{self.llm_model}',digital_human='{self.digital_human}',url='{self.url}',activate='{self.activate}',info='{self.info}',job_titles='{self.job_titles}')>"

    def to_out_dict(self,is_detail=True):

        kb_counts = len(self.kb_ids)

        app_type_name =""
        if is_detail:
            if self.type_id:
                app_type = app_type_detail(id=self.type_id)
                if app_type:
                    app_type_name = app_type["data"].get("name")
        
        from server.db.repository.knowledge_base_repository import _kb_name_list
        kbs = []
        if is_detail:
            if self.kb_ids:
                kbs = _kb_name_list(ids=self.kb_ids)["data"]

        dep_name =""
        if is_detail:
            if self.dep_id:
                dep = department_detail(id=self.dep_id,is_detail=False)
                dep_name = dep["data"].get("name")
                
        return {"id":self.id,
                # "type_id":
                # "app_type_name":
                "type_id":self.type_id,
                "type_name":app_type_name,
                "name":self.name,
                "desc":self.desc,
                "create_time":self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
                "kb_ids":self.kb_ids,
                "kbs":kbs,
                "kb_counts":kb_counts,
                # "kb_name":kb_name,
                "assistant_type":self.assistant_type,
                "hi":self.hi,
                "questions":self.questions,                
                "dep_id":self.dep_id,
                "dep_name":dep_name,
                "job_titles":self.job_titles,
                "update_time":self.update_time.strftime("%Y-%m-%d %H:%M:%S") if self.update_time else "",
                "llm_model":self.llm_model,
                "digital_human":self.digital_human,
                "url":self.url,
                "activate":self.activate,
                "info":self.info
                } 
