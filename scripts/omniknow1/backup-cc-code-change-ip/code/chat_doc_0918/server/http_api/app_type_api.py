import openai
import json
from server.utils import BaseResponse
import openai
from server.db.repository.app_type_repository import AppTypeModel,app_type_add,app_type_update,app_type_list,app_type_delete,app_type_detail
from server.http_api.user_api import token_check,admin_token_check,is_super_admin
from pydantic import BaseModel
from fastapi import Body,Depends

class AddAppTypeParams(BaseModel):
    name:str
    desc:str=None
    f_config: dict = {},
    b_config: dict = {},
    
def add_app_type(params:AddAppTypeParams,current_user_dict=Depends(admin_token_check)):
    db_obj = app_type_add(name=params.name,desc=params.desc,f_config=params.f_config,b_config=params.b_config)
    return BaseResponse(code = db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    pass

class UpdateAppTypeParams(BaseModel):
        id:int
        desc:str = None
        f_config:dict=None
        b_config:dict=None

def update_app_type(params:UpdateAppTypeParams,current_user_dict=Depends(admin_token_check)):
    db_obj = app_type_update(id=params.id,
                               desc=params.desc,
                               f_config=params.f_config,
                               b_config=params.b_config
                               )
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

    

def list_app_type(user_dict= Depends(token_check)):
    app_type_ids = None
    if not is_super_admin(user_dict=user_dict):
        user = user_dict["user"]
        dep_id = user.get("dep_id")
        if dep_id:
            from server.db.repository.department_repository import department_detail
            dep = department_detail(id=dep_id).get("data")
            if dep:
                app_type_ids =dep.get("app_type_ids")
    db_obj = app_type_list(app_type_ids=app_type_ids)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse


class DetailAppTypeParams(BaseModel):
        id:int

def detail_app_type(params:DetailAppTypeParams):
    db_obj = app_type_detail(id=params.id)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse
    
class DeleteAppTypeParams(BaseModel):
        id:int
def delete_app_type(params:DeleteAppTypeParams):
    db_obj = app_type_delete(id=params.id)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

    
