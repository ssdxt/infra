import openai
import json
from server.utils import BaseResponse
import openai
from server.db.repository.course_eval_history_repository import course_eval_history_add,course_eval_history_update,course_eval_history_list,course_eval_history_delete,course_eval_history_detail
from server.http_api.user_api import token_check,is_super_admin,admin_token_check,is_admin
from pydantic import BaseModel
from fastapi import Body,Depends
from typing import List

class AddParams(BaseModel):
    course_id:int
    score: int = None
    eval_type: str
    
def add_course_eval(params:AddParams,current_user_dict=Depends(token_check)):
    user = current_user_dict["user"]
    email = user.get("email")
    dep_id = user.get("dep_id")
    db_obj = course_eval_history_add(
                    user_email=email,
                    course_id = params.course_id,
                    dep_id=dep_id,
                    eval_type=params.eval_type,
                    score=params.score
                     )
    return BaseResponse(code = db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    pass

class UpdateParams(BaseModel):
    id:int
    course_id:int = None
    score: int = None
    eval_type: str = None

def update_course_eval(params:UpdateParams,current_user_dict=Depends(token_check)):
    user = current_user_dict["user"]
    email = user.get("email")
    dep_id = user.get("dep_id")
    db_obj = course_eval_history_update(
        id=params.id,
        user_email=email,
        course_id=params.course_id,
        score=params.score,
        dep_id=dep_id,
        eval_type=params.eval_type
        )
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse
    

class ListParams(BaseModel):
    course_id:int=None
    eval_type:str=None
    page_no:int =1
    page_size:int =10


# 超管，列出所有的考试记录
# 管理员，列出当前部门的（某项）考试记录
# 普通用户，当前用户的考试记录
def list_course_eval(params:ListParams,current_user_dict= Depends(token_check)):
    user =current_user_dict["user"]
    user_email = None
    dep_id = None
    if is_super_admin(user_dict= current_user_dict):
        #超管
        dep_id = None
    elif is_admin(user_dict= current_user_dict):
        #普通管理员
        dep_id = user["dep_id"]
    else:
        #普通用户
        dep_id = user["dep_id"]
        user_email = user["email"]
    page_start = (params.page_no-1) * params.page_size
    page_end = page_start+params.page_size    
    db_obj = course_eval_history_list(dep_id=dep_id,course_id=params.course_id,user_email=user_email,eval_type=params.eval_type,page_start=page_start,page_end=page_end)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse
    pass

class DetailParams(BaseModel):
        id:int

def detail_course_eval(params:DetailParams):

    db_obj = course_eval_history_detail(id=params.id)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

from server.db.repository.test_history_repository import test_history_delete

class DeleteParams(BaseModel):
        ids: List[int]
def delete_course_eval(params:DeleteParams,current_user_dict=Depends(admin_token_check)):
    for course_eval_id in params.ids:
        test_history_delete(eval_id=course_eval_id)
        db_obj = course_eval_history_delete(id=course_eval_id)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse


from server.db.repository.course_repository import student_list_course


def list_student_profile(current_user_dict=Depends(token_check)):
    user = current_user_dict["user"]
    email = user.get("email")
    dep_id = user.get("dep_id")

    # 获取课程数量
    course_count = student_list_course(dep_id)

    # 获取测试次数和平均分
    test_results = course_eval_history_list(dep_id=None, course_id=None, user_email=email, eval_type="培训考核", page_start=None, page_end=None)
    test_count = test_results["data"]["count"]

    # 计算测试平均分
    test_total_score = sum(eval_history["score"] for eval_history in test_results["data"]["course_evals"] if eval_history["score"] is not None)
    test_avg_score = round(test_total_score / test_count, 2) if test_count > 0 else 0

    # 获取考试次数和平均分
    exam_results = course_eval_history_list(dep_id=None, course_id=None, user_email=email, eval_type="规定考试", page_start=None, page_end=None)
    exam_count = exam_results["data"]["count"]

    # 计算考试平均分
    exam_total_score = sum(eval_history["score"] for eval_history in exam_results["data"]["course_evals"] if eval_history["score"] is not None)
    exam_avg_score = round(exam_total_score / exam_count, 2) if exam_count > 0 else 0

    # 统计有考核记录的课程数量
    all_evals = test_results["data"]["course_evals"] + exam_results["data"]["course_evals"]
    course_ids_with_evals = {eval_history["course_id"] for eval_history in all_evals if eval_history["course_id"] is not None}
    course_with_evals_count = len(course_ids_with_evals)

    profile_data = {
        "course_count": course_count,
        "course_with_evals_count": course_with_evals_count,
        "test_count": test_count,
        "exam_count": exam_count,
        "test_avg_score": test_avg_score,
        "exam_avg_score": exam_avg_score,
    }

    return BaseResponse(code=0, msg="成功", data=profile_data)


from server.db.repository.test_history_repository import test_history_list
from server.db.repository.test_case_repository import test_case_detail
from server.db.repository.app_repository import app_detail

class CalculateParams(BaseModel):
        eval_id:int
        eval_type:str
        app_id:int = None

def calculate_score(params:CalculateParams):
    # Step 1: 获取所有相关的历史记录
    test_history_data = test_history_list(eval_id=params.eval_id,user_email=None)
    
    if test_history_data['code'] != 0:
        return {"code": 1, "msg": "获取考核记录失败"}
    
    test_historys = test_history_data['data']['test_historys']
    
    # Step 2: 提取每个题目的question_type 和 score
    question_type_count = {"选择题": 0, "判断题": 0, "问答题": 0}
    question_scores = {"选择题": 0, "判断题": 0, "问答题": 0}
    
    for record in test_historys:
        test_case_id = record['test_case_id']
        test_case_detail_data = test_case_detail(id=test_case_id,is_detail=True)
        
        if test_case_detail_data['code'] != 0:
            return {"code": 400, "msg": "试题信息有误"}
        
        test_case_detail_info = test_case_detail_data['data']
        question_type = test_case_detail_info['question_type']
        score = float(record['score'])
        
        # 根据题目类型分类统计
        if question_type == "选择题":
            question_type_count["选择题"] += 1
            question_scores["选择题"] += score
        elif question_type == "判断题":
            question_type_count["判断题"] += 1
            question_scores["判断题"] += score
        elif question_type == "问答题":
            question_type_count["问答题"] += 1
            question_scores["问答题"] += score

    # Step 3: 根据考核类型计算得分
    if params.eval_type == "规定考试":
        # 固定题目数量
        required_counts = {"选择题": 20, "判断题": 10, "问答题": 5}
        score_per_question = {"选择题": 2, "判断题": 1, "问答题": 10}
        total_possible_score = 20 * 2 + 10 * 1 + 5 * 10
        total_obtained_score = 0

        # 计算各题型的得分
        for q_type in required_counts:
            required_count = required_counts[q_type]
            actual_count = question_type_count[q_type]
            per_question_score = score_per_question[q_type] / 100

            if actual_count > 0:
                # 如果做了题目，按比例计算得分
                obtained_score = question_scores[q_type] * per_question_score
                if actual_count >= required_count:
                    total_obtained_score += obtained_score / actual_count * required_count
                else:
                    total_obtained_score += obtained_score
            # 如果题目数量少于要求，未做的题目得 0 分
        final_score = round((total_obtained_score / total_possible_score) * 100, 2)
        return {"code": 0, "msg": "成功", "data": {"score": final_score}}

    elif params.eval_type == "培训考核":
        app_info = app_detail(id=params.app_id,is_detail=False)
        train_num = app_info["data"].get("info", {}).get("trainNum")
        total_count = train_num*3
        total_score = 0
        for q_type in question_scores:
            total_score += question_scores[q_type]
        
        # 如果没有做题，得分为 0
        if sum(question_type_count.values()) == 0:
            return {"code": 0, "msg": "成功", "data": {"score": 0}}
        
        # 计算平均分
        average_score = round(total_score / total_count, 2)
        return {"code": 0, "msg": "成功", "data": {"score": average_score}}

    return {"code": -1, "msg": "未知的考核类型"}
