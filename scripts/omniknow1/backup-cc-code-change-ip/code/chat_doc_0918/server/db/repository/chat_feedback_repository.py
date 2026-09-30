from server.db.session import with_session
from server.db.models.chat_feedback import ChatFeedbackModel
import re
import uuid
from typing import Dict, List
from server.knowledge_base.kb_service.base import KBServiceFactory
from langchain.docstore.document import Document

@with_session
def chat_feedback_add(session,
            app_id:int,
            app_name:str,
            kb_name:str,
            chat_session_id:str,
            chat_id:str,
            feedback_score:int,
            feedback_reason:str,
            user_email:str,
            user_name:str,
            dep_id:int,
            meta_data:Dict = None
            ) -> Dict:
    
    db_obj = session.query(ChatFeedbackModel).filter_by(chat_session_id=chat_session_id,chat_id=chat_id,feedback_reason=feedback_reason).first()
    if db_obj:
        return {"code":-1,"msg":"该条问答已提交过相同反馈","data":{}}
    else:
        obj = ChatFeedbackModel(app_id=app_id,app_name=app_name,kb_name=kb_name,chat_session_id=chat_session_id,chat_id=chat_id,feedback_score=feedback_score,feedback_reason=feedback_reason,user_email=user_email,user_name=user_name,dep_id=dep_id,meta_data=meta_data)
    
    session.add(obj)
    session.commit()
    db_obj = session.query(ChatFeedbackModel).filter_by(chat_session_id=chat_session_id,chat_id=chat_id,feedback_reason=feedback_reason).first()

    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}

@with_session
def chat_feedback_update(session,
                id:int,
                feedback_reason:str,
                meta_data: dict = None
                      ) -> Dict:
    
    db_obj = session.query(ChatFeedbackModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"反馈记录不存在","data":{}}
    
    if feedback_reason:
        db_obj.feedback_reason = feedback_reason
    
    if meta_data is not None:
        db_obj.meta_data = meta_data
        
    session.commit()
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}

@with_session
def chat_feedback_delete(session,
                    id:int,
                    ) -> Dict:
    
    db_obj = session.query(ChatFeedbackModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"该数据不存在","data":{}}
    
    # 获取文件夹路径信息
    chat_session_id = db_obj.chat_session_id
    chat_id = db_obj.chat_id
    
    kb_name = db_obj.kb_name
    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return {"code":-1,"msg":"知识库不存在","data":{}}
    
    kb.do_delete_vs_by_feedback_id(id)
    kb.save_vector_store()
    
    # 删除对应的文件夹
    import os
    import shutil
    project_root = os.getcwd()
    feedback_dir = os.path.join(project_root, "feedback_files", chat_session_id, chat_id)
    
    if os.path.exists(feedback_dir):
        try:
            shutil.rmtree(feedback_dir)
        except Exception as e:
            # 记录日志但不影响数据库删除
            print(f"删除文件夹失败: {feedback_dir}, 错误: {str(e)}")
    
    session.delete(db_obj)
    session.commit()

    return {"code":0,"msg":"删除成功","data":{}}

@with_session
def chat_feedback_list(session,dep_id,id=None,check_status=None,page_start=None,page_end=None) -> Dict:
    
    db_objs = session.query(ChatFeedbackModel)
    db_objs = db_objs.order_by(ChatFeedbackModel.id.desc())

    if dep_id:
        db_objs = db_objs.filter_by(dep_id=dep_id)
    if id:
        db_objs = db_objs.filter_by(id=id)
    if check_status:
        db_objs = db_objs.filter_by(check_status=check_status)

    count = db_objs.count()

    if page_start is not None and page_end is not None:
        db_objs = db_objs.slice(page_start,page_end).all()
    else:
        db_objs = db_objs.all()
    
    data =[db_obj.to_out_dict() for db_obj in  db_objs]
    
    return {"code":0,"msg":"成功","data":{"count":count,"chat_feedbacks":data}}

@with_session
def chat_feedback_detail(session,
                    id:int,
                    is_detail:bool=True
                    ) -> Dict:
    
    db_obj = session.query(ChatFeedbackModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict(is_detail)}

@with_session
def chat_feedback_check(session,
                    id:int,
                    check_status:str,
                    query:str
                    ) -> Dict:
    
    db_obj = session.query(ChatFeedbackModel).filter_by(id=id).first()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    
    db_obj.check_status = check_status
    
    session.commit()

    if check_status == "通过":
        kb_name = db_obj.kb_name
        feedback_reason = db_obj.feedback_reason
        kb = KBServiceFactory.get_service_by_name(kb_name)
        if kb is None:
            return {"code":0,"msg":"未找到知识库","data":{}}

        feedback_files = []
        if db_obj.meta_data and "feedback_files" in db_obj.meta_data:
            feedback_files = db_obj.meta_data["feedback_files"]
        
        document = Document(page_content=query,metadata={"feedback_source_id": id,"answer":feedback_reason,"source":kb_name,"feedback_files":feedback_files})
        
        qa = kb.add_qa(docs=[document])

        if qa:
            kb.save_vector_store()
            return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}
        else:
            return {"code":0,"msg":"更新失败","data":{}}
        
    return {"code":0,"msg":"成功","data":db_obj.to_out_dict()}