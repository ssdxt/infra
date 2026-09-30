import sys
sys.path.append("./")

from sqlalchemy import Column, Integer, String, DateTime, JSON, func
from server.db.repository.user_info_repository import get_user
from server.db.repository.doc_template_repository import doc_template_detail
from server.db.repository.knowledge_base_repository import kb_detail
from server.db.base import Base
from datetime import datetime, timezone, timedelta
from server.db.repository.knowledge_base_repository import _kb_name_list

def beijing_time():
    """
    返回当前北京时间
    """
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)

class DocHistoryModel(Base):
    """
    知识库模型
    """
    __tablename__ = 'doc_history'
    id = Column(Integer, primary_key=True, autoincrement=True,comment='主键')
    name = Column(String(256), comment='名称')
    desc = Column(String(2048), comment='描述')
    dep_id = Column(Integer, comment='部门id')
    content = Column(String(40960), comment='文档内容')
    file_name = Column(String(256), comment='文档名称')
    file_path = Column(String(2048), comment='文档路径')
    doc_template_id = Column(Integer, comment='文档模版id')
    user_email = Column(String(256), comment='文档生成的email')
    kb_ids = Column(JSON, default={}, comment='知识库名称，多个')
    keywords = Column(JSON, default={}, comment='名称和型号信息')
    create_time = Column(DateTime(timezone=True), default=beijing_time, comment='文档生成时间')
    doc_ref = Column(JSON, default={}, comment='参考文档')
    info = Column(JSON, default={}, comment='其他信息')
    

    def __repr__(self):
        return f"<DocHistoryModel(id='{self.id}', name='{self.name}', desc='{self.desc}', dep_id='{self.dep_id}', file_name='{self.file_name},file_path='{self.file_path} ,doc_template_id='{self.doc_template_id} ,create_user_email='{self.user_email} ,create_time='{self.create_time} ,doc_ref='{self.doc_ref},info='{self.info}')>"

    def to_out_dict(self,is_detail=True):
        from http_api.utils import convert_generate_file_to_download_url
        url_path = convert_generate_file_to_download_url(self.file_path,self.file_name)

        username = None
        if is_detail:
            user_db = get_user(self.user_email,is_detail=False)
            if user_db["code"]== 0:
                username = user_db["data"]["username"]
         

        doc_template_name = None
        if is_detail:
            _db = doc_template_detail(self.doc_template_id,is_detail=False)
            if _db["code"]== 0:
                doc_template_name = _db["data"]["name"]

        kbs = []
        if self.kb_ids:
            kbs = _kb_name_list(ids=self.kb_ids)["data"]
        # if is_detail:
        # for kb_id in self.kb_ids:
        #     kb_name = kb_detail(id=kb_id,is_detail=False)["data"].get("name")
        #     kbs.append({"id":kb_id,"name":kb_name})
        
        return {
            "id":self.id,
                "name":self.name,
                "desc":self.desc,
                "dep_id":self.dep_id,
                "content":self.content,
                "file_name":self.file_name,
                "file_path":url_path,
                "doc_template_id":self.doc_template_id,
                "doc_template_name":doc_template_name,
                "user_email":self.user_email,
                "username":username,
                "kb_ids":self.kb_ids,
                "kbs":kbs,
                "keywords":self.keywords,
                "create_time":self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                "doc_ref":self.doc_ref,
                "info":self.info
                }
