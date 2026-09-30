import openai
import json
from server.utils import BaseResponse
import openai
from server.db.repository.app_repository import app_add,app_update,app_list,app_delete,app_detail,app_token_save,specific_app_list,app_logo_update
from server.http_api.user_api import token_check,is_super_admin,admin_token_check
from pydantic import BaseModel,Json
from fastapi import Body,Depends
from fastapi import Form,File,UploadFile
import os
import shutil
from urllib.parse import urlencode
from typing import List
from PIL import Image
    
class AddAppParams(BaseModel):
    name: str
    desc: str = None
    kb_ids: List
    assistant_type: str
    hi: str = None
    questions: list = None
    dep_id: int = None
    digital_human: str = "无"
    digital_human_voice: str = "无"
    url: str = None
    activate: bool = True
    info: dict = {}

def add_app(params:AddAppParams,current_user_dict=Depends(admin_token_check)):
    
    user =current_user_dict["user"]
    user_email=user["email"]
    dep_id = user["dep_id"]

    llm_model = "cc-13b-5"

    if params.dep_id:
         dep_id = params.dep_id


    db_obj = app_add(type_id=1,
                     name=params.name,
                     desc=params.desc,
                     kb_ids=params.kb_ids,
                     assistant_type=params.assistant_type,
                     hi=params.hi,
                     questions=params.questions,
                     dep_id=dep_id,
                     digital_human=params.digital_human,
                     digital_human_voice=params.digital_human_voice,
                     llm_model=llm_model,
                     url=params.url,
                     activate=params.activate,
                     info=params.info,
                     user_email=user_email
                     )
    return BaseResponse(code = db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])

class UpdateAppParams(BaseModel):
        id: int
        name: str = None
        desc: str = None
        kb_ids: List = None
        assistant_type: str = None
        hi: str = None
        questions: list = None
        dep_id: int = None
        digital_human: str = None
        digital_human_voice: str = None
        llm_model: str = None
        url: str = None
        activate: bool = None
        info: dict = None

def update_app(params:UpdateAppParams,current_user_dict=Depends(admin_token_check)):
    
    user =current_user_dict["user"]
    user_email=user["email"]
    dep_id = user["dep_id"]

    if params.dep_id:
         dep_id = params.dep_id

    db_obj = app_update(id=params.id,
                        name=params.name,
                        desc=params.desc,
                        kb_ids=params.kb_ids,
                        assistant_type=params.assistant_type,
                        hi=params.hi,
                        questions=params.questions,
                        dep_id=dep_id,
                        digital_human=params.digital_human,
                        digital_human_voice=params.digital_human_voice,
                        llm_model= params.llm_model,
                        url=params.url,
                        activate=params.activate,
                        info = params.info,
                        user_email=user_email
                        )
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

class ListParams(BaseModel):
        name:str = None
        page_no:int =1
        page_size:int =10
        assistant:bool = True

def list_app(params:ListParams,user_dict= Depends(token_check)):
    user =user_dict["user"]
    dep_id = user["dep_id"]

    if is_super_admin(user_dict=user_dict):
        dep_id = None
    
    page_start = (params.page_no-1) * params.page_size
    page_end = page_start+params.page_size
    
    db_obj = app_list(dep_id=dep_id,name=params.name,assistant=params.assistant,page_start=page_start,page_end=page_end)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

from typing import Optional
from fastapi import Header,Request,Response


class DetailAppParams(BaseModel):
        id:int
        access_token: Optional[str] = None

def detail_app(params:DetailAppParams,token: Optional[str] = Header(None)):
    role = 3
    if not params.access_token:
        current_user_dict = token_check(request=Request,response=Response,token=token)
        if not current_user_dict:
            return BaseResponse(code=-1, msg="请校验身份", data={})
        current_user = current_user_dict["user"]
        role = current_user["role"]

    db_obj = app_detail(id=params.id,role=role)

    if db_obj["code"] != 0:
        return BaseResponse(code=db_obj["code"], msg=db_obj["msg"], data={})
    
    if params.access_token:
        stored_access_token = db_obj["data"].get("info", {}).get("access_token")
        if stored_access_token != params.access_token:
            return BaseResponse(code=-1, msg="校验失败", data={})

    response = BaseResponse(code=db_obj["code"], msg=db_obj["msg"], data=db_obj["data"])
    return response

def app_logo(
    id: int = Body(..., description="应用id"),
    file: UploadFile = File(..., description="上传文件"),
) -> BaseResponse:

    project_root = os.getcwd()

    logo_dir = os.path.join(project_root, "app_logo", str(id))

    if os.path.exists(logo_dir):
        for filename in os.listdir(logo_dir):
            file_path = os.path.join(logo_dir, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
    else:
        os.makedirs(logo_dir)

    file_location = os.path.join(logo_dir, file.filename)
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    _image_filename = os.path.basename(file_location)
    file_location_relative = os.path.join("app_logo", str(id), file.filename)
    _image_url_request_parameters = urlencode({"filepath": file_location_relative, "filename": _image_filename})
    _image_url = f"knowledge_base/download_img?" + _image_url_request_parameters

    db_obj = app_logo_update(id=id,app_logo=_image_url)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

class DeleteAppParams(BaseModel):
        id:int
def delete_app(params:DeleteAppParams,current_user_dict=Depends(admin_token_check)):
    db_obj = app_delete(id=params.id)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

import uuid
import base64

class CreateApptokenParams(BaseModel):
        id:int

def create_app_token(params:CreateApptokenParams,current_user_dict=Depends(admin_token_check)):

    user =current_user_dict["user"]
    user_email=user["email"]
    dep_id = user["dep_id"]
    
    token_id = uuid.uuid4()
    access_token = base64.b32encode(token_id.bytes).decode('utf-8').rstrip('=')
    db_obj=app_token_save(id=params.id,access_token=access_token,user_email=user_email)
    
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse
    

def list_specific_app(user_dict= Depends(admin_token_check)):
    user =user_dict["user"]
    user_email=user["email"]
    dep_id = user["dep_id"]

    if is_super_admin(user_dict=user_dict):
        dep_id = None
    
    db_obj = specific_app_list(dep_id=dep_id)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

def update_specific_app(
        id: int = Body(..., description="应用id"),
        kb_ids: List[int] = Body(None, description="知识库id"),
        trainNum: int = Body(1, description="培训题目数量"),
        greet: str = Body(None, description="培训招呼"),
        current_user_dict=Depends(admin_token_check)):
    
    user =current_user_dict["user"]
    user_email=user["email"]
    dep_id = user["dep_id"]

    info = {
        "trainNum": trainNum,
        "greet": greet if greet else "您好，同学，今天也要好好学习啊。"
    }

    db_obj = app_update(id=id,
                        kb_ids=kb_ids,
                        info = info
                        )
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse
