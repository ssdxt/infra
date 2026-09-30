from server.db.repository.chat_history_repository import feedback_chat_history_to_db,feedback_reason_in_db
from server.db.repository.user_info_repository import get_user
from server.utils import BaseResponse, ListResponse
from fastapi import Body,Form,Depends
from pydantic import Json
from server.http_api.user_api import token_check
from server.knowledge_base.kb_service.base import KBServiceFactory
from langchain.docstore.document import Document

__g_token_user_set ={}
def feedback_chat_history_to_db_api(
        session_id: str = Body(..., description="聊天窗口session id", examples=["samples"]),
        chat_id: str = Body(..., description="聊天对话chat_id", examples=["samples"]),
        feedback_score: int = Body(0, description="", examples=[0,1,...,9,10]),
        feedback_reason: str = Body(..., description="原因", examples=["test.txt"]),
        user_id: str = Body(None, description="user_id", examples=["samples"]),     
        user_dict = Depends(token_check)
) -> BaseResponse:
    
    user = user_dict["user"]
    user_email = user["email"]
    user_info = get_user(email=user_email, is_detail=True)
    user_id = user_info["data"].get("id")

    chat_history = feedback_reason_in_db(session_id=session_id,chat_history_id=chat_id, feedback_score=feedback_score, feedback_reason=feedback_reason,user_id=user_id)

    chat_data = chat_history["data"]

    query = chat_data.get("query")
    feedback_reason = chat_data.get("feedback_reason")
    combined_feedback = f"{query}\n{feedback_reason}"

    kb_name = chat_data.get("chat_type")

    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {kb_name}")

    document = Document(page_content=combined_feedback,metadata={"source": chat_id})
    
    qa = kb.add_qa(docs=[document])

    if qa:
        kb.save_vector_store()
        return BaseResponse(code=200, msg=f"反馈答案更新成功",data={})
    else:
        return BaseResponse(code=500, msg="知识库更新失败", data={})


# def  feedback_reason_to_db(
#         chat_id: str = Body(..., description="聊天对话chat_id", examples=["samples"]),
#         feedback_score: int = Body(-1, description="", examples=[0,1,...,9,10]),
#         feedback_reason: str = Body(..., description="答案反馈", examples=["test.txt"]),
#         user_dict = Depends(token_check)
# ) -> BaseResponse:

#     user = user_dict["user"]
#     user_email = user["email"]
#     user_info = get_user(email=user_email, is_detail=True)
#     user_id = user_info["data"].get("id")

#     chat_history = feedback_reason_in_db(chat_history_id=chat_id, feedback_score=feedback_score, feedback_reason=feedback_reason,user_id=user_id)

#     chat_data = chat_history["data"]

#     query = chat_data.get("query")
#     feedback_reason = chat_data.get("feedback_reason")
#     combined_feedback = f"{query}\n{feedback_reason}"

#     kb_name = chat_data.get("chat_type")

#     kb = KBServiceFactory.get_service_by_name(kb_name)
#     if kb is None:
#         return BaseResponse(code=404, msg=f"未找到知识库 {kb_name}")

#     document = Document(page_content=combined_feedback,metadata={"source": chat_id})
    
#     qa = kb.add_qa(docs=[document])

#     if qa:
#         kb.save_vector_store()
#         return BaseResponse(code=200, msg=f"反馈答案更新成功",data={})
#     else:
#         return BaseResponse(code=500, msg="知识库更新失败", data={})



# def register_test(
#         email:str = Body(..., examples=["samples"]),
#         username: str = Body(...,examples=["samples"]),
#         password: str = Body(...,examples=["samples"]),
#         role: int = Body(-1,examples=["test.txt"]),
#         info: Json = Form({}, examples=["samples"]),
# ) -> BaseResponse:
#     print("register test.....")
#     return BaseResponse(200,msg="test")