# from server.db.models.user_info_model import UserInfoModel
from server.db.models.test_case import TestCase
from server.db.session import with_session
from server.db.models.knowledge_file_model import KnowledgeFileModel,FileDocModel
from server.db.models.knowledge_base_model import KnowledgeBaseModel

from server.db.models.app_type_model import AppTypeModel
from server.db.models.app_model import AppModel
from server.db.models.doc_template_model import DocTemplateModel
from server.db.models.doc_history_model import DocHistoryModel
from server.db.models.course import Course
from server.db.models.course_eval_history import EvalHistory
from server.db.models.test_history import TestHistory
from server.db.models.department_model import DepartmentModel
from server.db.models.user_info_model import UserInfoModel
from server.db.models.chat_feedback import ChatFeedbackModel
from server.db.repository.doc_template_repository import update_doc_template_counts

from typing import Dict
from sqlalchemy import cast
from datetime import datetime


@with_session
def statistics_knowledge(
            session,
            dep_id:int
                      ) -> Dict:
    
    kbs = session.query(KnowledgeBaseModel.id,KnowledgeBaseModel.kb_name,KnowledgeBaseModel.file_count)
    kbs = kbs.filter(KnowledgeBaseModel.kb_type == "单位")
    if dep_id is not None:
        kbs = kbs.filter_by(dep_id=dep_id)
    result = []
    
    for kb in kbs:
        print("kb",str(kb))
        #查询chunk数
        chunks = session.query(FileDocModel).filter_by(kb_name=kb[1])
        chunk_count = len(chunks.all())
        result.append({"kb_name":kb[1],"file_count":kb[2],"chunk_count":chunk_count})

    return {"code":0,"msg":"成功","data":result}


@with_session
def statistics_all(session,
                dep_id:int
                      ) -> Dict:
    kb_count = 0
    objs = session.query(KnowledgeBaseModel.id)
    if dep_id is not None:
        objs = objs.filter_by(dep_id=dep_id).filter(KnowledgeBaseModel.kb_type == "单位")
    if objs:
        kb_count = len(objs.all())
    
    app_count = 0
    objs = session.query(AppModel)
    if dep_id is not None:
        objs = objs.filter_by(dep_id=dep_id)
    if objs:
        app_count = len(objs.all())
        
    doc_tem_count = 0
    objs = session.query(DocTemplateModel)
    if dep_id is not None:
        objs = objs.filter_by(dep_id=dep_id)
    if objs:
        doc_tem_count = len(objs.all())
        
    course_count = 0
    objs = session.query(Course)
    if dep_id is not None:
        objs = objs.filter_by(dep_id=dep_id)
    if objs:
        course_count = len(objs.all())
    
    gen_doc_count = 0
    objs = session.query(DocHistoryModel)
    if dep_id is not None:
        docs = session.query(DocTemplateModel).filter_by(dep_id=dep_id).all()
        data = [doc.to_out_dict() for doc in docs]
        doc_template_ids = [doc["id"] for doc in data if "id" in doc]
        if doc_template_ids:
            objs = objs.filter(DocHistoryModel.doc_template_id.in_(doc_template_ids))
    if objs:
        gen_doc_count = len(objs.all())
        
    course_eval_count = 0
    objs = session.query(EvalHistory)
    if dep_id is not None:
        objs = objs.filter_by(dep_id=dep_id)
    if objs:
        course_eval_count = len(objs.all())
    
    chat_feedback_count = 0
    objs = session.query(ChatFeedbackModel)
    if dep_id is not None:
        objs = objs.filter_by(dep_id=dep_id)
    if objs:
        chat_feedback_count = len(objs.all())

    return {"code": 0, "msg": "成功", "data": {"kb_count":kb_count,"app_count":app_count,"doc_template_count":doc_tem_count,"course_count":course_count,"gen_doc_count":gen_doc_count,"course_eval_count":course_eval_count,"chat_feedback_count":chat_feedback_count}}

from sqlalchemy import func

@with_session
def statistics_user(session,dep_id) -> Dict:
    
    db_obj = session.query(UserInfoModel.dep_id,func.count(UserInfoModel.id),DepartmentModel.name)
    if dep_id is not None:
        db_obj =  db_obj.filter_by(dep_id=dep_id)
    db_obj = db_obj.outerjoin(DepartmentModel,UserInfoModel.dep_id == DepartmentModel.id).group_by(UserInfoModel.dep_id).all()
    result = []
    for db_ in db_obj:
        if db_[2] is not None:
            result.append({"dep_id":db_[2],"count":db_[1]})
    

    return {"code":0,"msg":"成功","data":result}

