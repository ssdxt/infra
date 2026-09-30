import openai
import json
from server.utils import BaseResponse
import openai
from server.db.repository.test_case_repository import test_case_add,test_case_update,test_case_list,test_case_delete,test_case_detail,get_file_test_case_count
from server.db.repository.course_repository import course_detail,course_update_ep_status
from server.http_api.user_api import token_check,is_super_admin,is_admin,admin_token_check
from pydantic import BaseModel
from fastapi import Body,Depends
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

class AddParams(BaseModel):
    question:str
    answer:str
    vs_id: str = None
    test_case_type:str = "生成试题"
    course_id:int =None
    question_type:str = "问答题"

def add_test_case(params:AddParams,current_user_dict=Depends(admin_token_check)):
    user =current_user_dict["user"]
    user_email = user["email"]
    db_obj = test_case_add(
                    question=params.question,
                    answer=params.answer,
                    vs_id=params.vs_id,
                    user_email = user_email,
                    test_case_type=params.test_case_type,
                    course_id=params.course_id,
                    question_type=params.question_type
                     )

    return BaseResponse(code = db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    pass

class UpdateParams(BaseModel):
    id:int
    question:str = None
    answer:str = None
    vs_id: str = None
    test_case_type:str = "生成试题"
    course_id:int = None
    question_type:str = None

def update_test_case(params:UpdateParams,current_user_dict=Depends(admin_token_check)):
    user =current_user_dict["user"]
    user_email = user["email"]
    db_obj = test_case_update(id=params.id,
                               question=params.question,
                               answer=params.answer,
                               vs_id=params.vs_id,
                               user_email=user_email,
                               test_case_type=params.test_case_type,
                               course_id=params.course_id,
                               question_type=params.question_type
                               )
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

class ListParams(BaseModel):
    question:str = None
    course_id:int = None
    vs_id:str = None
    test_case_type:str = None
    question_type:str = None
    page_no:int =1
    page_size:int =10

#列出当前文档的分开所有考题
#列出当前课程所有试题
#列出当前所有的 参考/生成 试题
def list_test_case(params:ListParams,user_dict= Depends(token_check)):
    page_start = (params.page_no-1) * params.page_size
    page_end = page_start+params.page_size
    db_obj = test_case_list(question=params.question,course_id=params.course_id,vs_id=params.vs_id,test_case_type=params.test_case_type,question_type=params.question_type,page_start=page_start,page_end=page_end)

    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse


class GetidParams(BaseModel):
    id:int
    question:str = None
    answer:str = None

from server.db.repository.test_case_repository import get_test_case_by_id
def get_test_case_id(params:GetidParams,user_dict= Depends(token_check)):

    db_obj = get_test_case_by_id(id=params.id)

    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse


import random
import pandas as pd
from server.db.repository.test_history_repository import test_history_list,test_history_suggestion
from server.db.repository.test_case_repository import test_case_list,get_tc_by_courseid
from server.db.repository.test_recommend_repository import comprehensive_recommendation_system
from server.db.repository.app_repository import app_detail

class GentpParams(BaseModel):
    course_id:int
    app_id:int

# 出题考试
def generate_test_paper(params: GentpParams, user_dict=Depends(token_check)):
    user = user_dict["user"]
    user_email = user["email"]

    app_info = app_detail(id=params.app_id,is_detail=False)
    train_num = app_info["data"].get("info", {}).get("trainNum")
    count = train_num
    
    try:
        test_cases = test_case_list(question=None, course_id=params.course_id, vs_id=None, test_case_type=None, question_type=None, page_start=None, page_end=None)["data"]["test_cases"]
        # 如果当前课程没有题目，返回空题目
        if not test_cases:
            return BaseResponse(code=200, msg="当前课程没有题目", data={})
        
        test_histories = test_history_list(eval_id=None, user_email=None)["data"]["test_historys"]

        test_case_data = pd.DataFrame([{
            'test_case_id': case.get("id"),
            'question': case.get("question"),
            'answer': case.get("answer"),
            'course_id': params.course_id,
            'question_type': case.get("question_type"),
            'create_time': case.get("create_time")
        } for case in test_cases])

        test_history_data = pd.DataFrame([{
            'history_id': history.get("id"),
            'test_case_id': history.get("test_case_id"),
            'result': history.get("result"),
            'score': history.get("score"),
            'consume_time': history.get("consume_time"),
            'user_email': history.get("user_email"),
            'eval_id': history.get("eval_id"),
            'eval_index': history.get("eval_index")
        } for history in test_histories])

    
        # 获取当前课程相关的所有题目 ID
        course_case_ids = test_case_data['test_case_id']

        # 检查是否有匹配的历史数据
        if test_history_data.empty or not course_case_ids.isin(test_history_data['test_case_id']).any():
            question_types = ['选择题', '判断题', '问答题']
            selected_questions = []
            missing_question_types = []
            # 如果没有匹配的历史数据，直接从题库中随机抽取题目
            for question_type in question_types:
                filtered_cases = test_case_data[test_case_data['question_type'] == question_type]

                # 如果某类题型题目数量不足，记录需要添加的题型信息
                if len(filtered_cases) < count:
                    missing_question_types.append({
                        "question_type": question_type,
                        "missing_count": count - len(filtered_cases)
                    })
                else:
                    sampled_cases = filtered_cases.sample(n=count, replace=False)
                    sampled_cases = sampled_cases.rename(columns={'test_case_id': 'id'}).drop(columns=['answer']).to_dict(orient='records')
                    selected_questions.extend(sampled_cases)

            # 如果有缺失题型信息
            if missing_question_types:
                return BaseResponse(
                    code=200, 
                    msg="题目不足", 
                    data={"missing_question_types": missing_question_types}
                )

            selected_questions = sorted(
                selected_questions,
                key=lambda x: question_types.index(x['question_type'])
            )

            return BaseResponse(code=200, msg="成功", data={"test_case": selected_questions})

        # 合并test_case和test_history表的数据
        merged_data = test_history_data.merge(test_case_data, on='test_case_id')
        question_types = ['选择题', '判断题', '问答题']
        recommended_questions = []
        missing_question_types = []

        # 使用推荐系统来生成试卷
        for question_type in question_types:

            filtered_cases = test_case_data[
                (test_case_data['course_id'] == params.course_id) &
                (test_case_data['question_type'] == question_type)
            ]

            recommendations = comprehensive_recommendation_system(
                user_email=user_email,
                course_id=params.course_id,
                num_questions=count,
                merged_data=merged_data,
                question_type=question_type,
                low_score_weight=0.4,
                long_time_weight=0.3,
                global_error_weight=0.3
            )

            if len(recommendations) < count:
                    recommended_ids = [r.get('test_case_id') for r in recommendations]
                    remaining_cases = filtered_cases[
                        ~filtered_cases['test_case_id'].isin(recommended_ids)
                    ]
                    num_needed = count - len(recommendations)
                
                    if not remaining_cases.empty:
                        additional_cases = remaining_cases.sample(
                            n=min(num_needed, len(remaining_cases)), replace=False
                        )
                        additional_cases = additional_cases.rename(
                            columns={'test_case_id': 'id'}
                        ).drop(columns=['answer']).to_dict(orient='records')
                        recommendations.extend(additional_cases)
            
            recommended_questions.extend([
                {k if k != 'test_case_id' else 'id': v for k, v in r.items()}
                for r in recommendations
            ])

        if missing_question_types:
            return BaseResponse(
                code=200,
                msg="题目不足",
                data={"missing_question_types": missing_question_types}
            )
        
        recommended_questions = sorted(
                recommended_questions,
                key=lambda x: question_types.index(x['question_type'])
            )
        return BaseResponse(code=200, msg="成功", data={"test_case": recommended_questions})
    # 如果发生异常，使用备用逻辑生成试卷
    except Exception as e:
        print(f"Error occurred: {e}. Falling back to alternative method.")

        # 获取所有试题和用户历史记录
        test = get_tc_by_courseid(course_id=params.course_id)["data"]
        history = test_history_suggestion(user_email=user_email, is_detail=False)["data"]

        # 从历史记录和试题中筛选出共有的 test_case_id
        history_test_case_ids = {item["test_case_id"] for item in history}
        test_case_ids = {item["id"] for item in test}
        common_test_case_ids = history_test_case_ids.intersection(test_case_ids)

        question_types = ['选择题', '判断题', '问答题']
        selected_questions = {q_type: [] for q_type in question_types}
        missing_question_types = []

        for question_type in question_types:
            # 筛选出当前题型的试题
            filtered_test = [
                item for item in test if item["question_type"] == question_type
            ]
            if common_test_case_ids:
                # 从历史中提取低分题目（score < 10）的记录
                low_score_questions = [
                    item for item in history
                    if item["test_case_id"] in common_test_case_ids and
                    item["score"] < 10 and
                    item["test_case_id"] in {t["id"] for t in filtered_test}
                ]

                # 随机选择30%低分题目
                selected_low_score_questions = random.sample(
                    low_score_questions,
                    min(count * 30 // 100, len(low_score_questions))
                )
                selected_low_score_question_ids = {
                    item["test_case_id"] for item in selected_low_score_questions
                }

                # 根据低分题目ID获取完整试题
                selected_low_score_questions = [
                    item for item in filtered_test if item["id"] in selected_low_score_question_ids
                ]

                # 剩余试题中随机补全题目
                remaining_test_questions = [
                    item for item in filtered_test if item["id"] not in selected_low_score_question_ids
                ]
                remaining_count = count - len(selected_low_score_questions)
                if remaining_count > len(remaining_test_questions):
                    remaining_questions = remaining_test_questions
                else:
                    remaining_questions = random.sample(remaining_test_questions, remaining_count)

                # 汇总当前题型的最终选择题目
                selected_questions[question_type] = selected_low_score_questions + remaining_questions

            else:
                # 如果没有低分题目记录，随机选择指定数量的试题
                selected_questions[question_type] = random.sample(
                    filtered_test, min(count, len(filtered_test))
                )

            # 如果当前题型题目不足，记录缺失信息
            if len(selected_questions[question_type]) < count:
                missing_question_types.append({
                    "question_type": question_type,
                    "missing_count": count - len(selected_questions[question_type])
                })

        # 如果存在缺失题型，返回缺失信息
        if missing_question_types:
            return BaseResponse(
                code=200,
                msg="题目不足",
                data={"missing_question_types": missing_question_types}
            )

        # 整理最终选择的题目并移除不需要的字段（如 answer）
        final_selected_questions = [
            {k: v for k, v in q.items() if k != "answer"}
            for q_type in question_types
            for q in selected_questions[q_type]
        ]

        return BaseResponse(code=200, msg="成功", data={"test_case": final_selected_questions})



class DetailParams(BaseModel):
        id:int

def detail_test_case(params:DetailParams):

    db_obj = test_case_detail(id=params.id)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse
    
class DeleteParams(BaseModel):
        ids: List[int]

def delete_test_case(params:DeleteParams,current_user_dict=Depends(admin_token_check)):

    failed_ids = []
    successful_ids = []

    for test_case_id in params.ids:
        db_obj = test_case_delete(id=test_case_id)

        if db_obj["code"] == 0:
            successful_ids.append(test_case_id)
        else:
            failed_ids.append(test_case_id)

    if failed_ids:
        return BaseResponse(code=-1,msg=f"部分试题删除失败,失败的ID: {failed_ids}",data={"failed_ids": failed_ids, "successful_ids": successful_ids})
    else:
        return BaseResponse(code=0, msg="所有试题已成功删除",data={"successful_ids": successful_ids})


from server.knowledge_base.kb_service.base import KBServiceFactory
from server.http_api.tools_api import generate_course_exam_chunk
from server.db.repository.knowledge_base_repository import load_kb_from_db_id
from server.db.repository.knowledge_file_repository import update_qa_count,update_qa_status

generate_status = {}
executor = ThreadPoolExecutor(max_workers=50)
class GenTestCasesParams(BaseModel):
    kb_name:str
    file_name:str 

#列出当前文档的分开所有考题
#列出当前课程所有试题
#列出当前所有的 参考/生成 试题
def generate_test_case_chunk(chunk, user_email):
    print(chunk)
    title = chunk.metadata.get("titles")
    content = chunk.page_content
    context = title + "\n" + content
    vs_id = chunk.metadata.get("vs_id")
    
    # 定义三种题目类型
    exam_types = ["选择题", "判断题", "问答题"]
    
    results = []
    
    # 为每种题目类型生成题目
    for exam_type in exam_types:
        qa_list = generate_course_exam_chunk(context, exam_type)
        
        if isinstance(qa_list, list) and len(qa_list) > 0:
            for qa in qa_list:
                if exam_type == "选择题":
                    question = qa["Question"]

                    if "\nA." not in question and "A." in question:
                        question = question.replace("A.", "\nA.")

                    if "\nB." not in question and "B." in question:
                        question = question.replace("B.", "\nB.")

                    if "\nC." not in question and "C." in question:
                        question = question.replace("C.", "\nC.")

                    if "\nD." not in question and "D." in question:
                        question = question.replace("D.", "\nD.")
                    
                    qa["Question"] = question

                result = test_case_add(
                    question=qa["Question"],
                    answer=qa["Answer"],
                    vs_id=vs_id,
                    user_email=user_email,
                    test_case_type="生成试题",
                    course_id=None,
                    question_type=exam_type
                )
                results.append(result)
    
    return results

def generate_test_cases(params:GenTestCasesParams, user_dict=Depends(token_check)):
    user = user_dict["user"]
    user_email = user["email"]

    kb_name = params.kb_name
    file_name = params.file_name

    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {kb_name}")
    
    update_qa_status(kb_name, file_name, "生成中")
    
    chunks = kb.list_docs(file_name)

    print(chunks)
    if chunks is None or len(chunks) == 0:
        update_qa_status(kb_name, file_name, "失败")
        return BaseResponse(code=500, msg=f"未找到文档块")
    
    if generate_status.get((kb_name, file_name), False):
        return BaseResponse(code=400, msg="正在生成试题，请稍后再试", data={})
    
    # 设置生成状态
    generate_status[(kb_name, file_name)] = True
    
    try:
        results = []
        for chunk in chunks:
            chunk_results = generate_test_case_chunk(chunk, user_email)
            results.extend(chunk_results if chunk_results else [])
        
        update_qa_status(kb_name, file_name, "已生成")
        
        count = get_file_test_case_count(kb_name, file_name)
        update_qa_count(kb_name, file_name, count)
        
        return BaseResponse(code=200, msg="试题生成完成", data={"count": count})
    except Exception as e:
        print(f"Error generating test cases: {e}")
        update_qa_status(kb_name, file_name, "失败")
        return BaseResponse(code=500, msg=f"生成试题失败: {str(e)}", data={})
    finally:
        generate_status[(kb_name, file_name)] = False


#后台是否在生成试题中
def generate_test_cases_status(params:GenTestCasesParams,user_dict= Depends(token_check)):
    kb_name = params.kb_name
    file_name = params.file_name
    status = generate_status.get((kb_name, file_name), False)
    response = BaseResponse(code=200, msg="Success", data={"status": status})
    return response

from server.db.repository.course_repository import course_update_exam,course_list_exam,course_update_exam_fields

class GenexamParams(BaseModel):
    course_id: int

def generate_exam_paper(params: GenexamParams, user_dict=Depends(token_check)):
    user = user_dict["user"]
    user_email = user["email"]

    choice_questions_data = test_case_list(
        question=None,
        course_id=params.course_id,
        vs_id=None,
        test_case_type=None,
        question_type="选择题",
        page_start=None,
        page_end=None
    )["data"]

    judgment_questions_data = test_case_list(
        question=None,
        course_id=params.course_id,
        vs_id=None,
        test_case_type=None,
        question_type="判断题",
        page_start=None,
        page_end=None
    )["data"]

    short_answer_questions_data = test_case_list(
        question=None,
        course_id=params.course_id,
        vs_id=None,
        test_case_type=None,
        question_type="问答题",
        page_start=None,
        page_end=None
    )["data"]

    if choice_questions_data["count"] < 20:
        return BaseResponse(code=400, msg="选择题数量不足", data={"可用的选择题数量": choice_questions_data["count"]})
    if judgment_questions_data["count"] < 10:
        return BaseResponse(code=400, msg="判断题数量不足", data={"可用的判断题数量": judgment_questions_data["count"]})
    if short_answer_questions_data["count"] < 5:
        return BaseResponse(code=400, msg="问答题数量不足", data={"可用的问答题数量": short_answer_questions_data["count"]})

    selected_choice_questions = random.sample(choice_questions_data["test_cases"], 20)
    selected_judgment_questions = random.sample(judgment_questions_data["test_cases"], 10)
    selected_short_answer_questions = random.sample(short_answer_questions_data["test_cases"], 5)

    selected_test_cases = selected_choice_questions + selected_judgment_questions + selected_short_answer_questions
    test_case_ids = [test_case["id"] for test_case in selected_test_cases]

    course_update_exam(params.course_id, {"exam_questions": test_case_ids,"exam_time": "1小时"})
    course_update_ep_status(id=params.course_id,exam_paper_status="已生成")
    return BaseResponse(code=200, msg="试卷生成成功", data={"exam_questions": test_case_ids})

class UpdateexamParams(BaseModel):
    course_id: int
    exam_questions: List[int] = None
    exam_time: str = None
    
def update_exam_paper(params: UpdateexamParams, user_dict=Depends(admin_token_check)):

    update_result = course_update_exam_fields(
        id=params.course_id,
        exam_questions=params.exam_questions,
        exam_time=params.exam_time
    )
    
    if update_result["code"] != 0:
        return BaseResponse(code=400, msg=update_result["msg"], data={})
    
    return BaseResponse(code=200, msg="试卷更新成功", data={})

class ListexamParams(BaseModel):
    course_id:int
    
def list_exam_paper(params: ListexamParams,user_dict= Depends(token_check)):
    user =user_dict["user"]

    if is_super_admin(user_dict=user_dict):
        # 超级管理员
        user_permission = True
    elif is_admin(user_dict=user_dict):
        # 普通管理员
        user_permission = True
    else:
        # 普通用户
        user_permission = False

    response = course_list_exam(params.course_id)

    if response["code"] == -1:
        return BaseResponse(code=400, msg="数据不存在", data={})
    elif response["code"] == 400:
        return BaseResponse(code=400, msg="试卷未生成", data={})

    exam_questions = response["data"]

    choice_questions = []
    true_or_false_questions = []
    subjective_questions = []

    for question_id in exam_questions:

        result = test_case_detail(id=question_id,is_detail=True)
        question_type = result["data"].get("question_type")

        if user_permission:
            exam_detail = {
                "test_case_id": question_id,
                "question_type":question_type,
                "question": result["data"].get("question"),
                "answer": result["data"].get("answer")
            }
        else:
            exam_detail = {
                "test_case_id": question_id,
                "question_type":question_type,
                "question": result["data"].get("question")
            }

        if question_type == "选择题":
            choice_questions.append(exam_detail)
        elif question_type == "判断题":
            true_or_false_questions.append(exam_detail)
        elif question_type == "问答题":
            subjective_questions.append(exam_detail)

    exam_details = choice_questions + true_or_false_questions + subjective_questions

    return BaseResponse(code=200, msg="试卷获取成功", data={"exam_details": exam_details})




