# from server.db.models.user_info_model import UserInfoModel
from server.db.models.test_case import TestCase
from server.db.session import with_session
from server.knowledge_base.utils import KnowledgeFile
from typing import List, Dict

from datetime import datetime
from server.db.repository.course_repository import course_detail
from server.db.repository.knowledge_base_repository import load_kb_from_db_id
from server.db.repository.knowledge_file_repository import list_filedoc_from_db

@with_session
def test_case_add(
            session,
            question:str,
            answer:str,
            vs_id: str,
            user_email: str,
            test_case_type:str,
            course_id:int,
            question_type:str
                      ) -> Dict:
    
    user = session.query(TestCase).filter_by(question=question).first()
    if user:
        return {"code":-1,"msg":"已经存在","data":{}}

    obj = TestCase(question=question,answer=answer,vs_id=vs_id,user_email=user_email,test_case_type=test_case_type,course_id=course_id,question_type=question_type)
    session.add(obj)
    session.commit()
    #返回obj
    db_obj = session.query(TestCase).filter_by(question=question).first()
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def test_case_update(session,
                id:int,
                question:str,
                answer:str,
                vs_id: str,
                user_email: str,
                test_case_type:str,
                course_id:int,
                question_type:str
                      ) -> Dict:
    
    db_obj = session.query(TestCase).filter_by(id=id).first()
    if db_obj is None:
        return {"code":200,"msg":"数据不存在","data":{}}

    if question:
        obj = session.query(TestCase).filter_by(question=question).first()
        if obj and obj.id != id:
            return {"code": -1, "msg": "问题已经存在", "data": {}}
        else:
            db_obj.question = question

    if answer:
        db_obj.answer = answer
    if vs_id:
        db_obj.vs_id = vs_id
    if user_email:
        db_obj.user_email = user_email
    if test_case_type:
        db_obj.test_case_type = test_case_type
    if course_id:
        db_obj.course_id = course_id
    if question_type:
        db_obj.question_type = question_type

    session.commit()
    return {"code": 0, "msg": "成功", "data": db_obj.to_out_dict()}


@with_session
def test_case_delete(session,
                    id:int,
                    ) -> Dict:
    
    db_obj = session.query(TestCase).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"该数据不存在","data":{}}
    session.delete(db_obj)
    session.commit()
    return {"code":0,"msg":"成功","data":{}}


@with_session
def test_case_list(session, question=None, course_id=None, vs_id=None, test_case_type=None, question_type=None, page_start=None, page_end=None) -> Dict:

    db_objs = session.query(TestCase)
    
    if test_case_type == "参考试题":
        if course_id:
            db_objs = db_objs.filter_by(course_id=course_id)
    
    else:
        if course_id:
            course_info = course_detail(id=course_id, is_detail=False)
            if course_info["code"] != 0:
                return {"code": -1, "msg": "课程信息获取失败", "data": {}}

            kb_id = course_info["data"].get("kb_id")
            file_name = course_info["data"].get("file_name")

            if not kb_id or not file_name:
                return {"code": -1, "msg": "课程的知识库信息或文件名缺失", "data": {}}

            kb_name, vs_type, embed_model = load_kb_from_db_id(kb_id)

            if not kb_name:
                return {"code": -1, "msg": "知识库名称获取失败", "data": {}}
    
            vs_id_response = list_filedoc_from_db(kb_name=kb_name, file_name=file_name)
            if vs_id_response["code"] != 0:
                return {"code": -1, "msg": "向量库文档ID获取失败", "data": {}}

            vs_ids = [doc["doc_id"] for doc in vs_id_response["data"]]
            if not vs_ids:
                return {"code": -1, "msg": "未找到匹配的向量库文档ID", "data": {}}

            db_objs_course = db_objs.filter_by(course_id=course_id)
            db_objs_vs = db_objs.filter(TestCase.vs_id.in_(vs_ids))
            db_objs = db_objs_course.union(db_objs_vs)

    if vs_id:
        db_objs = db_objs.filter_by(vs_id=vs_id)
    if test_case_type:
        db_objs = db_objs.filter_by(test_case_type=test_case_type)
    if question_type:
        db_objs = db_objs.filter_by(question_type=question_type)
    if question:
        db_objs = db_objs.filter(TestCase.question.like('%' + question + '%'))

    db_objs = db_objs.order_by(TestCase.id.desc())
    
    count = db_objs.count()

    if page_start is not None and page_end is not None:
        db_objs = db_objs.slice(page_start, page_end).all()
    else:
        db_objs = db_objs.all()

    data = [db_obj.to_out_dict() for db_obj in db_objs]

    return {"code": 0, "msg": "成功", "data": {"count": count, "test_cases": data}}


