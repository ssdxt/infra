import openai
import json
from server.utils import BaseResponse
import openai
from server.db.repository.department_repository import DepartmentModel,department_add,department_update,department_list,department_delete,department_detail
from server.http_api.user_api import token_check
from pydantic import BaseModel
from fastapi import Body,Depends
from typing import Optional

class AddParams(BaseModel):
    name:str
    desc:str=None
    parent_id: int = None
    theme_color: str = None
    info:dict=None
    
def add_department(params:AddParams):
    db_obj = department_add(name=params.name,desc=params.desc,parent_id=params.parent_id,theme_color=params.theme_color,info=params.info)
    return BaseResponse(code = db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    pass

class UpdateParams(BaseModel):
        id:int
        name:str
        desc:str = None
        parent_id:int=None
        app_type_ids:list=None
        theme_color:str = None
        info:dict=None

def update_department(params:UpdateParams):
    db_obj = department_update(id=params.id,
                               name = params.name,
                               desc = params.desc,
                               parent_id=params.parent_id,
                               app_type_ids=params.app_type_ids,
                               theme_color=params.theme_color,
                               info=params.info
                               )
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

    

class ListParams(BaseModel):
        dep_name: str = None
        page_no:int =1
        page_size:int =10

def list_department(params: Optional[ListParams] = Body(None),current_user_dict=Depends(token_check)):
    current_user = current_user_dict["user"]
    current_email = current_user["email"]
    c_dep_id = current_user["dep_id"]
    role = current_user["role"]
    dep_id = c_dep_id
    
    page_no = params.page_no if params else 1
    page_size = params.page_size if params else 10
    dep_name = params.dep_name if params else None

    page_start = (page_no - 1) * page_size
    page_end = page_start + page_size

    if role == 1 :
        dep_id = None
    

    db_obj = department_list(id=dep_id,name=dep_name,page_start=page_start,page_end=page_end)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse


class DetailParams(BaseModel):
        id:int

def detail_department(params:DetailParams):
    db_obj = department_detail(id=params.id)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse
    
class DeleteParams(BaseModel):
        id:int
def delete_department(params:DeleteParams):
    db_obj = department_delete(id=params.id)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

    
