import urllib
import sys
# print(sys.path)
sys.path.append('/mnt/ddata/chat_doc')
from server.utils import BaseResponse, ListResponse
from server.knowledge_base.utils import validate_kb_name
from server.knowledge_base.kb_service.base import KBServiceFactory
from server.db.repository.knowledge_base_repository import kb_list,kb_detail
from configs import EMBEDDING_MODEL, logger, log_verbose
from fastapi import Body,Form,Request,Response,Depends,Header,HTTPException,status
import glob
from langchain.vectorstores.faiss import FAISS
import os
from tqdm import tqdm
from server.embeddings_api import embed_documents
import csv
import json
from server.utils import gen_question,run_in_thread_pool
import subprocess
from server.http_api.user_api import token_check,admin_token_check,is_super_admin
from server.db.repository.user_info_repository import get_user
from pydantic import BaseModel
from langchain.embeddings.huggingface import HuggingFaceEmbeddings
import torch,gc
from server.db.repository.knowledge_file_repository import delete_tc_by_kbfile

class ListParams(BaseModel):
        dep_id:int = None
        kb_name:str = None
        page_no:int =1
        page_size:int =10

def list_kbs(params:ListParams,current_user_dict = Depends(token_check)):
    current_user = current_user_dict["user"]
    current_email = current_user["email"]
    dep_id = current_user["dep_id"]
    role = current_user["role"]

    if role > 2 :
        kb_type = "个人"
        create_user_email = current_email
    else:
        if role == 1:
            dep_id = None
        kb_type = "单位"
        create_user_email = None
    # dep_id = current_user_dict["user"].get("dep_id")
    #超管的话以用户参数为第一优先级
    # if is_super_admin(current_user_dict):
    #     if params.dep_id is not None:
    #         dep_id = params.dep_id
    #     else:
    #         dep_id = None
    
    page_start = (params.page_no - 1) * params.page_size
    page_end = page_start + params.page_size
    db_obj = kb_list(dep_id=dep_id,kb_name=params.kb_name,kb_type=kb_type,create_user_email=create_user_email,page_start=page_start,page_end=page_end)

    reponse = BaseResponse(code=db_obj["code"],msg=db_obj["msg"],data=db_obj["data"])
    return reponse


class AddParams(BaseModel):
        kb_name:str
        kb_info:str = None
        
def create_kb(params:AddParams,
            current_user_dict = Depends(token_check)
            ) -> BaseResponse:

    current_user = current_user_dict["user"]
    current_email = current_user["email"]
    dep_id = current_user["dep_id"]
    role = current_user["role"]

    if role > 2 :
        kb_type = "个人"
    else:
        kb_type = "单位"

    create_user_email = current_email

    vector_store_type = "faiss"
    embed_model = EMBEDDING_MODEL
    
    if not validate_kb_name(params.kb_name):
        return BaseResponse(code=403, msg="Don't attack me")
    if params.kb_name is None or params.kb_name.strip() == "":
        return BaseResponse(code=404, msg="知识库名称不能为空，请重新填写知识库名称")

    kb = KBServiceFactory.get_service_by_name(params.kb_name)
    if kb is not None:
        return BaseResponse(code=404, msg=f"已存在同名知识库 {params.kb_name}")

    kb = KBServiceFactory.get_service(params.kb_name, vector_store_type, embed_model)
    
    # create_user_email = current_user_dict["user"].get("email")
    # dep_id = current_user_dict["user"].get("dep_id")
    try:
        if params.kb_info:
            kb.kb_info = params.kb_info
        kb.create_user_email = create_user_email 
        kb.dep_id = dep_id
        result = kb.create_kb(kb_type=kb_type)
        return BaseResponse(code=200, msg=f"成功 {params.kb_name}",data=result["data"])
    except Exception as e:
        msg = f"创建知识库出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)

class UpdateParams(BaseModel):
        kb_name:str
        kb_info:str = None
        dep_id:int = None

def update_kb(
            params:UpdateParams,
            current_user_dict = Depends(admin_token_check) 
            ) -> BaseResponse:
    
    vector_store_type = "faiss"
    embed_model = EMBEDDING_MODEL

    if not validate_kb_name(params.kb_name):
        return BaseResponse(code=403, msg="Don't attack me")
    if params.kb_name is None or params.kb_name.strip() == "":
        return BaseResponse(code=404, msg="知识库名称不能为空，请重新填写知识库名称")

    kb = KBServiceFactory.get_service_by_name(params.kb_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"该知识 {params.kb_name} 不存在")

    kb = KBServiceFactory.get_service(params.kb_name, vector_store_type, embed_model)
    try:
        if params.kb_info:
            kb.kb_info = params.kb_info
        if params.dep_id:
            kb.dep_id = params.dep_id
        result = kb.update_kb()
        return BaseResponse(code=200, msg=f"成功 {params.kb_name}",data=result["data"])
    except Exception as e:
        msg = f"创建知识库出错： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)

from typing import List

class DeleteParams(BaseModel):
        kb_names: List[str]
        
def delete_kb(
    params:DeleteParams,
    current_user_dict = Depends(admin_token_check) 
    ) -> BaseResponse:

    results = []
    # Delete selected knowledge base
    for kb_name in params.kb_names:
        if not validate_kb_name(kb_name):
            results.append({"kb_name": kb_name, "status": "failed", "reason": "Invalid name"})
            continue
    # if not validate_kb_name(params.kb_name):
    #     return BaseResponse(code=403, msg="Don't attack me")
        kb_name = urllib.parse.unquote(kb_name)
        kb = KBServiceFactory.get_service_by_name(kb_name)

        if kb is None:
            results.append({"kb_name": kb_name, "status": "failed", "reason": f"未找到知识库 {kb_name}"})
            continue
            # return BaseResponse(code=404, msg=f"未找到知识库 {params.kb_name}")

        try:
            delete_tc_by_kbfile(kb_name)
            status = kb.clear_vs()
            status = kb.drop_kb()
            if status:
                results.append({"kb_name": kb_name, "status": "success"})
            else:
                results.append({"kb_name": kb_name, "status": "failed", "reason": "Unknown error during deletion"})
                # return BaseResponse(code=200, msg=f"成功删除知识库 {params.kb_name}")
        except Exception as e:
            msg = f"删除知识库时出现意外： {e}"
            logger.error(f'{e.__class__.__name__}: {msg}',
                        exc_info=e if log_verbose else None)
            results.append({"kb_name": kb_name, "status": "failed", "reason": str(e)})
            # return BaseResponse(code=500, msg=msg)
    success_count = len([r for r in results if r["status"] == "success"])

    return BaseResponse(
        code=200 if success_count > 0 else 500,
        msg=f"批量删除完成，成功 {success_count} 项，失败 {len(results) - success_count} 项",
        data={"results": results}
    )

class DetailParams(BaseModel):
        kb_name:str
def detail_kb(params:DetailParams
    ) -> BaseResponse:
    # Delete selected knowledge base
    if not validate_kb_name(params.kb_name):
        return BaseResponse(code=403, msg="包含非法字符")
    params.kb_name = urllib.parse.unquote(params.kb_name)

    kb = KBServiceFactory.get_service_by_name(params.kb_name)

    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {params.kb_name}")

    try:
        kb_dict = kb_detail(kb_name=params.kb_name)
        print
        if kb_dict["code"]>-1:
            return BaseResponse(code=200, msg=f"Success",data=kb_dict)
        else:
            return BaseResponse(code=403, msg=f"未找到知识库 {params.kb_name}")
    except Exception as e:
        msg = f"获取知识库时出现意外： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)

from server.db.repository.knowledge_base_repository import kb_update
import time

class UpdateEmbeddingParams(BaseModel):
    kb_name:str
    embedding_model_name:str

def load_faiss_index(index_path: str, embeddings) -> FAISS:
    return FAISS.load_local(index_path, embeddings)

def update_embedding(params:UpdateEmbeddingParams):
    kb = KBServiceFactory.get_service_by_name(params.kb_name)

    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {params.kb_name}")
    try:
        kb_update(kb_name=params.kb_name, activate="更新")
        kb_update(kb_name=params.kb_name, embedding_name=params.embedding_model_name)
        time.sleep(10)
        kb_update(kb_name=params.kb_name, activate="正常")
        return BaseResponse(code=200, msg=f"成功更新Embedding模型")
    except Exception as e:
        msg = f"更新知识库Embedding模型时出现意外： {e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)


class MergeKBParams(BaseModel):
    kb_name_path1: str
    kb_name_path2: str
    merge_kb_name_path: str
    embedding_path: str

embedding_function = None
merge_kb_status = False


