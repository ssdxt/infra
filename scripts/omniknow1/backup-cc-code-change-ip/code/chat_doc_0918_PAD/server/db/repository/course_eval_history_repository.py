# from server.db.models.user_info_model import UserInfoModel
from server.db.models.course_eval_history import EvalHistory
from server.db.session import with_session
from server.knowledge_base.utils import KnowledgeFile
from typing import List, Dict

from datetime import datetime


@with_session
def course_eval_history_add(session,
            user_email:str,
            course_id:int,
            dep_id:int,
            eval_type:str,
            score: int = None
            ) -> Dict:
    
    obj = EvalHistory(user_email=user_email,course_id=course_id,score=score,dep_id=dep_id,eval_type=eval_type)
    id = session.add(obj)
    print("session_id",id)
    session.commit()
    #返回obj
    # db_obj = session.query(EvalHistory).filter_by(user_email=user_email).filter_by(course_id=course_id).filter_by(score=score).filter_by(dep_id=dep_id).first()
    db_obj = session.query(EvalHistory).filter_by(user_email=user_email).filter_by(course_id=course_id).filter_by(dep_id=dep_id).filter_by(eval_type=eval_type).order_by(EvalHistory.id.desc()).first()

    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def course_eval_history_update(session,
                id:int,
                user_email:str = None,
                course_id:int = None,
                score: int = None,
                dep_id:int = None,
                eval_type:str = None
                      ) -> Dict:
    
    db_obj = session.query(EvalHistory).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    if user_email:
        db_obj.user_email = user_email
    if course_id:
        db_obj.course_id = course_id
    if score:
        db_obj.score = score
    if dep_id:
        db_obj.dep_id = dep_id
    if eval_type:
        db_obj.eval_type = eval_type

    session.commit()
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def course_eval_history_delete(session,
                    id:int,
                    ) -> Dict:
    
    db_obj = session.query(EvalHistory).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"该数据不存在","data":{}}
    session.delete(db_obj)
    session.commit()
    return {"code":0,"msg":"成功","data":{}}

@with_session
def course_eval_history_list(session,dep_id=None,course_id=None,user_email= None,eval_type=None,page_start=None,page_end=None) -> Dict:
    db_objs = session.query(EvalHistory)
    db_objs = db_objs.filter(EvalHistory.score != None)

    #部门
    if dep_id:
        db_objs = db_objs.filter_by(dep_id=dep_id)
    #课程
    if course_id:
        db_objs = db_objs.filter_by(course_id=course_id)
    #用户email
    if user_email:
        db_objs = db_objs.filter_by(user_email=user_email)
    #考核类型
    if eval_type:
        db_objs = db_objs.filter_by(eval_type=eval_type)

    db_objs = db_objs.order_by(EvalHistory.id.desc())
    count=len(db_objs.all())

    if page_start is not None and page_end is not None:
        db_objs = db_objs.slice(page_start,page_end).all()
    else:
        db_objs = db_objs.all()
    
    data =[db_obj.to_out_dict() for db_obj in  db_objs]
    
    return {"code":0,"msg":"成功","data":{"count":count,"course_evals":data}}


@with_session
def course_eval_history_detail(session,
                    id:int,
                    is_detail:bool=True
                    ) -> Dict:
    
    db_obj = session.query(EvalHistory).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict(is_detail)}
