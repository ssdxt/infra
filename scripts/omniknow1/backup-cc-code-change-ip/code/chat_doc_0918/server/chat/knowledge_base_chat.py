from fastapi import Body, Request
from fastapi import File, Form, Body, Query, UploadFile,Depends
from fastapi.responses import StreamingResponse
from configs import (LLM_MODELS, VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD, TEMPERATURE,EMBEDDING_MODEL,MODEL_ROOT_PATH,MODEL_PATH,EMBEDDING_SERVER,RERANK_MODEL_SERVER)
from server.utils import wrap_done, get_ChatOpenAI_new
from server.utils import BaseResponse, get_prompt_template
from langchain.chains import LLMChain
from langchain.callbacks import AsyncIteratorCallbackHandler
from typing import AsyncIterable, List, Optional
import asyncio
# from langchain.prompts.chat import ChatPromptTemplate
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from server.knowledge_base.kb_service.bm25 import BM25Retriever
import jieba
from server.chat.utils import History,source_type_from_url
from server.knowledge_base.kb_service.base import KBServiceFactory
from server.knowledge_base.utils import get_doc_path,get_bm_path
from server.utils import load_local_embeddings
import json
import math
import os
from server.embeddings_api import embed_texts
from pathlib import Path
from urllib.parse import urlencode
from server.knowledge_base.kb_doc_api import search_docs
from langchain import PromptTemplate
import numpy as np
from sentence_transformers import SentenceTransformer
from server.db.repository import add_chat_history_to_db, update_chat_history,feedback_chat_history_to_db
import numpy
from server.http_api.user_api import token_check
from server.db.repository.app_repository import app_detail
from datetime import datetime
from embeddings.xinference.rerank_model import VllmRerank

reranker_tokenizer = None
reranker_model = None

rerank = VllmRerank(key=RERANK_MODEL_SERVER["api_key"], model_name=RERANK_MODEL_SERVER["model_name"], base_url=RERANK_MODEL_SERVER["base_url"])

def sentence_score(query_list,context_list):
    if EMBEDDING_SERVER:
        if context_list is None or len(context_list) == 0:
            return numpy.array([0.0])
        query_embedding = embed_texts(query_list).data
        context_embedding = embed_texts(context_list).data
        query_vec = np.array(query_embedding)
        context_vecs = np.array(context_embedding)
        scores = query_vec @ context_vecs.T
        return scores
    else:
        if context_list is None or len(context_list) == 0:
            return numpy.array([0.0])
        g_emb_model = load_local_embeddings(EMBEDDING_MODEL).client
        q_embeddings = g_emb_model.encode(query_list, normalize_embeddings=True)
        p_embeddings = g_emb_model.encode(context_list, normalize_embeddings=True)
        scores = q_embeddings @ p_embeddings.T
        return scores

def query_image_title_similarity(querys,_image_titles,_image_urls):
    _s_image_urls = []
     
    if _image_titles is None or _image_urls is None or len(_image_titles) != len(_image_urls) :
        return _s_image_urls
    if _image_titles:
        scores = sentence_score(querys,_image_titles)
        sim_scores = list(scores>0.5)
        try:
            if len(sim_scores)>0:
                sim_scores = sim_scores[0]
            if type(sim_scores)== numpy.ndarray:
                sim_scores = sim_scores.tolist()
        except:
            pass
  
        for idx,_image_url in enumerate(_image_urls):
            if sim_scores[idx]== True and len(_image_url) >0 :
                _s_image_urls.append(_image_url)
    return _s_image_urls

#计算短句的相似度
def sentence_score_api(query_list:List[str]= Body(..., examples=[["xxx", "yyy"]]),context_list:List[str]= Body(..., examples=[["xxx", "yyy"]])):
    scores = sentence_score(query_list,context_list)
    return BaseResponse(code=200, msg=f"",data={"scores":scores[0].tolist()})

def intent_ie(historys,query,keywords):
    from server.http_api.tools_api import GenerateQueryIntentParams,generate_query_intent_s
    intent_dict = generate_query_intent_s(historys,query,keywords).data
    return intent_dict
    
def get_keyword_pairs(knowledge_base_name):
    mapping={"核电网站":[["协会","中国核能行业协会"],
           ["核协","中国核能行业协会"],
           ["核能行业协会","中国核能行业协会"],
           ["数字协会","中国核能行业协会数字协会"],
           ["团标","团体标准"],
           ["我国","中国"],
           ["法人","法人代表"],
           ["当年","2024年"],
           ["当前","2024年9月13日"]]
             }
    return mapping.get(knowledge_base_name,None)
    
    
def top_kbs(kbs,query,messages):
    return kbs
    # if len(kbs) == 1:
        
    # intent_dict = intent_ie(query,messages)
    # if intent_dict.get("意图") == "闲聊":
    #     return []   
    # else:
    #     new_query = intent_dict["型号"]+" "+intent_dict.get("名称")
        
    #     sim_scores= list(sentence_score([new_query],kbs)>0.3)
    #     print("new_query",kbs)
    #     print("new_query",new_query)
    #     print("sim_scores",sim_scores)
        
    #     try:
    #         if len(sim_scores)>0:
    #             sim_scores = sim_scores[0]

    #         ret = numpy.array(kbs)[sim_scores]
    #         return ret.tolist()
    #     except:
    #         pass
    #     return []
         

class AsyncIteratorWrapper:
    def __init__(self, obj):
        self._it = iter(obj)
 
    def __aiter__(self):
        return self
 
    async def __anext__(self):
        try:
            value = next(self._it)
        except StopIteration:
            raise StopAsyncIteration
        return value
 
 
async def knowledge_base_chat(query: str = Body(..., description="用户输入", examples=["你好"]),
                            knowledge_base_name: str = Body(None, description="知识库名称", examples=["samples"]),
                            history: List[History] = Body([],
                                                      description="历史对话",
                                                      examples=[[
                                                          {"role": "user",
                                                           "content": "我们来玩成语接龙，我先来，生龙活虎"},
                                                          {"role": "assistant",
                                                           "content": "虎头虎脑"}]]
                                                      ),
                            stream: bool = Body(True, description="流式输出"),
                            model_name: str = Body(LLM_MODELS[0], description="LLM 模型名称。"),
                            max_tokens: Optional[int] = Body(None, description="限制LLM生成Token数量，默认None代表模型最大值"),
                            chat_session_id:str = Body("", description="聊天窗口的session，可以为空，为空表示新创建一个session"),
                            app_id:int = Body(None, description="应用id"),
                            hybird_search: bool = Body(True, description="混合检索"),
                        ):

