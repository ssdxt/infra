import openai
import json
from server.utils import BaseResponse
import openai
from server.db.repository.course_repository import course_add,course_update,course_list,course_delete,course_detail
from server.http_api.user_api import token_check,is_super_admin,admin_token_check,is_admin
from server.db.repository.test_case_repository import test_case_list
from pydantic import BaseModel
from fastapi import Body,Depends
from typing import List
from fastapi import File,UploadFile
import os
from PIL import Image

# class AddParams(BaseModel):
#     name:str
#     desc:str = None
#     job_title: str = None,
#     kb_id: int
#     file_name:str
#     abstract:str = None
#     activate:bool = True
    
# def add_course(params:AddParams,
#                current_user_dict=Depends(admin_token_check),
#                cover_image: UploadFile = File(None, description="课程封面图片")):
    
#     user =current_user_dict["user"]
#     user_email=user["email"]
#     dep_id = user["dep_id"]
    
#     if cover_image:
#         project_root = os.getcwd()
#         cover_dir = os.path.join(project_root, "course_img")
#         if not os.path.exists(cover_dir):
#             os.makedirs(cover_dir)
        
#         cover_filename = f"{params.name}.jpg"
#         file_location = os.path.join(cover_dir, cover_filename)
#         with Image.open(cover_image.file) as img:
#             img = img.convert("RGB")
#             img.save(file_location, format="JPEG")
        

#     db_obj = course_add(
#                      name=params.name,
#                      desc=params.desc,
#                      job_title=params.job_title,
#                      kb_id=params.kb_id,
#                      file_name=params.file_name,
#                      user_email=user_email,
#                      abstract=params.abstract,
#                      activate=params.activate,
#                      dep_id=dep_id
#                      )
#     return BaseResponse(code = db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
#     pass