def merge_kb(params: MergeKBParams):
    # 由于faiss-gpu版本不支持merge这个接口，所以需要改源码
    # 源码位置：env/langchain_vllm2/lib/python3.8/site-packages/langchain/vectorstores/faiss.py第851到867是新增的（try except）
    global embedding_function
    global merge_kb_status
    merge_kb_status = False

    kb_name_path1 = params.kb_name_path1
    kb_name_path2 = params.kb_name_path2
    merge_kb_name_path = params.merge_kb_name_path
    embedding_path = params.embedding_path

    # EMBEDDING_NAME = "/mnt/ddata/models/bge-large-zh-v1.5/"
    # embedding_function = SentenceTransformer(EMBEDDING_NAME)

    try:
        model_kwargs = {'device': 'cuda'}
        encode_kwargs = {'normalize_embeddings': True}
        embedding_function = HuggingFaceEmbeddings(
            model_name=embedding_path,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs
        )
        
        new_vs1 = FAISS.load_local(kb_name_path1, embedding_function)
        new_vs2 = FAISS.load_local(kb_name_path2, embedding_function)

        new_vs1.merge_from(new_vs2)
        new_vs1.save_local(merge_kb_name_path)
        print("Merge completed")
        
        return BaseResponse(code=200, msg=f"向量库合并成功，合并后的向量库位于 {merge_kb_name_path}",data={})
    except:

        return BaseResponse(code=500, msg=f"向量库合并失败，两个向量库用的Embedding模型可能不都是{embedding_path}/或者两个库中有重复id")
    finally:
        merge_kb_status = True
        # 删除模型
        del embedding_function
        torch.cuda.empty_cache()
        # 调用垃圾回收
        gc.collect()
        embedding_function = None


def monitor_merge_kb():
    global merge_kb_status

    if merge_kb_status == True:
        return BaseResponse(code=200, msg=f"向量库合并完成",data={})
    
    return BaseResponse(code=200, msg=f"向量库合并中...",data={})


# def read_emb_config(knowledge_base_name):
    
#     emb_config ={knowledge_base_name:{"emb_name":EMBEDDING_MODEL,"acc":0,"version":1,"old_version":[0.9,0.8]}}
#     if os.path.exists("emb_config.json"):
#         with open("emb_config.json") as emb_json:
#             emb_config = json.load(emb_json)
#     return emb_config
    

# def read_csv_source_file(knowledge_base_name):
#     csv_dir = os.path.join("./knowledge_base/"+knowledge_base_name+"/csv/")
#     csv_files = glob.glob(csv_dir+"*emb.csv")
#     print(csv_files)
#     result =[]
#     for csv_file in csv_files:
#         with open(csv_file) as csvfile: 
#             reader = csv.reader(csvfile)
#             for row in reader:
#                 title,context,g_query,image_title = row[0].strip(),row[1].strip(),row[2].strip(),row[3].strip()
#                 g_query = g_query.split("\n")
#                 image_title  = image_title[1:-1]
#                 image_title = image_title.split(",")
#                 # print(image_title,type(image_title))
#                 result.append((title,context,g_query,image_title))
#     return result
                
# def statics_topk(knowledge_base_name,title_context_query):
#     success_count=0
#     query_count=0
#     avg_score =0
#     # kbService = KBServiceFactory.get_service_by_name(knowledge_base_name)
#     from server.knowledge_base.kb_service.faiss_kb_service import FaissKBService
#     kbService = FaissKBService(knowledge_base_name)
#     for context_query in title_context_query:
#         title,context,query_list = context_query[0],context_query[1],context_query[2]
#         if len(query_list) == 0:
#             continue
#         # 遍历所有问题
#         for q in query_list:
#             q = q.strip()
#             if q == None or len(q)==0:
#                 continue
#             query_count+=1
#             retrival_list  = kbService.do_search(q,1,0.95)
#             retrival_result = False
#             for retrival in retrival_list:
#                 document,score = retrival[0],retrival[1]
#                 titles = document.metadata["titles"]
#                 images = " ".join(document.metadata["images"])
#                 # print("titles",titles,type(titles))
                
#                 if str(titles).find(title)>-1:
#                     retrival_result =True
#                     avg_score+=score
#                     break
    
#             if retrival_result:
#                 success_count+=1
#             else:
#                 print(q,retrival_list)
#                 print("------------------")
#                 pass
#     return 0 if query_count ==0 else float(success_count/query_count)

