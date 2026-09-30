import openai
import json
from server.utils import BaseResponse
import openai
from server.db.repository.chat_history_repository import delete_chat_session
from server.http_api.user_api import token_check,is_super_admin,admin_token_check
from pydantic import BaseModel
from fastapi import Body,Depends
from typing import List
from server.db.repository.knowledge_base_repository import check_temp_kb
import uuid
from server.knowledge_base.kb_api import delete_temp_kb
from server.knowledge_base.kb_service.base import KBServiceFactory
import threading
from threading import Timer, Event
from datetime import datetime, timedelta

class DeleteParams(BaseModel):
    chat_session_id: str

def chat_session_delete(params: DeleteParams,current_user_dict=Depends(token_check)):
    
    kb = KBServiceFactory.get_service_by_name(params.chat_session_id)
    print(kb)
    if kb:
        delete_temp_kb(kb_names=[params.chat_session_id])

    delete_chat_session(chat_session_id=params.chat_session_id)

    return BaseResponse(code=200, msg="窗口删除成功", data={})

# def temp_kb_check(user_dict=Depends(token_check)):
#     user=user_dict["user"]
#     user_email=user["email"]

#     expired_kb_names = check_temp_kb(user_email=user_email)
#     if expired_kb_names:
#         delete_temp_kb(kb_names=expired_kb_names)
#         return BaseResponse(code=200, msg="过期临时知识库删除成功", data={})

#     else:
#         return BaseResponse(code=200, msg="暂无过期临时知识库", data={})
    

stop_event = Event()
cleanup_timer = None

def clear_temp_kb():
    if stop_event.is_set():
        return
        
    expired_kb_names = check_temp_kb()
    print(expired_kb_names)
    if expired_kb_names:
        delete_temp_kb(kb_names=expired_kb_names)
        print("过期临时知识库删除成功")
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    global cleanup_timer
    if not stop_event.is_set():
        cleanup_timer = Timer(86400, clear_temp_kb)
        cleanup_timer.daemon = True
        cleanup_timer.start()

cleanup_timer = Timer(86400, clear_temp_kb)
cleanup_timer.daemon = True
cleanup_timer.start()

def stop_cleanup_timer():
    stop_event.set()
    if cleanup_timer:
        cleanup_timer.cancel()


