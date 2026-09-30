from server.db.session import with_session
from server.db.models.chat_history_model import ChatHistoryModel
import re
import uuid
from typing import Dict, List


def _convert_query(query: str) -> str:
    p = re.sub(r"\s+", "%", query)
    return f"%{p}%"


@with_session
def add_chat_history_to_db(session, chat_type, query, response="", chat_history_id=None, metadata: Dict = {},chat_session_id=None,user_id=None):
    """
    新增聊天记录
    """
    if not chat_session_id:
        chat_session_id = uuid.uuid4().hex
    if not chat_history_id:
        chat_history_id = uuid.uuid4().hex
    ch = ChatHistoryModel(id=chat_history_id, chat_type=chat_type, query=query, response=response,
                        metadata=metadata,chat_session_id=chat_session_id,user_id=user_id)
    session.add(ch)
    session.commit()
    return chat_session_id,ch.id


@with_session
def update_chat_history(session, chat_session_id, chat_id, response: str = None, metadata: Dict = None):
    """
    更新已有的聊天记录
    """
    ch = session.query(ChatHistoryModel).filter_by(chat_session_id=chat_session_id,id=chat_id).first()
    if response:
        ch.response = response
    session.commit()
    return {"code":0,"msg":"成功","data":ch.to_out_dict()}
    # ch = get_chat_history_by_id(chat_history_id)
    # if ch is not None:
    #     if response is not None:
    #         ch.response = response
    #     if isinstance(metadata, dict):
    #         ch.meta_data = metadata
    #     session.add(ch)
    #     return ch.id


@with_session
def feedback_chat_history_to_db(session, chat_history_id, feedback_score, feedback_reason,chat_session=None,user_id=None):
    """
    反馈聊天记录
    """
    ch = session.query(ChatHistoryModel).filter_by(id=chat_history_id).first()
    if ch:
        ch.feedback_score = feedback_score
        ch.feedback_reason = feedback_reason
        if chat_session:
            ch.chat_session = chat_session
        if user_id :
            ch.user_id = user_id
        return ch.id

@with_session
def feedback_reason_in_db(session,session_id,chat_history_id,feedback_score,feedback_reason,user_id):
    """
    反馈正确答案
    """
    ch = session.query(ChatHistoryModel).filter_by(chat_session_id=session_id,id=chat_history_id).first()
    if feedback_score:
        ch.feedback_score = feedback_score
    if feedback_reason:
        ch.feedback_reason = feedback_reason
    if user_id :
        ch.user_id = user_id
    session.commit()
    return {"code":0,"msg":"成功","data":ch.to_out_dict()}

@with_session
def get_chat_history_by_id(session,chat_session_id,chat_history_id):
    """
    查询聊天记录
    """
    ch = session.query(ChatHistoryModel).filter_by(chat_session_id=chat_session_id,id=chat_history_id).first()
    if ch is None:
        return {"code":-1,"msg":"历史记录不存在","data":{}}
    
    return {"code":0,"msg":"成功","data":ch.to_out_dict()}


@with_session
def filter_chat_history(session, query=None, response=None, score=None, reason=None) -> List[ChatHistoryModel]:
    ch =session.query(ChatHistoryModel)
    if query is not None:
        ch = ch.filter(ChatHistoryModel.query.ilike(_convert_query(query)))
    if response is not None:
        ch = ch.filter(ChatHistoryModel.response.ilike(_convert_query(response)))
    if score is not None:
        ch = ch.filter_by(feedback_score=score)
    if reason is not None:
        ch = ch.filter(ChatHistoryModel.feedback_reason.ilike(_convert_query(reason)))

    return ch

@with_session
def delete_chat_session(session, chat_session_id):
    """
    删除当前聊天框数据
    """
    from server.db.models.chat_feedback import ChatFeedbackModel
    
    history_deleted_count = session.query(ChatHistoryModel)\
                          .filter_by(chat_session_id=chat_session_id)\
                          .delete()

    feedback_deleted_count = session.query(ChatFeedbackModel)\
                           .filter(ChatFeedbackModel.kb_name == chat_session_id)\
                           .delete()

    session.commit()
    
    total_deleted_count = history_deleted_count + feedback_deleted_count
    
    if total_deleted_count > 0:
        return {"code": 0, "msg": "成功删除", "data": {
            "deleted_count": total_deleted_count,
            "history_deleted_count": history_deleted_count,
            "feedback_deleted_count": feedback_deleted_count
        }}
    else:
        return {"code": 404, "msg": "未找到对应记录", "data": {}}
    