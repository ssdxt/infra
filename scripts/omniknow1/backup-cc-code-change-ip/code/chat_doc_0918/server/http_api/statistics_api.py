import openai
import json
from server.utils import BaseResponse
import openai
from server.db.repository.test_case_repository import test_case_add,test_case_update,test_case_list,test_case_delete,test_case_detail
from server.db.repository.statistics_repository import statistics_all,statistics_user,statistics_test_case,statistics_app,statistics_knowledge,statistics_course,statistics_doc,statistics_job_title
from server.http_api.user_api import token_check,is_super_admin,admin_token_check
from pydantic import BaseModel
from fastapi import Body,Depends
from concurrent.futures import ThreadPoolExecutor, as_completed

class StaticsticsParams(BaseModel):
    dep_id:int = None

#列出当前文档的分开所有考题
#列出当前课程所有试题
#列出当前所有的 参考/生成 试题
def knowledge_statistic(params:StaticsticsParams,user_dict= Depends(token_check)):
    user =user_dict["user"]
    dep_id=user["dep_id"]
    if is_super_admin(user_dict):
        dep_id = None
        if params.dep_id is not None:
            dep_id = params.dep_id
    result = statistics_knowledge(dep_id=dep_id)
    reponse = BaseResponse(code=result["code"],msg=result["msg"],data=result["data"])
    return reponse


#列出当前文档的分开所有考题
#列出当前课程所有试题
#列出当前所有的 参考/生成 试题
def all_statistic(params:StaticsticsParams,user_dict= Depends(token_check)):
    user =user_dict["user"]
    dep_id=user["dep_id"]
    if is_super_admin(user_dict):
        dep_id = None
        if params.dep_id is not None:
            dep_id = params.dep_id
    result = statistics_all(dep_id=dep_id)
    reponse = BaseResponse(code=result["code"],msg=result["msg"],data=result["data"])
    return reponse


def user_statistic(params:StaticsticsParams,user_dict= Depends(token_check)):
    user =user_dict["user"]
    dep_id=user["dep_id"]
    
    if is_super_admin(user_dict):
        dep_id = None
        if params.dep_id is not None:
            dep_id = params.dep_id
            
    result = statistics_user(dep_id=dep_id)
    print("result",result)
    reponse = BaseResponse(code=result["code"],msg=result["msg"],data=result["data"])
    # reponse = BaseResponse(code=0,msg="xxxx",data={})
    return reponse


def doc_statistic(params:StaticsticsParams,user_dict= Depends(token_check)):
    user =user_dict["user"]
    dep_id=user["dep_id"]
    if is_super_admin(user_dict):
        dep_id = None
        if params.dep_id is not None:
            dep_id = params.dep_id
    result = statistics_doc(dep_id=dep_id)
    reponse = BaseResponse(code=result["code"],msg=result["msg"],data=result["data"])
    return reponse

def app_statistic(params:StaticsticsParams,user_dict= Depends(token_check)):
    user =user_dict["user"]
    dep_id=user["dep_id"]
    if is_super_admin(user_dict):
        dep_id = None
        if params.dep_id is not None:
            dep_id = params.dep_id
    result = statistics_app(dep_id=dep_id)
    reponse = BaseResponse(code=result["code"],msg=result["msg"],data=result["data"])
    return reponse



def course_statistic(params:StaticsticsParams,user_dict= Depends(token_check)):
    user =user_dict["user"]
    dep_id=user["dep_id"]
    if is_super_admin(user_dict):
        dep_id = None
        if params.dep_id is not None:
            dep_id = params.dep_id
    result = statistics_course(dep_id=dep_id)
    reponse = BaseResponse(code=result["code"],msg=result["msg"],data=result["data"])
    return reponse

def test_case_statistic(params:StaticsticsParams,user_dict= Depends(token_check)):
    user =user_dict["user"]
    dep_id=user["dep_id"]
    if is_super_admin(user_dict):
        dep_id = None
        if params.dep_id is not None:
            dep_id = params.dep_id
    result = statistics_test_case(dep_id=dep_id)
    reponse = BaseResponse(code=result["code"],msg=result["msg"],data=result["data"])
    return reponse

def job_title_statistic(params:StaticsticsParams,user_dict= Depends(token_check)):
    user =user_dict["user"]
    dep_id=user["dep_id"]
    if is_super_admin(user_dict):
        dep_id = None
        if params.dep_id is not None:
            dep_id = params.dep_id
    result = statistics_job_title(dep_id=dep_id)
    reponse = BaseResponse(code=result["code"],msg=result["msg"],data=result["data"])
    return reponse