#    from server.chat.time_validator import validate_expiration_time
#    expiration_result = validate_expiration_time()
#    if expiration_result:
#        return expiration_result


    top_k = VECTOR_SEARCH_TOP_K*4
    score_threshold = SCORE_THRESHOLD
    temperature = 0.95
    history_len = 6

    if knowledge_base_name:
        keywords=get_keyword_pairs(knowledge_base_name)
    else:
        keywords=None
        
    prompt = """你是领域专家小真，由杭州炽橙数字科技公司开发。今天是"""+str(datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'))+"""。请根据'已知信息'回答问题。\n\n限制:\n - 请尽量以干净的'Markdown'格式形式结构化的输出,不需要以```开始；\n- 当询问专业场景问题时，请采用严谨专业的语言风格；\n- 直接输出内容本身，不要输出见附件，见某某表格 \n- 在专业场景中，如果用户本身意图不够清晰，可以对用户进行追问以帮助你理解用户的真实意图；\n\n已知信息：'{{context}}'\n问题：'{{question}}'\n回答："""
    import os
    Infer_server_api = [
      {
        "model_title": "cc-13b-chat",
        "model_name": "glm-4",
        "api_base_url": os.getenv("GLM_BASE_URL", "http://127.0.0.1:10006/v1"),
        "api_key": "empty",
        "openai_proxy": ""
      },
    ]
    # deepseek-r1 / qwen：仅当环境变量配置了服务地址才出现在可选列表（未部署即隐藏）
    if os.getenv("LLM_DEEPSEEK_URL", ""):
        Infer_server_api.append({
            "model_title": "deepseek-r1",
            "model_name": "deepseek-r1",
            "api_base_url": os.getenv("LLM_DEEPSEEK_URL"),
            "api_key": "empty",
            "openai_proxy": ""
        })
    if os.getenv("LLM_QWEN_URL", ""):
        Infer_server_api.append({
            "model_title": "qwen",
            "model_name": "qwen",
            "api_base_url": os.getenv("LLM_QWEN_URL"),
            "api_key": "empty",
            "openai_proxy": "",
        })
    model_config = next((item for item in Infer_server_api if item["model_title"] == model_name), None)
    if app_id:
        app_info = app_detail(id=app_id,is_detail=True)
        current_time = datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')

        prompt = app_info["data"].get("info").get("chat_config").get("prompt")
        prompt = f"当前时间是{current_time}。" + prompt
        temperature = app_info["data"].get("info").get("chat_config").get("temperature")
        score_threshold = app_info["data"].get("info").get("chat_config").get("score_threshold")
        top_k = app_info["data"].get("info").get("chat_config").get("top_k")
        history_len = app_info["data"].get("info").get("chat_config").get("history_len")
        Infer_server_api = app_info["data"].get("info").get("chat_config").get("Infer_server_api")
        model_config = next((item for item in Infer_server_api if item["model_title"] == model_name), None)
        keywords = app_info["data"].get("info").get("keywords")

        if knowledge_base_name is None:
            kbs = app_info["data"].get("kbs")
            kb_names = [kb["kb_name"] for kb in kbs] if kbs else []
        

        temperature=float(temperature)
        score_threshold=float(score_threshold)
        top_k=int(top_k)
        history_len=int(history_len)

        if model_config is None:
            return {"code":0,"msg":"未获取到对应模型配置"}
    
    if knowledge_base_name == "临时知识库":
        knowledge_base_name = chat_session_id  

    max_tokens = 4096*2
    query_new = query

    if knowledge_base_name != "hjj知识库":

        res = intent_ie(historys=history,query=query,keywords=keywords)
        
        if type(res) == dict:
            if res.get("改写后内容"):
                query_new_t = res.get("改写后内容")
                if query_new_t and type(query_new_t) == str:
                    query_new = query_new_t
                    if knowledge_base_name:
                        with open("temp_ie.txt","a") as f:
                            f.write(knowledge_base_name+","+str(history)+","+query+","+query_new+"\n")
                    else:
                        with open("temp_ie.txt","a") as f:
                            f.write(str(history)+","+query+","+query_new+"\n")
                print("改写后内容",query,query_new)
                
            # query = query_new
    # if knowledge_base_name == "长龙航空地服":
    #     prompt_name = "long_air_default"
    #     score_threshold = 1.05
    #     pass

    if knowledge_base_name:
        kbs = str(knowledge_base_name).split(",")
        kb_names = kbs
    # kb_names = top_kbs(kbs,query=query,messages=history)

    history = history[:-1]
    history = [History.from_data(h) for h in history]
    history = history[-history_len:]

    async def knowledge_base_chat_iterator(query: str,
                                           top_k: int,
                                           history: Optional[List[History]],
                                           model_config: dict,
                                           prompt: str = prompt,
                                           chat_session_id:str = chat_session_id,
                                           knowledge_base_name:str = knowledge_base_name
                                           ) -> AsyncIterable[str]:
        callback = AsyncIteratorCallbackHandler()
        
        model = get_ChatOpenAI_new(
            model_config=model_config,
            temperature=temperature,
            max_tokens=max_tokens,
            callbacks=[callback],
        )
        import time
        t1 = time.time()*1000
        docs =[]
        
        for kb in kb_names:
            print(query_new)
            d = search_docs(query_new, kb, top_k, score_threshold).data
            if len(d)>0:
                docs.extend(d)
        
        if len(docs)>0:
            # docs.sort(key=lambda doc:doc.score)
    
            # import torch
            # from transformers import AutoModelForSequenceClassification, AutoTokenizer
            # global reranker_tokenizer,reranker_model
            # if reranker_tokenizer is None:
            #     reranker_tokenizer = AutoTokenizer.from_pretrained(RERANK_MODEL_PATH)
            #     reranker_model = AutoModelForSequenceClassification.from_pretrained(RERANK_MODEL_PATH).cuda()
            #     reranker_model.eval()
                
                
            # 去重
            temp = []
            new_docs = []
            for i in docs:
                if i.page_content not in temp:
                    temp.append(i.page_content)
                    new_docs.append(i)


            # print('================ new_docs =====================',new_docs)
            docs = new_docs
            contexts = []
            for doc in docs:
                c = ""
                if 'keyword' in doc.metadata:
                    c += " ".join(doc.metadata["keyword"])+"\n"
                if 'titles' in doc.metadata:
                    c += doc.metadata["titles"]+"\n"
                c += doc.page_content+"\n\n"
                
                contexts.append(c)
                
            
            scores = rerank.similarity(query, contexts)
            docs = [doc for _, doc in sorted(zip(scores[0], docs), key=lambda x: x[0], reverse=True)]
            docs = docs[:top_k]
                
            # with torch.no_grad():
            #     inputs = reranker_tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=512).to(reranker_model.device)
            #     scores = reranker_model(**inputs, return_dict=True).logits.view(-1, ).float()
            #     scores = scores.cpu().numpy()
            #     idxs = numpy.argsort(scores)
            #     idxs = idxs[::-1]
            #     print(scores,idxs)
            #     doc_temp = []
            #     for _idx in idxs:
            #         doc_temp.append(docs[_idx])
            #         if len(doc_temp)>=VECTOR_SEARCH_TOP_K:
            #             break
            #     docs = doc_temp

        t2 = time.time()*1000
        t3 = t2
        t4 = t2
        
        
        #后续应该改为意图识别：
        #意图识别：闲聊，找图，找条款，问题指示代词不全，
        # image_index = -1
        # image_doc = None
        # if len(docs)>0:
        #     print("docs",docs)
        #     for doc in docs:
        #         sim_scores = query_image_title_similarity_scores([query],doc.metadata.get("images",None))
        #         try:
        #             if len(sim_scores)>0:
        #                 sim_scores = sim_scores[0]
        #             if type(sim_scores)== numpy.ndarray:
        #                 sim_scores = sim_scores.tolist()
        #             image_index =sim_scores.index(True)
        #         except:
        #             pass
        #         print("sim_scores:",sim_scores,type(sim_scores),image_index)
        #         if image_index >-1:
        #             image_doc = doc
        #             break
        
        # if image_doc and image_doc.metadata.get("images_path",None) and image_doc.metadata["images_path"][image_index] == None:
        #     print("error>>>not match",image_doc.metadata)
        # #如果找到图片
        # if image_doc and image_doc.metadata.get("images_url",None) and image_doc.metadata["images_url"][image_index]:
        #     image_txt =  json.dumps({"answer": "为您找到相关图片" +"\n"}, ensure_ascii=False)
        #     _image_url = image_doc.metadata["images_url"][image_index]
        #     _image_url_dict = {"url":str(_image_url)}
        #     _image_url_json_str = json.dumps({"ref_images": [_image_url_dict]}, ensure_ascii=False)
            
        #     #聊天记录存在数据库中
        #     chat_session_id,chat_id = add_chat_history_to_db(chat_session_id=chat_session_id,chat_type=knowledge_base_chat,query=query, response="为您找到相关图片" +"\n"+_image_path, chat_history_id=None, metadata={"context":None})
        #     _doc_filename = doc.metadata.get("filename")
        #     _doc_url = doc.metadata.get("url")
        #     ref_doc = {
        #             "filename":_doc_filename,
        #             "url":str(_doc_url),
        #             "score":image_doc.score,
        #             "page_no":image_doc.metadata["content_pos"][0]['page_no'] if "content_pos" in image_doc.metadata else 0 ,
        #             "page_content":"",
        #             "content_pos":image_doc.metadata["content_pos"] if "content_pos" in image_doc.metadata else [],
        #             "questions":image_doc.metadata["g_query"] if "g_query" in image_doc.metadata else [],
        #             }

        #     ref_docs = json.dumps({"ref_docs": [ref_doc],"chat_session_id":chat_session_id,"chat_id":chat_id}, ensure_ascii=False)
        #     image_result_output =[image_txt,_image_url_json_str]
        #     async for ss in AsyncIteratorWrapper(image_result_output):
        #         import time
        #         time.sleep(0.0001)
        #         print(ss)
        #         yield ss
                
        # else:
            # context = "\n".join(["'已知信息'\n"+doc.metadata["titles"]+"\n"+doc.page_content for doc in docs])
            
        # if len(docs)>0:
        #     anims =[]
        #     for doc in docs:
        #         source_type =doc.metadata.get("source_type")
        #         if source_type == "anim":
        #             score = doc.score
        #             try:
        #                 if score<0.550:
        #                     info = doc.metadata.get("info")
        #                     action = "show_animation"
        #                     ref_doc ={"action":action,"info":info}
        #                     anims.append(ref_doc)
        #             except:
        #                 pass
        # if len(anims)>0:
        #     anims_output =[json.dumps(anims)]
        #     print(anims_output)
        #     async for ss in AsyncIteratorWrapper(anims_output):
        #         import time
        #         time.sleep(0.0001)
        #         # asyncio.sleep(0.0001)
        #         print(ss)
        #         yield ss
        if True:
            context =""
            feedback_doc = None
            for index, doc in enumerate(docs):
                if 'feedback_source_id' in doc.metadata:
                    feedback_doc = doc
                    break
            if feedback_doc:
                context = doc.metadata.get("answer")
                prompt = """你是领域专家小真，由杭州炽橙数字科技公司开发。今天是"""+str(datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'))+"""。请根据'已知信息'回答问题。\n\n限制:\n - 请尽量以干净的'Markdown'格式形式结构化的输出,不需要以```开始；\n- 当询问专业场景问题时，请采用严谨专业的语言风格；\n- 直接输出’已知信息‘的本身，不要输出见附件，见某某表格 \n- 在专业场景中，如果用户本身意图不够清晰，可以对用户进行追问以帮助你理解用户的真实意图；\n\n已知信息：'{{context}}'\n问题：'{{question}}'\n回答："""
            else:
                for index, doc in enumerate(docs):
                    chunk = ""
                    if 'keyword' in doc.metadata:
                        chunk += " ".join(doc.metadata["keyword"])+"\n"
                    if 'titles' in doc.metadata:
                        chunk += doc.metadata["titles"]+"\n"
                    chunk += doc.page_content+"\n\n"
                    context +=chunk
                    print(">>>>>",index,chunk)
                    print(doc.metadata)
                    if len(context) >max_tokens*0.75:
                        context = context[:int(max_tokens*0.75)]
                        break
                
            
            # context = context.replace("\n\n","")
            
            prompt_template = prompt
            
            # print('context: ',context)
            input_msg = History(role="user", content=prompt_template).to_msg_template(False)
            
            chat_prompt = ChatPromptTemplate.from_messages(
                [i.to_msg_template() for i in history] + [input_msg]) 

            print("使用的prompt模板:", prompt)
            print("完整的chat_prompt:", chat_prompt)

            chain = LLMChain(prompt=chat_prompt, llm=model)
            
            t2 = time.time()*1000
            t3 = t2
            t4 = t2
            print("输入模型的内容:", chat_prompt.format(context=context, question=query))
            task = asyncio.create_task(wrap_done(
                chain.acall({"context": context, "question": query}),
                callback.done),
            )

            ref_documents=[]
            kb_name = ""
            for inum, doc in enumerate(docs):
                if 'feedback_source_id' in doc.metadata:
                    ref_documents=[]
                    ref_documents.append(doc.metadata)
                    break
                    # feedback_source_id = doc.metadata.get("feedback_source_id")
                    # answer = doc.metadata.get("answer")
                    # characters = list(answer)
                    # chunk_size = 1
                    # for i in range(0, len(characters), chunk_size):
                    #     chunk = "".join(characters[i:i+chunk_size])                       
                    #     yield json.dumps({"answer": chunk},ensure_ascii=False) + "\n\n"
                    #     await asyncio.sleep(0.05)
                    
                    # chat_session_id,chat_id = add_chat_history_to_db(chat_session_id=chat_session_id,chat_type=knowledge_base_name,query=query, response=answer, chat_history_id=None, metadata={"context":context})                           
                    # anims = json.dumps({"chat_session_id":chat_session_id,"chat_id":chat_id}, ensure_ascii=False)
                    # print(anims)
                    # yield anims
                    # return

                else:
                    if knowledge_base_name is None and inum == 0 and 'source' in doc.metadata:
                        source_path = doc.metadata['source']
                        path_parts = source_path.split('/')
                        if len(path_parts) > 2 and path_parts[0] == 'knowledge_base':
                            knowledge_base_name = path_parts[1]
                            print(f"从文档中提取知识库名称: {knowledge_base_name}")
                    
                    if 'source' in doc.metadata:
                        source_path = doc.metadata['source']
                        path_parts = source_path.split('/')
                        if len(path_parts) > 2 and path_parts[0] == 'knowledge_base':
                            kb_name = path_parts[1]

                    if doc.metadata['source'].endswith("csv") or doc.metadata['source'].endswith("核电厂_建设中-new.json") or doc.metadata['source'].endswith("核电厂_运营中-new.json") or doc.metadata['source'].endswith("核电厂_筹建中-new.json") or doc.metadata['source'].endswith("核电-基础.json"):
                        continue
                    filename = doc.metadata.get("filename")
                    _doc_url = doc.metadata.get("url")
                    source_type =doc.metadata.get("source_type")
                    
                    print(filename)
                    info ={
                        "filename":str(filename),
                        "url":str(_doc_url),
                        "score":doc.score,
                        "page_no":doc.metadata["content_pos"][0]['page_no'] if "content_pos" in doc.metadata else 0 ,
                        "content_pos":doc.metadata["content_pos"] if "content_pos" in doc.metadata else []
                        }
                    action ="show_pdf"
                    _s_image_urls =[]
                    
                    if source_type == "anim":
                        info = doc.metadata.get("info")
                        action = "show_animation"
                    else:
                        _s_image_urls = query_image_title_similarity([query], doc.metadata.get("images",None),doc.metadata.get("images_url",None))
                        if len(_s_image_urls)>0:
                            info = _s_image_urls
                            action = "show_image"
                        else:
                            pass
                            
                    ref_doc = {
                        "source_type":source_type,
                        "kb_name":kb_name,
                        "filename":str(filename),
                        "url":str(_doc_url),
                        "score":doc.score,
                        "page_no":doc.metadata["content_pos"][0]['page_no'] if "content_pos" in doc.metadata else 0 ,
                        "content_pos":doc.metadata["content_pos"] if "content_pos" in doc.metadata else [],
                        "page_content":"",
                        "_s_image_urls":_s_image_urls,
                        "info":info,
                        "action":action
                        }
                    
                    ref_documents.append(ref_doc)

            token_index =0
            valid_token = False
            if stream:
                print(kb_names)
                if knowledge_base_name is None and kb_names and len(kb_names) > 0:
                    knowledge_base_name = kb_names[0]
                #聊天记录存在数据库中
                chat_session_id,chat_id = add_chat_history_to_db(chat_session_id=chat_session_id,chat_type=knowledge_base_name,query=query, response=None, chat_history_id=None, metadata={"context":context})              
                # anims = json.dumps({"ref_docs": ref_documents,"chat_session_id":chat_session_id,"chat_id":chat_id}, ensure_ascii=False) + "\n\n"
                # print("ref_docs",anims)
                # yield anims

                response_tokens = []
                inside_think = False
                reasoning_start_time = None
                reasoning_end_time = None
                async for token in callback.aiter():
                    print(token)
                    # Use server-sent-events to stream the response
                    token_index +=1
                    if token_index ==1:
                        t3 = time.time()*1000
                    # print("token:",repr(token))
                    if valid_token == False:
                        if len(token.strip()) == 0:
                            pass
                        else :
                            valid_token = True
                            response_tokens.append(token.lstrip())
                            if model_name == "deepseek-r1":
                                if token_index == 1:
                                    token = "<think>" + token
                                if "<think>" in token:
                                    inside_think = True
                                    reasoning_start_time = time.time()
                                    yield json.dumps({"reasoning": token.split("<think>", 1)[-1]}, ensure_ascii=False) + "\n\n"
                                elif inside_think:
                                    if "</think>" in token:
                                        reasoning_end_time = time.time()
                                        yield json.dumps({"reasoning": token.split("</think>", 1)[0]}, ensure_ascii=False) + "\n\n"
                                        inside_think = False
                                        reasoning_duration = reasoning_end_time - reasoning_start_time
                                        yield json.dumps({"reasoning_time": reasoning_duration,"answer": token.split("</think>", 1)[-1]}, ensure_ascii=False) + "\n\n"
                                    else:
                                        yield json.dumps({"reasoning": token}, ensure_ascii=False) + "\n\n"
                                else:
                                    yield json.dumps({"answer": token}, ensure_ascii=False) + "\n\n"
                            else:
                                yield json.dumps({"answer": token}, ensure_ascii=False)+"\n\n"
                            # await asyncio.sleep(0.0001)
                    else:
                        response_tokens.append(token)
                        if model_name == "deepseek-r1":
                            if token_index == 1:
                                token = "<think>" + token
                            if "<think>" in token:
                                inside_think = True
                                reasoning_start_time = time.time()
                                yield json.dumps({"reasoning": token.split("<think>", 1)[-1]}, ensure_ascii=False) + "\n\n"
                            elif inside_think:
                                if "</think>" in token:
                                    reasoning_end_time = time.time()
                                    yield json.dumps({"reasoning": token.split("</think>", 1)[0]}, ensure_ascii=False) + "\n\n"
                                    inside_think = False
                                    reasoning_duration = reasoning_end_time - reasoning_start_time
                                    yield json.dumps({"reasoning_time": reasoning_duration,"answer": token.split("</think>", 1)[-1]}, ensure_ascii=False) + "\n\n"
                                else:
                                    yield json.dumps({"reasoning": token}, ensure_ascii=False) + "\n\n"
                            else:
                                yield json.dumps({"answer": token}, ensure_ascii=False) + "\n\n"
                        else:
                            yield json.dumps({"answer": token}, ensure_ascii=False)+"\n\n"
                        # await asyncio.sleep(0.0001)
                s3 = time.time()*1000 
                t4 = time.time()*1000
                repsonse_str = "".join(response_tokens)
                print(">>>","检索向量时间：",str(t2-t1),"首字时间：",str(t3-t2),"token总时间：",str(t4-t3),"每秒token数：",str(1000*token_index/((t4-t3))),"每秒字数：",str(1000*len(repsonse_str)/((t4-t3))))
                
                update_chat_history(chat_session_id=chat_session_id,chat_id=chat_id,response=repsonse_str)
                
                #聊天记录存在数据库中
                # chat_session_id,chat_id = add_chat_history_to_db(chat_session_id=chat_session_id,chat_type=knowledge_base_name,query=query, response=repsonse_str, chat_history_id=None, metadata={"context":context})
                               
                if len(response_tokens) > 0:
                    anims = json.dumps({"ref_docs": ref_documents,"chat_session_id":chat_session_id,"chat_id":chat_id}, ensure_ascii=False)
                    print("ref_docs",anims)
                    yield anims
                
            else:
                answer = ""
                async for token in callback.aiter():
                    answer += token
                yield json.dumps({"answer": answer,},
                                ensure_ascii=False)
            await task
   
        

    return StreamingResponse(knowledge_base_chat_iterator(query=query,
                                                          top_k=top_k,
                                                          history=history,
                                                          model_config=model_config,
                                                          prompt=prompt,
                                                          chat_session_id = chat_session_id,
                                                          knowledge_base_name = knowledge_base_name
                                                          ),
                             media_type="text/event-stream")
