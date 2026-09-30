from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, JSON, func
from urllib.parse import urlencode
from server.db.base import Base
from datetime import datetime, timezone, timedelta

def beijing_time():
    """
    返回当前北京时间
    """
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)

class KnowledgeFileModel(Base):
    """
    知识文件模型
    """
    __tablename__ = 'knowledge_file'
    id = Column(Integer, primary_key=True, autoincrement=True, comment='知识文件ID')
    file_name = Column(String(255), comment='文件名')
    file_ext = Column(String(10), comment='文件扩展名')
    kb_name = Column(String(50), comment='所属知识库名称')
    #
    document_loader_name = Column(String(50), comment='文档加载器名称')
    text_splitter_name = Column(String(50), comment='文本分割器名称')
    file_version = Column(Integer, default=1, comment='文件版本')
    file_mtime = Column(Float, default=0.0, comment="文件修改时间")
    
    file_size = Column(Integer, default=0, comment="文件大小")
    #
    custom_docs = Column(Boolean, default=False, comment="是否自定义docs")
    
    docs_count = Column(Integer, default=0, comment="切分文档数量")
    create_time = Column(DateTime(timezone=True), default=beijing_time, comment='创建时间')

    qa_status = Column(String(10), default='未生成', comment='问答对生成状态')
    qa_count = Column(Integer, default=0, comment="问答对数量")
    parse_status = Column(String(10), default='未解析', comment='文档解析状态')
    file_parse_configs = Column(JSON, default={}, comment='文档解析配置信息')

    def __repr__(self):
        return f"<KnowledgeFile(id='{self.id}', file_name='{self.file_name}', file_ext='{self.file_ext}', kb_name='{self.kb_name}', document_loader_name='{self.document_loader_name}', text_splitter_name='{self.text_splitter_name}', file_version='{self.file_version}', create_time='{self.create_time}', qa_status='{self.qa_status}', qa_count='{self.qa_count}', parse_status='{self.parse_status}', file_parse_configs='{self.file_parse_configs}')>"
    
    def to_out_dict(self):
        from server.knowledge_base.utils import get_doc_thumbnail_path,get_kb_path
        from configs.kb_config import PROJECT_DIR
        import os

        # print("PROJECT_DIR",PROJECT_DIR)
        thumbnail_path = get_doc_thumbnail_path(knowledge_base_name=self.kb_name,doc_name=self.file_name)
        if not os.path.exists(thumbnail_path):
            thumbnail_path ="knowledge_base/0515/thumbnail/核电厂设计安全规定.jpg"
        else:
            thumbnail_path=thumbnail_path[len(PROJECT_DIR)+1:]
            
        # 
        
        parameters = urlencode({"filepath": thumbnail_path, "filename":thumbnail_path[thumbnail_path.rfind("/")+1:]})
        thumbnail_path = f"/knowledge_base/download_img?" + parameters
        # print("thumbnail_path",thumbnail_path)
        # 
        return {"file_name":self.file_name,
                "file_ext":self.file_ext,
                "file_version":self.file_version,
                "file_size":self.file_size,
                "create_time":self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                "block_count":self.docs_count,
                "thumbnail_path":thumbnail_path,
                "create_author":"",
                "qa_status": self.qa_status,
                "qa_count": self.qa_count,
                "parse_status": self.parse_status,
                "file_parse_configs":self.file_parse_configs 
                }


class FileDocModel(Base):
    """
    文件-向量库文档模型
    """
    __tablename__ = 'file_doc'
    id = Column(Integer, primary_key=True, autoincrement=True, comment='ID')
    kb_name = Column(String(50), comment='知识库名称')
    file_name = Column(String(255), comment='文件名称')
    doc_id = Column(String(50), comment="向量库文档ID")
    meta_data = Column(JSON, default={})
    page_content = Column(String(2048), comment='文本块内容')

    def __repr__(self):
        return f"<FileDoc(id='{self.id}', kb_name='{self.kb_name}', file_name='{self.file_name}', doc_id='{self.doc_id}', metadata='{self.meta_data}', page_content='{self.page_content}')>"

    def to_out_dict(self):
        return {"id":self.id,
                "kb_name":self.kb_name,
                "file_name":self.file_name,
                "doc_id":self.doc_id,
                "meta_data":self.meta_data,
                "page_content":self.page_content,
                } 
