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

class ChatHistoryModel(Base):
    """
    聊天记录模型
    """
    __tablename__ = 'chat_history'
    # 由前端生成的uuid，如果是自增的话，则需要将id 传给前端，这在流式返回里有点麻烦
    id = Column(String(32), primary_key=True, comment='聊天记录ID')
    # chat/agent_chat等
    chat_type = Column(String(50), comment='聊天类型')
    query = Column(String(4096), comment='用户问题')
    response = Column(String(4096), comment='模型回答')
    # 记录知识库id等，以便后续扩展
    meta_data = Column(JSON, default={})
    # 满分100 越高表示评价越好
    feedback_score = Column(Integer, default=-1, comment='用户评分')
    feedback_reason = Column(String(255), default="", comment='用户反馈答案')
    create_time = Column(DateTime(timezone=True), default=beijing_time, comment='创建时间')
    chat_session_id= Column(String(50), comment='聊天session')
    user_id= Column(String(50), comment='用户id')
    context= Column(String(4096), comment='知识库的上下文')

    def __repr__(self):
        return f"<ChatHistory(id='{self.id}', chat_type='{self.chat_type}', query='{self.query}', response='{self.response}',meta_data='{self.meta_data}',feedback_score='{self.feedback_score}', feedback_reason='{self.feedback_reason}', create_time='{self.create_time}',chat_session_id='{self.chat_session_id}', user_id='{self.user_id}', context='{self.context}')>"

    def to_out_dict(self):
        return {"id":self.id,
                "chat_type":self.chat_type,
                "query":self.query,
                "response":self.response,
                "meta_data":self.meta_data,
                "feedback_score":self.feedback_score,
                "feedback_reason":self.feedback_reason,
                "create_time":self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else "",
                "chat_session_id":self.chat_session_id,
                "user_id":self.user_id,
                "context":self.context
                } 