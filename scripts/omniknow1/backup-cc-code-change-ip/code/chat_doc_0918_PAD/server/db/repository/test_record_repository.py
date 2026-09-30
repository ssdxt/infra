from server.db.models.test_record import TestRecord
from server.db.session import with_session
from server.knowledge_base.utils import KnowledgeFile
from typing import List, Dict

from datetime import datetime


@with_session
def test_record_add(
            session,
            user_email:str,
            suggestion:str,
            reference:str,
                      ) -> Dict:
    
    db_obj = session.query(TestRecord).filter_by(user_email=user_email).first()
    if db_obj:
        return {"code":-1,"msg":"已经存在","data":{}}

    obj = TestRecord(user_email=user_email,suggestion=suggestion,reference=reference)
    session.add(obj)
    session.commit()
    db_obj = session.query(TestRecord).filter_by(user_email=user_email).first()
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}

@with_session
def test_record_update(session,
                user_email:str,
                suggestion:str,
                reference:str,
                      ) -> Dict:
    
    db_obj = session.query(TestRecord).filter_by(user_email=user_email).first()
    if db_obj is None:
        return {"code":200,"msg":"数据不存在","data":{}}

    if suggestion:
        db_obj.suggestion = suggestion
    if reference:
        db_obj.reference = reference

    session.commit()
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}

@with_session
def test_record_list(session,user_email=None) -> Dict:
    db_obj = session.query(TestRecord).filter_by(user_email=user_email).first()
    if not db_obj:
        return {"code": 200, "msg": "没有找到数据", "data":{}}
    
    return {"code": 0, "msg": "成功", "data":db_obj.to_out_dict()}

@with_session
def check_test_record(session, user_email: str) -> bool:
    return session.query(TestRecord).filter_by(user_email=user_email).first() is not None