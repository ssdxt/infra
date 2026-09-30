import openai
import json
from server.utils import BaseResponse
import openai
from server.db.repository.test_record_repository import test_record_add,test_record_update,test_record_list,check_test_record
from server.db.repository.course_repository import course_detail
from server.http_api.user_api import token_check,is_super_admin,admin_token_check
from pydantic import BaseModel
from fastapi import Body,Depends
from concurrent.futures import ThreadPoolExecutor, as_completed

class UpdateParams(BaseModel):
    user_email:str
    suggestion:str
    reference:str

def update_test_record(params: UpdateParams, current_user_dict=Depends(token_check)):
    user = current_user_dict["user"]
    user_email = user["email"]
    
    record_exists = check_test_record(user_email=params.user_email)
    
    if record_exists:
        db_obj = test_record_update(
            user_email=params.user_email,
            suggestion=params.suggestion,
            reference=params.reference
            )
    else:
        db_obj = test_record_add(
            user_email=params.user_email,
            suggestion=params.suggestion,
            reference=params.reference
            )
    
    response = BaseResponse(code=db_obj["code"], msg=db_obj["msg"], data=db_obj["data"])
    return response

class ListParams(BaseModel):
    user_email:str

def list_test_record(params: ListParams, current_user_dict=Depends(token_check)):

    db_obj = test_record_list(user_email=params.user_email)

    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse