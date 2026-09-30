# from server.db.models.user_info_model import UserInfoModel
from server.db.models.course import Course
from server.db.session import with_session
from server.knowledge_base.utils import KnowledgeFile
from server.db.repository.app_repository import app_detail
from typing import List, Dict
from server.db.repository.knowledge_base_repository import load_kb_from_db_id
from server.db.repository.knowledge_file_repository import get_file_detail
from datetime import datetime
import copy
from sqlalchemy import text

@with_session
def course_add(session,
            name:str,
            desc:str,
            job_title:List,
            kb_id: int,
            file_name:str,
            user_email:str,
            abstract:str,
            activate:bool,
            dep_id:int,
            ) -> Dict:
    
    db_obj = session.query(Course).filter_by(name=name, dep_id=dep_id).first()
    if db_obj:
        return {"code": -1, "msg": "已经存在", "data": {}}
    
    if job_title:
        import json
        if isinstance(job_title, str) and job_title.startswith('[') and job_title.endswith(']'):
            try:
                job_title = json.loads(job_title)
            except json.JSONDecodeError:
                pass
            
    obj = Course(name=name,desc=desc,job_title=job_title,kb_id=kb_id,file_name=file_name,user_email=user_email,abstract=abstract,activate=activate,dep_id=dep_id,exam_test_case={},exam_paper_status="未生成")
    session.add(obj)
    session.commit()

    db_obj = session.query(Course).filter_by(name=name, dep_id=dep_id).first()
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def course_update(session,
                id:int,
                name:str,
                desc:str,
                job_title:List,
                kb_id: int,
                file_name:str,
                user_email:str,
                abstract:str,
                activate:bool,
                dep_id:int,
                      ) -> Dict:
    
    db_obj = session.query(Course).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    
    if str(db_obj.name) != name:
        db_obj2 = session.query(Course).filter_by(name=name, dep_id=dep_id).first()
        if db_obj2 :
            return {"code":-1,"msg":"已经存在","data":{}}
        else:
            db_obj.name = name
    
    print("job_title=========",job_title)
    if desc:
        db_obj.desc = desc
    if job_title:
        import json
        if isinstance(job_title, str) and job_title.startswith('[') and job_title.endswith(']'):
            try:
                job_title = json.loads(job_title)
            except json.JSONDecodeError:
                pass
        db_obj.job_title = job_title
    if kb_id:
        db_obj.kb_id = kb_id
    if file_name:
        db_obj.file_name = file_name
    if user_email:
        db_obj.user_email = user_email
    if abstract:
        db_obj.abstract = abstract
    if activate is not None:
        db_obj.activate = activate
    if dep_id:
        db_obj.dep_id = dep_id
    
    session.commit()

    print("result============",db_obj.to_out_dict())
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def course_delete(session,
                    id:int,
                    ) -> Dict:
    
    db_obj = session.query(Course).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"该数据不存在","data":{}}
    session.delete(db_obj)
    session.commit()
    return {"code":0,"msg":"成功","data":{}}

# @with_session
# def course_list(session,dep_id=None,name=None,job_title=None,user_permission=False,app_id=None,page_start=None, page_end=None) -> Dict:
#     from server.db.repository.test_case_repository import test_case_list
#     from server.db.models.test_case import TestCase
#     from server.db.models.knowledge_file_model import FileDocModel
    
#     db_objs = session.query(Course)
#     db_objs = db_objs.order_by(Course.id.desc())

#     if dep_id:
#         db_objs = db_objs.filter_by(dep_id=dep_id)

#     if name:
#         db_objs = db_objs.filter(Course.name.like('%'+name+'%'))

#     if job_title:
#         db_objs = db_objs.filter(Course.job_title.like('%'+job_title+'%'))

#     if not user_permission:
#         db_objs = db_objs.filter_by(activate=True)
#         courses = db_objs.all()

#         app_info = app_detail(id=app_id,is_detail=False)
#         train_num = app_info["data"].get("info", {}).get("trainNum")
#         if train_num is None:
#                 return {"code":-1,"msg":"未设置考题数量","data":{}}

#         filtered_courses = []
#         question_types = ["选择题", "判断题", "问答题"]
        
#         for course in courses:
#             # 获取课程信息
#             course_info = course_detail(id=course.id, is_detail=False)
#             if course_info["code"] != 0:
#                 continue
                
#             kb_id = course_info["data"].get("kb_id")
#             file_name = course_info["data"].get("file_name")
            
#             if not kb_id or not file_name:
#                 continue
                
#             # 获取知识库名称
#             kb_name, vs_type, embed_model = load_kb_from_db_id(kb_id)
#             if not kb_name:
#                 continue
                
#             # 使用SQL直接查询各题型的数量
#             meets_requirements = True
            