@with_session
def test_case_detail(session,
                    id:int,
                    is_detail:bool=True
                    ) -> Dict:
    
    db_obj = session.query(TestCase).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict(is_detail)}

# 获取 test_case 的函数
@with_session
def get_test_case_by_id(session,
                    id:int,
                    ) -> Dict:

    db_obj = session.query(TestCase).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    
    question = db_obj.question
    answer = db_obj.answer

    session.commit()
    return {"code": 0, "msg": "成功", "data": {"question": question, "answer": answer}}

@with_session
def get_qa_by_vsid(session,
                    vs_id:str,
                    ) -> Dict:

    db_objs = session.query(TestCase).filter_by(vs_id=vs_id).all()
    if db_objs is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    
    data =[db_obj.to_out_dict(is_detail=False) for db_obj in  db_objs]

    session.commit()
    return {"code": 0, "msg": "成功", "data":data}

@with_session
def get_qa_by_vsid_batch(session,
                    vs_ids:List[str],
                    ) -> Dict:

    db_objs = session.query(TestCase.vs_id,TestCase.id,TestCase.question,TestCase.answer,TestCase.question_type).filter(TestCase.vs_id.in_(vs_ids)).all()
    data=[]
    for idx in range(len(vs_ids)):
        data.append(list())
    for db_obj in db_objs:
        _vs_id = db_obj[0]
        tc = {"test_case_id":db_obj[1],"question":db_obj[2],"answer":db_obj[3],"question_type":db_obj[4]}
        idx = vs_ids.index(_vs_id)
        data[idx].append(tc)
    return data


@with_session
def get_tc_by_courseid(session,
                    course_id:str,
                    ) -> Dict:

    db_objs = session.query(TestCase)

    course_info = course_detail(id=course_id, is_detail=False)
    if course_info["code"] != 0:
        return {"code": -1, "msg": "课程信息获取失败", "data": {}}

    kb_id = course_info["data"].get("kb_id")
    file_name = course_info["data"].get("file_name")

    if not kb_id or not file_name:
        return {"code": -1, "msg": "课程的知识库信息或文件名缺失", "data": {}}

    kb_name, vs_type, embed_model = load_kb_from_db_id(kb_id)

    if not kb_name:
        return {"code": -1, "msg": "知识库名称获取失败", "data": {}}

    vs_id_response = list_filedoc_from_db(kb_name=kb_name, file_name=file_name)
    if vs_id_response["code"] != 0:
        return {"code": -1, "msg": "向量库文档ID获取失败", "data": {}}

    vs_ids = [doc["doc_id"] for doc in vs_id_response["data"]]
    if not vs_ids:
        return {"code": -1, "msg": "未找到匹配的向量库文档ID", "data": {}}

    db_objs_course = db_objs.filter_by(course_id=course_id)
    db_objs_vs = db_objs.filter(TestCase.vs_id.in_(vs_ids))
    db_objs = db_objs_course.union(db_objs_vs)

    if db_objs is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    
    db_objs = db_objs.all()
    data =[db_obj.to_out_dict() for db_obj in  db_objs]

    session.commit()
    return {"code": 0, "msg": "成功", "data":data}

def get_file_test_case_count(kb_name: str, file_name: str):
    from server.db.repository.knowledge_file_repository import get_docs_detail
    """
    获取指定知识库和文件对应的所有题目的总数量
    """
    # 获取文件对应的所有文档详情
    docs_detail = get_docs_detail(kb_name=kb_name, filename=file_name)

    # 提取所有的vs_id（即doc_id）
    vs_ids = [doc["doc_id"] for doc in docs_detail if doc["doc_id"]]

    # 如果没有找到任何vs_id，则题目数量为0
    if not vs_ids:
        return 0

    # 获取所有vs_id对应的题目总数量
    count = 0
    for vs_id in vs_ids:
        # 调用test_case_list获取每个vs_id的题目数量
        result = test_case_list(vs_id=vs_id)
        count += result["data"]["count"]

    return count


def get_qa_by_kb_and_file(kb_name: str, file_name: str):

    from server.db.repository.knowledge_file_repository import get_docs_detail

    docs_detail = get_docs_detail(kb_name=kb_name, filename=file_name)

    vs_ids = [doc["doc_id"] for doc in docs_detail if doc["doc_id"]]
    if not vs_ids:
        return {"code": -1, "msg": "未找到匹配的向量库文档ID", "data": []}
    
    # 获取所有问答对
    qa_pairs = []
    for vs_id in vs_ids:
        qa_response = get_qa_by_vsid(vs_id=vs_id)
        if qa_response["code"] == 0:
            qa_pairs.extend(qa_response["data"])
    
    return {"code": 0, "msg": "成功", "data": qa_pairs}