# def generate_emb_train_data(knowledge_base_name,title_context_query,emb_config):
#     emb_lines=[]
#     from server.knowledge_base.kb_service.faiss_kb_service import FaissKBService
#     kbService = FaissKBService(knowledge_base_name)
#     for query_list in title_context_query[:]:
#         # print("query_list",query_list)
#         title,context,gen_questions,image_title=query_list
#         questions =[title]
#         questions.extend(image_title)
#         questions.extend(gen_questions)
#         for q in questions:
#             if len(q.strip())==0:
#                 continue
#             pos =[]
#             neg =[]

#             retrival_list = kbService.do_search(q,5,2)
#             pos.append(context)
            
#             for retrival in retrival_list[:5]:
#                 document,score = retrival[0],retrival[1]
#                 titles = document.metadata["titles"]
#                 images = " ".join(document.metadata["images"])
#                 if (str(titles).find(q)>-1 or str(images).find(q)>-1):
#                     pass
#                 else:
#                     neg.append(document.page_content)
#                 import random
#                 while len(neg) <5:
#                     rand_index = title_context_query[random.randint(0,len(title_context_query)-1)]
#                     rand_context = rand_index[1]
#                     if rand_context not in [neg] and rand_context != context:
#                         neg.append(rand_context)
            
#             emb_lines.append({"query":q,"pos":pos,"neg":neg})
#     config_version = emb_config[knowledge_base_name]["version"]+0.1
#     finetune_emb_filename = '../FlagEmbedding/FlagEmbedding/baai_general_embedding/finetune/'+knowledge_base_name+"_v"+format(config_version,'.1f')+'.jsonl'
#     with open(finetune_emb_filename, 'w') as jsonl_file:
#         for entry in emb_lines:
#             json.dump(entry, jsonl_file,ensure_ascii=False)
#             jsonl_file.write('\n')
#     return finetune_emb_filename

# def generate_questions_file(knowledge_base_name):
#     csv_dir = os.path.join("./knowledge_base/"+knowledge_base_name+"/csv/")
#     csv_files = glob.glob(csv_dir+"*.csv")
#     print("csv_files",csv_files)
#     for csv_file in csv_files:
#         if str(csv_file).endswith("emb.csv"):
#             continue
#         if os.path.exists(csv_file.replace(".csv","emb.csv")):
#             continue
#         csv_temp = csv_file.replace(".csv","emb_.csv")
#         content_len = 0
#         with open(csv_file) as csvfile: 
#             content_len = len(csvfile.readlines())
#         with open(csv_file) as csvfile: 
#             reader = csv.reader(csvfile)
#             import tqdm
#             b_unit = tqdm.tqdm(total=content_len, desc="parse {}: 0".format(os.path.basename(csv_file)))
#             for row in reader:
#                 b_unit.update(1)
#                 b_unit.refresh()
               
#                 title,context,image_title= row[0].strip(),row[1].strip(),row[2].strip()
#                 if len(context)>50:
#                     generate_questions = gen_question(title+"\n"+context)
#                     generate_questions = "\n".join(generate_questions)
#                 else:
#                     generate_questions=""
#                 print(title,generate_questions)
#                 with open(csv_temp, 'a', newline='') as f:
#                     writer = csv.writer(f)
#                     writer.writerow([title,context,image_title,generate_questions])
#             if os.path.exists(csv_temp):
#                 os.rename(csv_temp,csv_temp.replace("emb_.csv","emb.csv"))
                
#         # for result in run_in_thread_pool(save_file, params=params):
#         #     yield result
                    
# def subprocess_popen(statement):
#     p = subprocess.Popen(statement, shell=True, stdout=subprocess.PIPE)  # 执行shell语句并定义输出格式
#     # while p.poll() is None:  # 判断进程是否结束（Popen.poll()用于检查子进程（命令）是否已经执行结束，没结束返回None，结束后返回状态码）
#     #     if p.wait() is not 0:  # 判断是否执行成功（Popen.wait()等待子进程结束，并返回状态码；如果设置并且在timeout指定的秒数之后进程还没有结束，将会抛出一个TimeoutExpired异常。）
#     #         yield "命令执行失败，请检查设备连接状态"
#     #         return False
#     #     else:
#     #         while re := p.stdout.readline() !=None:
#     #             print("xxx",re)
#     #             yield(re)
#             # result = []
#             # for i in range(len(re)):  # 由于原始结果需要转换编码，所以循环转为utf8编码并且去除\n换行
#             #     res = re[i].decode('utf-8').strip('\r\n')
#                 # result.append(res)
            
#             # return result   
            
            
            
