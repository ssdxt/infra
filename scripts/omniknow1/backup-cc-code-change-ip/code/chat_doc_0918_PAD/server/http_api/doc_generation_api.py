from server.db.repository.doc_history_repository import DocHistoryModel,doc_history_add,doc_history_list,doc_history_detail,doc_history_delete
from server.db.repository.doc_template_repository import DocTemplateModel,doc_template_add,doc_template_update,doc_template_delete,doc_template_detail,doc_template_list,doc_template_count_plus1
from http_api.user_api import token_check,admin_token_check,is_super_admin,is_admin
from server.utils import BaseResponse, ListResponse
from fastapi import Body,UploadFile,File,Form,Request,Response,Depends,Header,HTTPException,status
from datetime import datetime,timedelta
from typing import Optional
from pydantic import Json
import time
from pydantic import BaseModel
import os
from typing import List
import uuid


class DocTemplateAdd(BaseModel):
    name:str
    desc:str = None
    role: str = None
    fromat_req: str = None
    generate_info:list = None
    info:dict =None

#注册用户

def add_doc_template(params:DocTemplateAdd,current_user_dict=Depends(token_check)
) -> BaseResponse:
    
    current_user = current_user_dict["user"]
    current_email = current_user["email"]
    dep_id = current_user["dep_id"]
    print(">>>>>",dep_id)
    
    db_obj = doc_template_add(name=params.name,
                             desc=params.desc,
                             role=params.role,
                             fromat_req=params.fromat_req,
                             user_email=current_email,
                             dep_id=dep_id,
                             generate_info=params.generate_info,
                             info=params.info)
    print("add_doctemplate",db_obj)
    if db_obj["code"] >=0:
        response = BaseResponse(code=200, msg=f"更新成功",data=db_obj["data"])
        return response
    else :
        return BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data={})

    
class DocTemplateUpdate(BaseModel):
    id:int
    name:str = None
    desc:str = None
    role: str = None
    fromat_req: str = None
    generate_info:list = None
    count:int = None
    info:dict =None
    dep_id:int = None
    
def update_doc_template(params:DocTemplateUpdate,current_user_dict=Depends(token_check)
) -> BaseResponse:
    
    db_obj = doc_template_update(id=params.id,
                                name=params.name,
                                desc=params.desc,
                                role=params.role,
                                fromat_req=params.fromat_req,
                                count=params.count,
                                dep_id=params.dep_id,
                                generate_info=params.generate_info,
                                info=params.info
                                )
    if db_obj["code"] >=0:
        db_obj = db_obj["data"]
        response = BaseResponse(code=200, msg=f"更新成功",data={"role":db_obj})
        return response
    else :
        return BaseResponse(code=db_obj["code"] ,msg=db_obj["msg"],data={})

class DocTemplateList(BaseModel):
    name:str = None
    page_no:int = 1
    page_size:int = 20
      
def list_doc_template(params:DocTemplateList,current_user_dict=Depends(token_check)
) -> BaseResponse:
    
    current_user = current_user_dict["user"]
    current_email = current_user["email"]
    role = current_user["role"]
    dep_id = current_user["dep_id"]
    if role  == 1:
        #全部用户
        dep_id = None
    page_start = (params.page_no-1) * params.page_size
    page_end = page_start+params.page_size
        
    db_obj = doc_template_list(dep_id=dep_id,name=params.name,page_start=page_start,page_end=page_end)
    if db_obj["code"] >=0:
        response = BaseResponse(code=200, msg=f"更新成功",data=db_obj["data"])
        return response
    else :
        return BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data={})
    

class DeleteDocTemplateModel(BaseModel):
    id:int

def detail_doc_template(params:DeleteDocTemplateModel,current_user_dict=Depends(token_check)
) -> BaseResponse:
    db_obj = doc_template_detail(id= params.id)
    if db_obj["code"] >=0:
        response = BaseResponse(code=200, msg=f"更新成功",data=db_obj["data"])
        return response
    else :
        return BaseResponse(code=db_obj["code"] ,msg=db_obj["msg"],data={})

