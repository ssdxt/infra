import sys
sys.path.append("./")

from sqlalchemy import Column, Integer, String, DateTime, JSON, func,Boolean

from server.db.base import Base
from datetime import datetime, timezone, timedelta
from server.db.repository.app_type_repository import app_type_detail

from server.db.repository.department_repository import department_detail
import os 
from urllib.parse import urlencode

def beijing_time():
    """
    返回当前北京时间
    """
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)

class Course(Base):
    """
    课程
    """
    __tablename__ = 'course'
    id = Column(Integer, primary_key=True, autoincrement=True,comment='主键')
    name = Column(String(256), comment='名称')
    desc = Column(String(2048), comment='课程描述')
    # job_title = Column(String(256), default='', comment='岗位')
    job_title = Column(JSON, default=[], comment='岗位列表')
    kb_id= Column(Integer, default=0, comment='知识库id')
    file_name = Column(String(256), default='', comment='课程文件名')
    create_time = Column(DateTime(timezone=True), default=beijing_time, comment='创建时间')
    user_email = Column(String(256), default='',comment='创建者')
    abstract = Column(String(2048), default="",comment='目录')
    activate = Column(Boolean, default=True,comment='状态')
    dep_id = Column(Integer, default=-1,comment='部门id')
    exam_test_case = Column(JSON, default={}, comment='真题题目信息')
    exam_paper_status = Column(String(10), default='未生成', comment='真题生成状态')

    def __repr__(self):
        return f"<Course(id='{self.id}', dep_id='{self.dep_id}',name='{self.name} desc='{self.desc}', create_time='{self.create_time}', exam_test_case='{self.exam_test_case}', exam_paper_status='{self.exam_paper_status}')>"

    def to_out_dict(self,is_detail=False):
        course_kb_name = ""
        username = ""
        sample_test_case=None
        _doc_url =""
        qa_status = "未生成"
        qa_count = 0
        kb_name = ""
        
        from server.db.repository.test_case_repository import test_case_list
        ref_test_case_count = test_case_list(course_id=self.id,test_case_type="参考试题")["data"].get("count",0)
        if ref_test_case_count > 0:
            ref_test_case_status = "已添加"
        else:
            ref_test_case_status = "未添加" 

        if self.kb_id:
            from server.db.repository.knowledge_base_repository import kb_detail
            kb_name = kb_detail(id=self.kb_id,is_detail=False)["data"].get("kb_name")
            from server.db.repository.knowledge_file_repository import get_file_detail
            file_detail = get_file_detail(kb_name=kb_name, file_name=self.file_name)
            if file_detail:
                qa_status = file_detail.get("qa_status", "未生成")
                qa_count = file_detail.get("qa_count", 0)
                    
        if is_detail:
            course_kb_name = kb_name
            
            if self.user_email:
                from server.db.repository.user_info_repository import get_user
                username = get_user(email=self.user_email,is_detail=False)["data"].get("username")

            # 获取当前课程的所有题库          
            sample_test_case = test_case_list(course_id=self.id,test_case_type="参考试题")["data"].get("test_cases",[])
            file_name = str(self.file_name)

            if file_name.lower().endswith(('.docx', '.doc', '.ppt', '.pptx')):
                file_name = os.path.splitext(file_name)[0] + '.pdf'

            source = "knowledge_base/"+str(kb_name)+"/content/"+str(file_name)
            _doc_filename=str(os.path.basename(source))
            _doc_url_request_parameters = urlencode({"knowledge_base_name": kb_name, "file_name":_doc_filename})
            _doc_url = f"knowledge_base/download_doc?" + _doc_url_request_parameters
        
        cover_image_dir = "course_img"
        cover_image_filename = f"{self.dep_id}_{self.name}.jpg"
        cover_image_path = os.path.join(cover_image_dir, cover_image_filename)
        _cover_image_url_request_parameters = urlencode({"filepath": cover_image_path, "filename": cover_image_filename})
        _cover_image_url = f"knowledge_base/download_img?" + _cover_image_url_request_parameters
        
        return {"id":self.id,
                "name":self.name,
                "desc":self.desc,
                "job_title":self.job_title,
                "kb_id":self.kb_id,
                "kb_name":course_kb_name,
                "file_name":self.file_name,
                "file_url":_doc_url,
                "create_time":self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
                "user_email":self.user_email,
                "username":username,
                "abstract":self.abstract,
                "activate":self.activate, 
                "dep_id":self.dep_id,
                "sample_test_case":sample_test_case,
                "ref_test_case_status":ref_test_case_status,
                "ref_test_case_count":ref_test_case_count,
                "gen_qa_status":qa_status,
                "gen_qa_count":qa_count,
                "exam_test_case":self.exam_test_case,
                "exam_paper_status":self.exam_paper_status,
                "_cover_image_url":_cover_image_url
                } 