# from fastapi.responses import StreamingResponse
# def update_emb_model(knowledge_base_name: str = Body(..., examples=["samples"]),
#             vector_store_type: str = Body("faiss"),
#             embed_model: str = Body(EMBEDDING_MODEL),
#             ) -> BaseResponse:
    
#     # 读取配置文件
#     emb_config = read_emb_config(knowledge_base_name)
#     # 产生questions
#     generate_questions_file(knowledge_base_name)
#     # 读取列表
#     title_context_query = read_csv_source_file(knowledge_base_name)
#     # 统计现有向量库的Top1准确率
#     acc= statics_topk(knowledge_base_name,title_context_query)
#     #
#     emb_config[knowledge_base_name]["acc"] =acc
#     # 生成emb训练数据集，移动到训练目录
#     # output_path = ""
#     train_data_file = generate_emb_train_data(knowledge_base_name,title_context_query,emb_config)
#     next_version = round(emb_config[knowledge_base_name]["version"],1)+0.1
#     print("next_version",next_version)
#     output_dir = "/mnt/ddata/models/"+knowledge_base_name+"_v"+format(next_version,'.1f')
    
#     print("train_data_file",train_data_file)
#     print("output_dir",output_dir)
    
#     # os.system("cd ../FlagEmbedding && && bash finetune_test.sh "+output_dir+" "+train_data_file)
#     cmd = "cd ../FlagEmbedding && bash finetune_test.sh "+output_dir+" "+train_data_file
    
#     result = subprocess.call(cmd,shell=True)
#     # # 训练完成成，生成新版本的向量库
    
#     # # 统计新向量库的准确率
#     # # 删除旧向量库
#     # # 构建先信息的
    
#     # return StreamingResponse(subprocess_popen(cmd), media_type="text/event-stream")
    
#     emb_config[knowledge_base_name]["old_version"].append(emb_config[knowledge_base_name]["version"])
#     emb_config[knowledge_base_name]["version"] = next_version
#     with open("emb_config.json","w") as emb_f:
#         json.dump(emb_config,emb_f,ensure_ascii=False)
    
#     return BaseResponse(code=200, msg=f"已新增知识库 {knowledge_base_name}")

def delete_temp_kb(
    kb_names: List[str] = Body(..., description="文件名称，支持多文件", examples=[["file_name1", "text.txt"]])
    ) -> BaseResponse:

    results = []
    # Delete selected knowledge base
    for kb_name in kb_names:
        if not validate_kb_name(kb_name):
            results.append({"kb_name": kb_name, "status": "failed", "reason": "Invalid name"})
            continue
    # if not validate_kb_name(params.kb_name):
    #     return BaseResponse(code=403, msg="Don't attack me")
        kb_name = urllib.parse.unquote(kb_name)
        kb = KBServiceFactory.get_service_by_name(kb_name)

        if kb is None:
            results.append({"kb_name": kb_name, "status": "failed", "reason": f"未找到知识库 {kb_name}"})
            continue
            # return BaseResponse(code=404, msg=f"未找到知识库 {params.kb_name}")

        try:
            status = kb.clear_vs()
            status = kb.drop_kb()
            if status:
                results.append({"kb_name": kb_name, "status": "success"})
            else:
                results.append({"kb_name": kb_name, "status": "failed", "reason": "Unknown error during deletion"})
                # return BaseResponse(code=200, msg=f"成功删除知识库 {params.kb_name}")
        except Exception as e:
            msg = f"删除知识库时出现意外： {e}"
            logger.error(f'{e.__class__.__name__}: {msg}',
                        exc_info=e if log_verbose else None)
            results.append({"kb_name": kb_name, "status": "failed", "reason": str(e)})
            # return BaseResponse(code=500, msg=msg)
    success_count = len([r for r in results if r["status"] == "success"])

    return BaseResponse(
        code=200 if success_count > 0 else 500,
        msg=f"批量删除完成，成功 {success_count} 项，失败 {len(results) - success_count} 项",
        data={"results": results}
    )

# if __name__ == "__main__":
#     kb_name="nuclear_law"
#     result = read_csv_source_file(kb_name)
#     result = statics_topk(kb_name,result)
    
#     # from server.knowledge_base.kb_service.faiss_kb_service import FaissKBService
#     # kbService = FaissKBService(knowledge_base_name)
    
#     # result = kbService.do_search("请问在核动力厂房设计时，通风系统的设计应该考虑哪些方面？",5,2)
#     print(result)