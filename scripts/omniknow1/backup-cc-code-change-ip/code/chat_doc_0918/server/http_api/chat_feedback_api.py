from tkinter import FALSE
import openai
import json
from server.utils import BaseResponse
import openai
from server.db.repository.chat_feedback_repository import chat_feedback_add,chat_feedback_update,chat_feedback_delete,chat_feedback_list,chat_feedback_detail,chat_feedback_check
from server.http_api.user_api import token_check,is_super_admin,admin_token_check
from pydantic import BaseModel,Json
from fastapi import Body,Depends
from typing import List
from server.knowledge_base.kb_doc_api import search_feedback_docs
from fastapi import Form, File, UploadFile
from typing import Optional
import os
import shutil
from urllib.parse import urlencode
# class AddFeedbackParams(BaseModel):
#     app_id:int
#     app_name:str
#     kb_name:str
#     chat_session_id:str
#     chat_id:str
#     feedback_score:int
#     feedback_reason:str
    
def add_chat_feedback(
    app_id: int = Form(..., description="助手ID"),
    app_name: str = Form(..., description="助手名称"),
    kb_name: str = Form(..., description="知识库名称"),
    chat_session_id: str = Form(..., description="对话记录ID"),
    chat_id: str = Form(..., description="问答记录ID"),
    feedback_score: int = Form(..., description="用户评分"),
    feedback_reason: str = Form(..., description="用户反馈答案"),
    files: Optional[List[UploadFile]] = File(None, description="上传的文件，支持多文件"),
    current_user_dict=Depends(token_check)
):
    user =current_user_dict["user"]
    user_email=user["email"]
    dep_id = user["dep_id"]
    user_name = user["username"]

    image_files = []
    video_files = []
    meta_data = {}
    
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.tiff'}
    video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v', '.3gp'}
    
    if files and files[0] is not None:
        project_root = os.getcwd()
        
        feedback_dir = os.path.join(project_root, "feedback_files", chat_session_id, chat_id)
        if not os.path.exists(feedback_dir):
            os.makedirs(feedback_dir)
        
        for file in files:
            if file.filename:
                file_location = os.path.join(feedback_dir, file.filename)
                
                with open(file_location, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                file_location_relative = os.path.join("feedback_files", chat_session_id, chat_id, file.filename)
                
                _file_filename = os.path.basename(file_location)
                _file_url_request_parameters = urlencode({"filepath": file_location_relative, "filename": _file_filename})
                _file_url = f"knowledge_base/download_file?" + _file_url_request_parameters
                
                file_ext = os.path.splitext(file.filename)[1].lower()
                file_info = {file.filename: _file_url}
                
                if file_ext in image_extensions:
                    image_files.append(file_info)
                elif file_ext in video_extensions:
                    video_files.append(file_info)

        meta_data = {
            "images": image_files,
            "videos": video_files
        }

    db_obj = chat_feedback_add(app_id=app_id,
                     app_name=app_name,
                     kb_name=kb_name,
                     chat_session_id=chat_session_id,
                     chat_id=chat_id,
                     feedback_score=feedback_score,
                     feedback_reason=feedback_reason,
                     user_email = user_email,
                     user_name = user_name,
                     dep_id=dep_id,
                     meta_data=meta_data
                     )
    
    return BaseResponse(code = db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])

# class UpdateFeedbackParams(BaseModel):
#         id:int
#         feedback_reason:str