#             for question_type in question_types:
#                 # 1. 查询参考试题数量
#                 ref_count = session.query(TestCase).filter(
#                     TestCase.course_id == course.id,
#                     TestCase.test_case_type == "参考试题",
#                     TestCase.question_type == question_type
#                 ).count()
                
#                 # 2. 查询与文件关联的所有doc_id
#                 file_docs = session.query(FileDocModel).filter(
#                     FileDocModel.kb_name == kb_name,
#                     FileDocModel.file_name == file_name
#                 ).all()
                
#                 doc_ids = [doc.doc_id for doc in file_docs]
                
#                 # 3. 如果有doc_ids，查询生成试题数量
#                 gen_count = 0
#                 if doc_ids:
#                     gen_count = session.query(TestCase).filter(
#                         TestCase.vs_id.in_(doc_ids),
#                         TestCase.test_case_type == "生成试题",
#                         TestCase.question_type == question_type
#                     ).count()
                
#                 # 4. 判断总数是否满足要求
#                 total_count = ref_count + gen_count
#                 if total_count < train_num:
#                     meets_requirements = False
#                     break
            
#             if meets_requirements:
#                 filtered_courses.append(course)

#         db_objs = filtered_courses

#     if isinstance(db_objs, list):
#         for course in db_objs:
#             if course.exam_test_case:
#                 course.exam_paper_status = "已生成"
#     else:
#         for course in db_objs.all():
#             if course.exam_test_case:
#                 course.exam_paper_status = "已生成"

#     if page_start is not None and page_end is not None:
#         if isinstance(db_objs, list):
#             count = len(db_objs)
#             data = [db_obj.to_out_dict() for db_obj in db_objs[page_start:page_end]]
#         else:
#             count = db_objs.count()
#             db_objs = db_objs.slice(page_start, page_end).all()
#             data = [db_obj.to_out_dict() for db_obj in db_objs]
#     else:
#         if isinstance(db_objs, list):
#             count = len(db_objs)
#             data = [db_obj.to_out_dict() for db_obj in db_objs]
#         else:
#             count = db_objs.count()
#             db_objs = db_objs.all()
#             data = [db_obj.to_out_dict() for db_obj in db_objs]
    
#     if not user_permission:
#         data = [item for item in data if item.get('kb_id') and item.get('file_name')]
#         count = len(data)
        
#     return {"code":0,"msg":"成功","data":{"count":count,"courses":data}}

