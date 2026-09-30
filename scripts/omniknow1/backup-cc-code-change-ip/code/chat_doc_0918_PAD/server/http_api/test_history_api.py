import openai
import json
from server.utils import BaseResponse
import openai
from server.db.repository.test_history_repository import test_history_add,test_history_update,test_history_list,test_history_delete,test_history_detail,test_history_suggestion
from server.http_api.user_api import token_check,is_super_admin,admin_token_check
from pydantic import BaseModel
from fastapi import Body,Depends
from server.db.repository.test_case_repository import test_case_detail
from server.http_api.tools_api import generate_train_proposal

class AddParams(BaseModel):
    test_case_id:int
    result:str
    score:int
    consume_time:int
    eval_id:int
    eval_index:int
    
def add_test_history(params:AddParams,current_user_dict=Depends(token_check)):
    user =current_user_dict["user"]
    user_email = user["email"]
    db_obj = test_history_add(test_case_id=params.test_case_id,
                     result=params.result,
                     score=params.score,
                     consume_time=params.consume_time,
                     user_email=user_email,
                     eval_id=params.eval_id,
                     eval_index=params.eval_index
                     )
    return BaseResponse(code = db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    pass

class UpdateParams(BaseModel):
        id:int
        test_case_id:int = None
        result:str = None
        score:int = None
        consume_time:int = None
        eval_id:int = None

def update_test_history(params:UpdateParams,current_user_dict=Depends(admin_token_check)):
    
    db_obj = test_history_update(id=params.id,
                        test_case_id=params.test_case_id,
                        result=params.result,
                        score=params.score,
                        consume_time=params.consume_time,
                        user_email=None,
                        eval_id=params.eval_id,  
                               )
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse

    
class ListParams(BaseModel):
    eval_id:int = None
    user_email:str = None
#查询当前用户某次测试详细情况
#查询某个用户某次测试详细情况
def list_test_history(params:ListParams,user_dict= Depends(token_check)):
    user =user_dict["user"]
    user_email = None
    if is_super_admin(user_dict=user_dict):
        if params.user_email is not None:
            user_email = params.user_email
    db_obj = test_history_list(eval_id=params.eval_id,user_email=user_email)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse


class DetailParams(BaseModel):
    id:int

def detail_test_history(params:DetailParams):

    db_obj = test_history_detail(id=params.id)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse
    
class DeleteParams(BaseModel):
    eval_id:int
def delete_test_history(params:DeleteParams,current_user_dict=Depends(admin_token_check)):
    db_obj = test_history_delete(eval_id=params.eval_id)
    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse


class GensgTestHistoryParams(BaseModel): 
    user_email: str

def generate_suggestion_test_history(params:GensgTestHistoryParams,user_dict= Depends(token_check)):
    user =user_dict["user"]
    user_email=user["email"]

    test = test_history_suggestion(user_email=params.user_email, is_detail=False)["data"]

    lowest_tests = sorted(test, key=lambda x: x['score'])[:5]

    test_case_ids = [test['test_case_id'] for test in lowest_tests]
    
    exam_result = ""
    for test, test_case_id in zip(lowest_tests, test_case_ids):
        test_case = test_case_detail(id=test_case_id, is_detail=False)["data"]
        if test_case:
            course_id = test_case["course_id"]
            question = test_case["question"]
            exam_result += f"题目: {question}, 课程ID: {course_id}, 得分: {test['score']}\n"
    # print(f"{exam_result}")

    proposal_result = generate_train_proposal(exam_result)

    return BaseResponse(code=200, msg="查询成功", data=proposal_result)

from server.db.repository.course_repository import course_detail
from server.knowledge_base.kb_doc_api import list_doc_block
from server.db.repository.knowledge_file_repository import get_filedoc_by_doc_id
from server.knowledge_base.kb_service.base import KBServiceFactory

class GenReferencesTestHistoryParams(BaseModel): 
    user_email: str

def generate_reference_test_history(params:GenReferencesTestHistoryParams,user_dict= Depends(token_check)):
    user=user_dict["user"]
    user_email=user["email"]
    # 查询该用户做题记录
    test = test_history_suggestion(user_email=params.user_email, is_detail=True)["data"]
    # 找出分数最低的5个
    # lowest_tests = sorted(test, key=lambda x: x['score'])[:5]
    # test_case_ids = [test['test_case_id'] for test in lowest_tests]
    lowest_tests = sorted(test, key=lambda x: x['score'])
    test_case_ids = [test['test_case_id'] for test in lowest_tests]
    
    reference = ""
    cnt = 0
    all_reference_tests = True
    for test, test_case_id in zip(lowest_tests, test_case_ids):
        test_case = test_case_detail(id=test_case_id, is_detail=False)["data"]
        test_case_type = test_case["test_case_type"]
        if test_case_type != "参考试题":
            all_reference_tests = False

        question = test_case["question"]
        print(f"题目: {question}")
        if test_case:
            # 获取试题的课程id和chunk_id
            vs_id = test_case["vs_id"]
            test_case_type = test_case["test_case_type"]
            if test_case_type == "参考试题":
                continue

            doc = get_filedoc_by_doc_id(vs_id)
            kb_name = doc['data'].get('kb_name')
            file_name = doc['data'].get('file_name')
            
            # 根据知识库查chunk页码
            kb = KBServiceFactory.get_service_by_name(kb_name)
            docs = kb.list_docs(file_name)
            # docs = list_doc_block(kb_name=kb_name, file_name=file_name)["data"]
            for doc in docs:
                # print(doc)
                # print(kb_name,file_name,"doc.metadata.get()",doc.metadata.get("vs_id"),vs_id)
                if doc and doc.metadata.get("vs_id") == vs_id:
                    page_no = [] 
                    cnt += 1
                    if cnt > 6:
                        break
                    # print(f"题目: {question}, {file_name}, {vs_id}\n")           
                    reference += "{} ".format(file_name)
                    for content in doc.metadata.get("content_pos"):
                        page_no.append(content["page_no"])
                    if len(page_no)<2:
                        reference += "第{}页 \n".format(page_no[0])
                    else:
                        reference += "第{}页~".format(page_no[0])
                        reference += "第{}页 \n".format(page_no[-1])
            if cnt > 6:
                break

    if all_reference_tests:
        return BaseResponse(code=200, msg="请咨询管理员参考内部题库", data="请咨询管理员参考内部题库")
    
    print(reference)
    if reference != "":
        reference_lines = reference.split('\n')
        reference_lines = [line.strip() for line in reference_lines if line.strip()]
        seen = set()
        unique_references = []

        for line in reference_lines:
            if line not in seen:
                unique_references.append(line)
                seen.add(line)
        reference = '\n'.join(unique_references)
        return BaseResponse(code=200, msg="参考资料生成成功", data=reference)
    else:
        return BaseResponse(code=200, msg="没有培训记录，生成失败", data={})



class ListevaltcParams(BaseModel):
    eval_id:int

def list_eval_test_case(params:ListevaltcParams):
    history_data = test_history_list(eval_id=params.eval_id,user_email=None)
    if history_data["code"] != 0:
        return {"code": -1, "msg": "无法获取历史做题信息", "data": {}}

    test_histories = history_data["data"]["test_historys"]
    combined_results = []

    for history in test_histories:
        test_case_id = history.get("test_case_id")
        eval_index = history.get("eval_index")
        result = history.get("result")

        test_case_data = test_case_detail(id=test_case_id, is_detail=True)
        if test_case_data["code"] != 0:
            return {"code": -1, "msg": f"无法获取试题详细信息，test_case_id: {test_case_id}", "data": {}}
        
        test_case = test_case_data["data"]
        question = test_case.get("question")
        answer = test_case.get("answer")
        question_type = test_case.get("question_type")
        
        combined_result = {
            "test_case_id": test_case_id,
            "result": result,
            "eval_index": eval_index,
            "question": question,
            "answer": answer,
            "question_type": question_type,
        }
        combined_results.append(combined_result)

    combined_results = sorted(combined_results, key=lambda x: x["eval_index"])
    return {"code": 0, "msg": "成功", "data": combined_results}
        