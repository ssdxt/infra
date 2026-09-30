from sqlalchemy import Column, Integer, String, DateTime, JSON, func

from server.db.base import Base
from datetime import datetime, timezone, timedelta

def beijing_time():
    """
    返回当前北京时间
    """
    utc_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)

class ChatFeedbackModel(Base):
    """
    对话反馈模型
    """
    __tablename__ = 'chat_feedback'
    id = Column(Integer, primary_key=True, autoincrement=True,comment='反馈记录id')
    app_id = Column(Integer, comment='助手id')
    app_name = Column(String(256), comment='助手名称')
    kb_name = Column(String(50), comment='知识库名称')
    chat_session_id = Column(String(50), comment='对话记录id')
    chat_id = Column(String(50), comment='问答记录id')
    feedback_score = Column(Integer, default=0, comment='用户评分')
    feedback_reason = Column(String(4096), default="", comment='用户反馈答案')
    check_status = Column(String(10), default='待审核', comment='用户反馈审核状态')
    create_time = Column(DateTime(timezone=True), default=beijing_time, comment='创建时间')    
    user_email= Column(String(50), comment='用户邮箱')
    user_name = Column(String(50), comment='用户名')
    dep_id = Column(Integer, comment='部门id')
    meta_data = Column(JSON, default={})

    def __repr__(self):
        return f"<ChatHistory(id='{self.id}', app_id='{self.app_id}', app_name='{self.app_name}', kb_name='{self.kb_name}',chat_session_id='{self.chat_session_id}',chat_id='{self.chat_id}', feedback_score='{self.feedback_score}', feedback_reason='{self.feedback_reason}', check_status='{self.check_status}', create_time='{self.create_time}', user_email='{self.user_email}',user_name='{self.user_name}', dep_id='{self.dep_id}', meta_data='{self.meta_data}')>"

    def to_out_dict(self,is_detail=False):

        query = ""
        response = ""

        if is_detail:
            from server.db.repository.chat_history_repository import get_chat_history_by_id
            chat_history = get_chat_history_by_id(chat_session_id=self.chat_session_id,chat_history_id=self.chat_id)
            query = chat_history["data"].get("query")
            response = chat_history["data"].get("response")
        
        kb_name = self.kb_name
        if self.chat_session_id == self.kb_name:
            kb_name = "临时知识库"
            
        return {"id":self.id,
                "app_id":self.app_id,
                "app_name":self.app_name,
                "kb_name":kb_name,
                "chat_session_id":self.chat_session_id,
                "chat_id":self.chat_id,
                "query":query,
                "response":response,
                "feedback_score":self.feedback_score,
                "feedback_reason":self.feedback_reason,
                "check_status":self.check_status,
                "create_time":self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
                "user_email":self.user_email,
                "user_name":self.user_name,
                "dep_id":self.dep_id,
                "meta_data":self.meta_data,
                } 