@with_session
def course_list(session,dep_id=None,name=None,job_title=None,user_permission=False,app_id=None,page_start=None, page_end=None) -> Dict:
    from server.db.models.test_case import TestCase
    from server.db.models.knowledge_file_model import FileDocModel
    from sqlalchemy import func
    
    db_objs = session.query(Course)
    db_objs = db_objs.order_by(Course.id.desc())

    if dep_id:
        db_objs = db_objs.filter_by(dep_id=dep_id)

    if name:
        db_objs = db_objs.filter(Course.name.like('%'+name+'%'))

    if job_title:
        db_objs = db_objs.filter(text("JSON_SEARCH(job_title, 'one', :job_title_pattern) IS NOT NULL").bindparams(
        job_title_pattern=f"%{job_title}%"
    ))

    if not user_permission:
        db_objs = db_objs.filter_by(activate=True)
        
        courses = db_objs.all()
        
        app_info = app_detail(id=app_id,is_detail=False)
        train_num = app_info["data"].get("info", {}).get("trainNum")
        if train_num is None:
            return {"code":-1,"msg":"未设置考题数量","data":{}}

        course_ids = [course.id for course in courses]
        course_details = {}
        for course_id in course_ids:
            course_info = course_detail(id=course_id, is_detail=False)
            if course_info["code"] == 0:
                course_details[course_id] = course_info["data"]
        
        kb_file_pairs = []
        course_kb_file_map = {}
        for course_id, details in course_details.items():
            kb_id = details.get("kb_id")
            file_name = details.get("file_name")
            if kb_id and file_name:
                kb_file_pairs.append((kb_id, file_name))
                course_kb_file_map[course_id] = (kb_id, file_name)
        
        kb_info_map = {}
        for kb_id, _ in kb_file_pairs:
            if kb_id not in kb_info_map:
                kb_name, vs_type, embed_model = load_kb_from_db_id(kb_id)
                if kb_name:
                    kb_info_map[kb_id] = (kb_name, vs_type, embed_model)
        
        kb_file_docs = {}
        for kb_id, file_name in kb_file_pairs:
            if kb_id in kb_info_map:
                kb_name = kb_info_map[kb_id][0]
                file_docs = session.query(FileDocModel).filter(
                    FileDocModel.kb_name == kb_name,
                    FileDocModel.file_name == file_name
                ).all()
                kb_file_docs[(kb_id, file_name)] = [doc.doc_id for doc in file_docs]
        
        question_types = ["选择题", "判断题", "问答题"]
        
        ref_counts = {}
        for course_id in course_ids:
            for question_type in question_types:
                ref_count = session.query(TestCase).filter(
                    TestCase.course_id == course_id,
                    TestCase.test_case_type == "参考试题",
                    TestCase.question_type == question_type
                ).count()
                ref_counts[(course_id, question_type)] = ref_count
        
        all_doc_ids = []
        for doc_ids in kb_file_docs.values():
            all_doc_ids.extend(doc_ids)
        
        gen_counts_by_doc = {}
        if all_doc_ids:
            gen_test_cases = session.query(TestCase.vs_id, TestCase.question_type, func.count('*').label('count')).filter(
                TestCase.vs_id.in_(all_doc_ids),
                TestCase.test_case_type == "生成试题"
            ).group_by(TestCase.vs_id, TestCase.question_type).all()
            
            for vs_id, question_type, count in gen_test_cases:
                gen_counts_by_doc[(vs_id, question_type)] = count
        
        filtered_courses = []
        for course in courses:
            course_id = course.id
            if course_id not in course_kb_file_map:
                continue
                
            kb_id, file_name = course_kb_file_map[course_id]
            if (kb_id, file_name) not in kb_file_docs:
                continue
                
            doc_ids = kb_file_docs[(kb_id, file_name)]
            
            meets_requirements = True
            for question_type in question_types:
                ref_count = ref_counts.get((course_id, question_type), 0)
                
                gen_count = 0
                for doc_id in doc_ids:
                    gen_count += gen_counts_by_doc.get((doc_id, question_type), 0)
                
                total_count = ref_count + gen_count
                if total_count < train_num:
                    meets_requirements = False
                    break
            
            if meets_requirements:
                filtered_courses.append(course)

        db_objs = filtered_courses

    if isinstance(db_objs, list):
        for course in db_objs:
            if course.exam_test_case:
                course.exam_paper_status = "已生成"
    else:
        for course in db_objs.all():
            if course.exam_test_case:
                course.exam_paper_status = "已生成"

    if page_start is not None and page_end is not None:
        if isinstance(db_objs, list):
            count = len(db_objs)
            data = [db_obj.to_out_dict() for db_obj in db_objs[page_start:page_end]]
        else:
            count = db_objs.count()
            db_objs = db_objs.slice(page_start, page_end).all()
            data = [db_obj.to_out_dict() for db_obj in db_objs]
    else:
        if isinstance(db_objs, list):
            count = len(db_objs)
            data = [db_obj.to_out_dict() for db_obj in db_objs]
        else:
            count = db_objs.count()
            db_objs = db_objs.all()
            data = [db_obj.to_out_dict() for db_obj in db_objs]
    
    if not user_permission:
        data = [item for item in data if item.get('kb_id') and item.get('file_name')]
        count = len(data)
        
    return {"code":0,"msg":"成功","data":{"count":count,"courses":data}}

@with_session
def course_detail(session,
                    id:int,
                    is_detail:bool=True
                    ) -> Dict:
    
    db_obj = session.query(Course).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    if db_obj.exam_test_case:
        db_obj.exam_paper_status = "已生成"
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict(is_detail)}

@with_session
def course_update_exam(session,id,exam_test_case) -> Dict:
    
    db_obj = session.query(Course).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    
    if exam_test_case:
        db_obj.exam_test_case = exam_test_case

    session.commit()
    return {"code":0,"msg":"成功","data":{}}

@with_session
def course_update_exam_fields(session, id, exam_questions=None, exam_time=None) -> Dict:
    """
    更新考试题目及时间信息
    """
    db_obj = session.query(Course).filter_by(id=id).first()
    if db_obj is None:
        return {"code": -1, "msg": "数据不存在", "data": {}}
    
    current_exam_test_case = copy.deepcopy(db_obj.exam_test_case or {})
    
    if exam_questions is not None:
        current_exam_test_case["exam_questions"] = exam_questions
    
    if exam_time is not None:
        current_exam_test_case["exam_time"] = exam_time
    
    db_obj.exam_test_case = current_exam_test_case
    session.commit()
    
    return {"code": 0, "msg": "成功", "data": {}}

@with_session
def course_list_exam(session,id) -> Dict:
    
    db_obj = session.query(Course).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}

    if not db_obj.exam_test_case:
        return {"code": 400, "msg": "试卷未生成", "data": {}}
    
    exam_questions = db_obj.exam_test_case["exam_questions"]

    return {"code": 0, "msg": "成功", "data": exam_questions}

@with_session
def student_list_course(session,dep_id) -> Dict:
    
    db_objs = session.query(Course).filter_by(dep_id=dep_id,activate=True).all() 
    count=len(db_objs)

    return count

@with_session
def course_update_ep_status(session,id:int,exam_paper_status:str) -> Dict:
    
    db_obj = session.query(Course).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    
    if exam_paper_status:
        db_obj.exam_paper_status = exam_paper_status
    
    session.commit()
    return True