@with_session
def statistics_doc(session,dep_id) -> Dict:
    update_doc_template_counts(dep_id=dep_id)
    db_obj = session.query(DocHistoryModel.doc_template_id,func.count(DocHistoryModel.id),DocTemplateModel.name).outerjoin(DocTemplateModel,DocHistoryModel.doc_template_id == DocTemplateModel.id)
    if dep_id is not None:
        db_obj = db_obj.filter(DocTemplateModel.dep_id == dep_id)
    db_obj = db_obj.group_by(DocHistoryModel.doc_template_id).all()
    result = []
    for db_ in db_obj:
        result.append({"doc_template_name":db_[2],"count":db_[1]})
    
    return {"code":0,"msg":"成功","data":result}


from sqlalchemy import Integer, JSON

@with_session
def statistics_app(session,dep_id
                    ) -> Dict:
    #查询应用数
    #查询用户数
    # app_count = 0
    objs = session.query(AppModel.id,AppTypeModel.name).outerjoin(AppTypeModel, AppModel.type_id == AppTypeModel.id)
    if dep_id is not None:
        objs = objs.filter(AppModel.dep_id==dep_id)
    ret = {}
    
    for db_ in objs:
        user_count = 0
        users = session.query(UserInfoModel.id).filter(
            func.json_contains(UserInfoModel.app_ids, str(db_[0]))
        )
        if users:
            user_count = len(users.all())
        app_type_name = db_[1]
        ret[app_type_name] = int(ret.get(app_type_name,0))+user_count
    result = []
    for key in ret.keys():
        result.append({"app_type_name":key,"count":ret.get(key,0)})

    return {"code":0,"msg":"成功","data":result}


@with_session
def statistics_course(session,
                      dep_id
                    ) -> Dict:
    #各个课程培训情况
    objs = session.query(Course.id,Course.name,func.count(EvalHistory.id)).outerjoin(Course, EvalHistory.course_id == Course.id)
    if dep_id is not None:
        objs = objs.filter(Course.dep_id==dep_id)
    
    objs = objs.group_by(Course.id).all()
    result = []
    for db_ in objs:
        result.append({"course_name":db_[1],"count":db_[2]})
    
    return {"code":0,"msg":"成功","data":result}


@with_session
def statistics_test_case(session,
                      dep_id
                    ) -> Dict:

    objs = session.query(TestCase.test_case_type,func.count(TestCase.id))
    if dep_id is not None:
        courses = session.query(Course).filter_by(dep_id=dep_id).all()
        data = [course.to_out_dict() for course in courses]
        course_ids = [course["id"] for course in data if "id" in course]
        if course_ids is not None:
            objs = objs.filter(TestCase.course_id.in_(course_ids))
               
    objs = objs.group_by(TestCase.test_case_type).all()
    result = []
    count = 0
    for db_ in objs:
        result.append({"test_case_type":db_[0],"count":db_[1]})
        count += int(db_[1])

    reference_qa_count = 0
    
    kb_query = session.query(KnowledgeBaseModel)
    if dep_id is not None:
        kb_query = kb_query.filter_by(dep_id=dep_id)
    
    kbs = kb_query.all()
    
    for kb in kbs:
        # 查询该知识库下所有qa_count大于0的文件
        files = session.query(KnowledgeFileModel).filter(
            KnowledgeFileModel.kb_name == kb.kb_name,
            KnowledgeFileModel.qa_count > 0
        ).all()
        
        for file in files:
            reference_qa_count += file.qa_count
    
    if reference_qa_count > 0:
        result.append({"test_case_type":"生成试题","count":reference_qa_count})
        count += reference_qa_count
    
    result.append({"test_case_type":"试题","count":count})
    return {"code":0,"msg":"成功","data":result}

@with_session
def statistics_job_title(session,
                      dep_id
                    ) -> Dict:
    #各个课程培训情况
    objs = session.query(Course.job_title,func.count(Course.id))
    if dep_id is not None:
        objs = objs.filter_by(dep_id=dep_id)
        
    objs = objs.group_by(Course.job_title).all()

    result = []
    for db_ in objs:
        result.append({"job_title":db_[0],"count":db_[1]})
    
    return {"code":0,"msg":"成功","data":result}