def add_course(
        name: str = Body(..., description="课程名称"),
        desc: str = Body(None, description="课程描述"),
        job_title = Body(..., description="岗位"),
        kb_id: int = Body(..., description="知识库id"),
        file_name: str = Body(..., description="课程文件名称"),
        abstract: str = Body(None, description="课程摘要"),
        activate: bool = Body(True, description="课程状态"),
        dep_id: int = Body(None, description="部门id"),
        current_user_dict=Depends(admin_token_check),
        cover_image: UploadFile = File(None, description="课程封面图片")):
    
    user =current_user_dict["user"]
    user_email=user["email"]
    user_dep_id = user["dep_id"]
    
    if is_super_admin(user_dict=current_user_dict):
        dep_id = dep_id
    else:
        dep_id = user_dep_id

    if cover_image:
        project_root = os.getcwd()
        cover_dir = os.path.join(project_root, "course_img")
        if not os.path.exists(cover_dir):
            os.makedirs(cover_dir)
        
        cover_filename = f"{dep_id}_{name}.jpg"
        file_location = os.path.join(cover_dir, cover_filename)
        with Image.open(cover_image.file) as img:
            img = img.convert("RGB")
            img.save(file_location, format="JPEG")
        

    db_obj = course_add(
                     name=str(name),
                     desc=desc,
                     job_title=job_title,
                     kb_id=kb_id,
                     file_name=file_name,
                     user_email=user_email,
                     abstract=abstract,
                     activate=activate,
                     dep_id=dep_id
                     )
    return BaseResponse(code = db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    pass
        
def update_course(
        id: int = Body(..., description="知识库id"),
        name: str = Body(None, description="课程名称"),
        desc: str = Body(None, description="课程描述"),
        job_title = Body(None, description="岗位"),
        kb_id: int = Body(None, description="知识库id"),
        file_name: str = Body(None, description="课程文件名称"),
        abstract: str = Body(None, description="课程摘要"),
        activate: bool = Body(None, description="课程状态"),
        dep_id: int = Body(None, description="部门id"),
        current_user_dict=Depends(admin_token_check),
        cover_image: UploadFile = File(None, description="课程封面图片")):
    
    user =current_user_dict["user"]
    user_email=user["email"]

    course_info = course_detail(id=id,is_detail=False)
    old_name = course_info["data"].get("name")
    old_dep_id = course_info["data"].get("dep_id")

    db_obj = course_update(id=id,
                            name=name,
                            desc=desc,
                            job_title=job_title,
                            kb_id=kb_id,
                            file_name=file_name,
                            user_email=user_email,
                            abstract=abstract,
                            activate=activate,
                            dep_id=dep_id
                               )
    
    course_info = course_detail(id=id,is_detail=False)
    update_name = course_info["data"].get("name")
    update_dep_id = course_info["data"].get("dep_id")

    project_root = os.getcwd()
    cover_dir = os.path.join(project_root, "course_img")

    old_filename = f"{old_dep_id}_{old_name}.jpg"
    cover_filename = f"{update_dep_id}_{update_name}.jpg"

    if cover_image is None:

        old_cover_file_path = os.path.join(cover_dir, old_filename)
        new_cover_file_path = os.path.join(cover_dir, cover_filename)

        if os.path.exists(old_cover_file_path):
            os.rename(old_cover_file_path, new_cover_file_path)

    if cover_image:
        if not os.path.exists(cover_dir):
            os.makedirs(cover_dir)
        
        file_location = os.path.join(cover_dir, cover_filename)
        with Image.open(cover_image.file) as img:
            img = img.convert("RGB")
            img.save(file_location, format="JPEG")

        if old_filename != cover_filename:
            old_file_location = os.path.join(cover_dir, old_filename)
            if os.path.exists(old_file_location):
                os.remove(old_file_location)    
    
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse
    

#根据课程类型，课程名字搜索所有课程
class ListParams(BaseModel):
    name:str = None
    job_title:str = None
    app_id:str = None
    page_no:int =1
    page_size:int =10

def list_course(params:ListParams,user_dict= Depends(token_check)):
    user =user_dict["user"]

    user_permission = False
    
    if is_super_admin(user_dict=user_dict):
        dep_id = None
        user_permission = True
    elif is_admin(user_dict= user_dict):
        #普通管理员
        dep_id = user["dep_id"]
        user_permission = True
    else:
        #普通用户
        dep_id = user["dep_id"]

    page_start = (params.page_no - 1) * params.page_size
    page_end = page_start + params.page_size
    db_obj = course_list(dep_id=dep_id,name=params.name,job_title=params.job_title,user_permission=user_permission,app_id=params.app_id,page_start=page_start,page_end=page_end)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse


class DetailParams(BaseModel):
        id:int

def detail_course(params:DetailParams):
    db_obj = course_detail(id=params.id)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse
    
from server.db.repository.course_eval_history_repository import course_eval_history_list

class DeleteParams(BaseModel):
    ids: List[int]

def delete_course(params: DeleteParams, user_dict= Depends(token_check)):
    user =user_dict["user"]  
    if is_super_admin(user_dict=user_dict):
        dep_id = None
    elif is_admin(user_dict= user_dict):
        #普通管理员
        dep_id = user["dep_id"]
    else:
        #普通用户
        dep_id = user["dep_id"]

    failed_deletions = []
    successful_deletions = []
    
    for course_id in params.ids:
        # db_obj = course_detail(id=course_id)
        # if db_obj is None:
        #     return {"code":-1,"msg":"删除的课程已经不存在","data":{}}
        # 获取与课程关联的题目
        test_cases = test_case_list(question=None, course_id=course_id, vs_id=None, test_case_type=None, question_type=None, page_start=None, page_end=None)["data"].get("test_cases")
        
        # 如果没有关联的题目，直接删除课程
        if not test_cases:
            db_obj = course_delete(id=course_id)
            successful_deletions.append(course_id)
            continue

        # 获取与课程相关的考核记录
        course_eval_histories = course_eval_history_list(dep_id=dep_id,course_id=course_id,user_email= None,page_start=None,page_end=None)["data"]["course_evals"]
        
        # 如果有考核记录，无法删除课程
        if course_eval_histories:
            failed_deletions.append(course_id)
            continue

        # 删除课程
        db_obj = course_delete(id=course_id)
        successful_deletions.append(course_id)
    
    # 根据删除结果返回响应
    if failed_deletions:
        return BaseResponse(code=0, msg="部分课程有关联的考核记录，不能删除", data={
            "成功删除的课程": successful_deletions,
            "无法删除的课程": failed_deletions
        })
    else:
        return BaseResponse(code=db_obj["code"], msg=db_obj["msg"], data=db_obj["data"])