def update_chat_feedback(
    id: int = Form(..., description="反馈记录ID"),
    feedback_reason: str = Form(..., description="用户反馈答案"),
    chat_session_id: str = Form(..., description="对话记录ID"),
    chat_id: str = Form(..., description="问答记录ID"),
    meta_data: Json = Form({}, description="绑定文件信息"),
    delete_files: Optional[List[str]] = Form(None, description="要删除的文件名列表"),
    files: Optional[List[UploadFile]] = File(None, description="上传的新文件，支持多文件"),
    current_user_dict=Depends(admin_token_check)
):
    project_root = os.getcwd()
    feedback_dir = os.path.join(project_root, "feedback_files", chat_session_id, chat_id)
    
    # 获取当前的 meta_data，如果传入的 meta_data 为空则使用现有的
    current_meta_data = dict(meta_data) if meta_data else {"images": [], "videos": []}
    
    # 处理文件删除
    if delete_files:
        current_images = current_meta_data.get("images", [])
        current_videos = current_meta_data.get("videos", [])
        
        # 从文件系统删除文件
        for filename in delete_files:
            file_path = os.path.join(feedback_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # 从 meta_data 中移除删除的文件
        current_images = [img for img in current_images if list(img.keys())[0] not in delete_files]
        current_videos = [vid for vid in current_videos if list(vid.keys())[0] not in delete_files]
        
        current_meta_data["images"] = current_images
        current_meta_data["videos"] = current_videos
    
    # 处理新文件上传（复用 add_chat_feedback 的逻辑）
    if files and files[0] is not None:
        if not os.path.exists(feedback_dir):
            os.makedirs(feedback_dir)
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.tiff'}
        video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v', '.3gp'}
        
        new_images = current_meta_data.get("images", [])
        new_videos = current_meta_data.get("videos", [])
        
        for file in files:
            if file.filename:
                file_location = os.path.join(feedback_dir, file.filename)
                
                # 保存文件（如果同名文件存在则覆盖）
                with open(file_location, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                
                # 构建文件URL（与 add_chat_feedback 相同的逻辑）
                file_location_relative = os.path.join("feedback_files", chat_session_id, chat_id, file.filename)
                _file_filename = os.path.basename(file_location)
                _file_url_request_parameters = urlencode({"filepath": file_location_relative, "filename": _file_filename})
                _file_url = f"knowledge_base/download_file?" + _file_url_request_parameters
                
                file_ext = os.path.splitext(file.filename)[1].lower()
                file_info = {file.filename: _file_url}
                
                # 检查是否已存在同名文件，如果存在则替换
                if file_ext in image_extensions:
                    # 移除同名的图片文件
                    new_images = [img for img in new_images if list(img.keys())[0] != file.filename]
                    new_images.append(file_info)
                elif file_ext in video_extensions:
                    # 移除同名的视频文件
                    new_videos = [vid for vid in new_videos if list(vid.keys())[0] != file.filename]
                    new_videos.append(file_info)
        
        current_meta_data["images"] = new_images
        current_meta_data["videos"] = new_videos
    
    # 更新反馈记录
    db_obj = chat_feedback_update(
        id=id,
        feedback_reason=feedback_reason,
        meta_data=current_meta_data
    )
    
    return BaseResponse(code=db_obj["code"], msg=db_obj["msg"], data=db_obj["data"])

class ListFeedbackParams(BaseModel):
        id:int=None
        check_status:str=None
        page_no:int =1
        page_size:int =10

def list_chat_feedback(params:ListFeedbackParams,user_dict= Depends(admin_token_check)):
    user =user_dict["user"]
    dep_id = user["dep_id"]

    if is_super_admin(user_dict=user_dict):
        dep_id = None
    
    page_start = (params.page_no-1) * params.page_size
    page_end = page_start+params.page_size
    
    db_obj = chat_feedback_list(dep_id=dep_id,id=params.id,check_status=params.check_status,page_start=page_start,page_end=page_end)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

class DeleteFeedbackParams(BaseModel):
        ids: List[int]

def delete_chat_feedback(params:DeleteFeedbackParams,current_user_dict=Depends(admin_token_check)):

    failed_ids = []
    successful_ids = []

    for feedback_id in params.ids:
        db_obj = chat_feedback_delete(id=feedback_id)

        if db_obj["code"] == 0:
            successful_ids.append(feedback_id)
        else:
            failed_ids.append(feedback_id)

    if failed_ids:
        return BaseResponse(code=-1,msg=f"部分反馈记录删除失败,失败的ID: {failed_ids}",data={"failed_ids": failed_ids, "successful_ids": successful_ids})
    else:
        return BaseResponse(code=0, msg="所有反馈记录已成功删除",data={"successful_ids": successful_ids})

class DetailFeedbackParams(BaseModel):
        id:int

def detail_chat_feedback(params: DetailFeedbackParams):
    db_obj = chat_feedback_detail(id=params.id)
    if db_obj["code"] == -1:
        return BaseResponse(code=db_obj["code"], msg=db_obj["msg"], data=db_obj["data"])
    
    kb_name = db_obj["data"].get("kb_name")
    query = db_obj["data"].get("query")

    search_result = search_feedback_docs(
        query=query, 
        kb_name=kb_name, 
        feedback_source_id=params.id,
        top_k=8, 
        score_threshold=0.5,
        include_self=FALSE
    )
    search_result_data = search_result.data

    search_result_dict = []
    for doc in search_result_data:
        doc_dict = {
            "page_content": doc.page_content,
            "metadata": doc.metadata,
            "score": doc.score
        }
        search_result_dict.append(doc_dict)

    combined_data = {
        "feedback": db_obj["data"],
        "search_result": search_result_dict
    }
    
    return BaseResponse(code=0, msg="反馈详情获取成功", data=combined_data)

class CheckFeedbackParams(BaseModel):
        id:int
        check_status:str
        query:str

def check_chat_feedback(params:CheckFeedbackParams):

    db_obj = chat_feedback_check(id=params.id,check_status=params.check_status,query=params.query)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