def delete_doc_template(params:DeleteDocTemplateModel,current_user_dict=Depends(token_check)
) -> BaseResponse:
    
    current_user = current_user_dict["user"]
    current_email = current_user["email"]
    role = current_user["role"]
    
    db_obj = doc_template_delete(id=params.id)
    if db_obj["code"] ==0:
        response = BaseResponse(code=200, msg=f"更新成功",data=db_obj["data"])
        return response
    else :
        return BaseResponse(code=db_obj["code"] ,msg=db_obj["msg"],data={})


#历史

def add_doc_history(
                    name:str=Form(...,examples=["samples"]),
                    desc:str=Form("",examples=["samples"]),
                    doc_template_id:int=Form(..., examples=["samples"]),
                    kb_ids :Json = Form([],examples=[]),
                    keywords:Json = Form({},examples=[]),
                    content:str = Form("",examples=[]),
                    file:UploadFile = File(..., description="上传文件，支持多文件"),
                    doc_ref:Json = Form({},examples=[]),
                    info:Json = Form({},examples=[]),
                    current_user_dict=Depends(token_check)
) -> BaseResponse:
    
    current_user = current_user_dict["user"]
    current_email = current_user["email"]
    dep_id = current_user["dep_id"]

    file_name = name+".docx"
    
    file_path_dir = "output/generate_files/"+current_email
    
    if not os.path.exists(file_path_dir):
        os.mkdir(file_path_dir)
    
    file_uuid = str(uuid.uuid4())
    actual_file_name = f"{name}_{file_uuid}.docx"
    file_path = file_path_dir + "/" + actual_file_name

    db_obj = doc_history_add(name=name,
                             desc= desc,
                             doc_template_id = doc_template_id,
                             kb_ids=kb_ids,
                             keywords=keywords,
                             content=content,
                             user_email=current_email,
                             file_name=file_name,
                             file_path=file_path,
                             dep_id=dep_id,
                             doc_ref=doc_ref,                             
                             info=info)
    
    
    if db_obj["code"] >=0:
        with open(file_path, "wb") as f:
            f.write(file.file.read())
        
        doc_template_count_plus1(id=doc_template_id)
        
        response = BaseResponse(code=200, msg=f"更新成功",data=db_obj["data"])
        return response
    else :
        return BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data={})

class DocHistoryList(BaseModel):
    
    page_no:int = 1
    page_size:int = 10
    
def list_doc_history(params:DocHistoryList,user_dict=Depends(token_check)
) -> BaseResponse:
    user = user_dict["user"]
    email = user["email"]
    dep_id = user["dep_id"]
    
    if is_super_admin(user_dict=user_dict):
        dep_id = None
        email = None
    elif is_admin(user_dict=user_dict):
        email = None
    page_start = (params.page_no-1) * params.page_size
    page_end = page_start + params.page_size

    db_obj = doc_history_list(dep_id,email,page_start=page_start,page_end=page_end)
    if db_obj["code"] >=0:
        response = BaseResponse(code=200, msg=f"查询成功",data=db_obj["data"])
        return response
    else :
        return BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data={})

class DocHistoryDetail(BaseModel):
    id:int

def detail_doc_history(params:DocHistoryDetail,current_user_dict=Depends(token_check)
) -> BaseResponse:
    db_obj = doc_history_detail(id= params.id)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse
    
class DeleteParams(BaseModel):
        ids: List[int]

def delete_doc_history(params:DeleteParams,current_user_dict=Depends(token_check)):

    failed_ids = []
    successful_ids = []

    for id in params.ids:
        db_obj = doc_history_delete(id=id)

        if db_obj["code"] == 0:
            successful_ids.append(id)
        else:
            failed_ids.append(id)

    if failed_ids:
        return BaseResponse(code=-1,msg=f"部分试题删除失败,失败的ID: {failed_ids}",data={"failed_ids": failed_ids, "successful_ids": successful_ids})
    else:
        return BaseResponse(code=0, msg="所有试题已成功删除",data={"successful_ids": successful_ids})