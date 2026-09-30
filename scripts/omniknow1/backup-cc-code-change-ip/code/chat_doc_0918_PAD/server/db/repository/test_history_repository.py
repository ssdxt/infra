# from server.db.models.user_info_model import UserInfoModel
from server.db.models.test_history import TestHistory
from server.db.session import with_session
from server.knowledge_base.utils import KnowledgeFile
from typing import List, Dict

from datetime import datetime


@with_session
def test_history_add(session,
            test_case_id:str,
            result:str,
            score: int,
            consume_time: int,
            user_email:str,
            eval_id:int,
            eval_index:int
                      ) -> Dict:
    
    obj = TestHistory(test_case_id=test_case_id,result=result,score=score,consume_time=consume_time,user_email=user_email,eval_id=eval_id,eval_index=eval_index)
    session.add(obj)
    session.commit()
    #返回obj
    # db_obj = session.query(TestHistory).filter_by(name=name).first()
    return {"code":0,"msg":"成功","data":{}}


@with_session
def test_history_update(session,
                id:int,
                test_case_id:str,
                result:str,
                score: int,
                consume_time: int,
                user_email:str,
                eval_id:int,
                eval_index:int
                      ) -> Dict:
    
    db_obj = session.query(TestHistory).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    if test_case_id:
        db_obj.test_case_id = test_case_id
    if result:
        db_obj.result = result
    if score:
        db_obj.score = score
    if consume_time:
        db_obj.consume_time = consume_time
    if user_email:
        db_obj.user_email = user_email
    if eval_id:
        db_obj.eval_id = eval_id
    if eval_index:
        db_obj.eval_index = eval_index
    session.commit()
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}


@with_session
def test_history_delete(session,
                    eval_id:int,
                    ) -> Dict:
    
    db_objs = session.query(TestHistory).filter_by(eval_id=eval_id).all()
    if db_objs is None:
        return {"code":-1,"msg":"该数据不存在","data":{}}
    for db_obj in db_objs:
        session.delete(db_obj)
    session.commit()
    return {"code":0,"msg":"成功","data":{}}

@with_session
def test_history_list(session,eval_id=None,user_email=None) -> Dict:
    db_objs = session.query(TestHistory)

    if eval_id:
        db_objs = db_objs.filter_by(eval_id=eval_id)
    if user_email:
        db_objs = db_objs.filter_by(user_email=user_email)
        
    db_objs = db_objs.order_by(TestHistory.eval_index.asc())
    db_objs = db_objs.order_by(TestHistory.id.desc())
    
    db_objs = db_objs.all()
    
    count=len(db_objs)
    data =[db_obj.to_out_dict() for db_obj in  db_objs]
    
    return {"code":0,"msg":"成功","data":{"count":count,"test_historys":data}}


@with_session
def test_history_detail(session,
                    id:int,
                    is_detail:bool=True
                    ) -> Dict:
    
    db_obj = session.query(TestHistory).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict(is_detail)}

@with_session
def test_history_suggestion(session,
                    user_email:str,
                    is_detail:bool=True
                    ) -> Dict:
    
    db_objs = session.query(TestHistory).filter_by(user_email=user_email).all()
    if db_objs is None:
        return {"code":-1,"msg":"数据不存在","data":[]}
    data = [obj.to_out_dict(is_detail) for obj in db_objs]
    return {"code":0,"msg":"成功","data":data}
