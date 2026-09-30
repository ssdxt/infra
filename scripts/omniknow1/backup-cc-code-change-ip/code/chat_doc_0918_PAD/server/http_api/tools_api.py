import openai
import json
import sys,os
import re
sys.path.append("/home/star/projects/chat_doc")
from server.utils import BaseResponse
import openai
from fastapi.responses import StreamingResponse
from server.knowledge_base.kb_service.base import KBServiceFactory
# from server.knowledge_base.kb_doc_api import search_docs
from server.knowledge_base.kb_doc_api import search_docs,search_docs_by_id
from configs import VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD
from configs.model_config import GENERATE_MODEL_SERVER
from openai import OpenAI
# openai.api_base = GENERATE_MODEL_SERVER["base_url"]
# openai.api_key = GENERATE_MODEL_SERVER["api_key"]

from pydantic import BaseModel
import requests
import base64
import fitz
from fastapi import Form, File, UploadFile, HTTPException
from starlette.datastructures import Headers


class ParseImgExam(BaseModel):
    file_url:str

def parse_img_exam(params:ParseImgExam):
    # openai.api_base = "http://192.168.5.210:9000/v1"
    # openai.api_key = "EMPTY"

    client = OpenAI(
    base_url="http://192.168.5.210:9000/v1",
    api_key="EMPTY"
    )

    file_url = params.file_url
    use_stream=False

    try:
        response = requests.get(file_url)
        response.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"文件下载失败: {str(e)}")

    root_path= os.path.abspath('.')
    upload_dir = root_path + "/uploads/"
    fn = file_url.split("/")[-1]
    temp_file = f"{upload_dir}/{fn}"

    with open(temp_file, 'wb') as f:
        f.write(response.content)
    
    suffix = temp_file.split(".")[-1]

    def encode_image(image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    base64_image = encode_image(temp_file)
    url = f"data:image/{suffix};base64,{base64_image}"

    messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": """
                        1. 你是一个图片内容提取专家，下面给你一张图片，将图片中所有的试题以结构化的形式进行输出。
                        2. 如果是选择题，将题目、选项和相应的答案列出来，样式严格遵守下面的示例格式：
                        [{"Question": "车子是'德龙 M3000'车型，哪一项是电源部分的组成", "type": "choice", "Options": ["A.蓄电池 G100、G101", "B.电源总开关 S4", "C. 发电机 G102", "D.发动机"] , "Answer": "ABC"},
                        {"Question": "对于富勒变速箱，富勒变速箱常见的故障有哪些？", "type": "choice", "Options": ["A. 换档困难", "B. 变速箱脱档", "C. 变速箱破损", "D.变速箱掉档"], "Answer": "ABD"}]
                        3. 如果是填空题，将题目、空白括号和相应的答案列出来，如果有多个空白括号，答案以list输出，样式严格遵守下面的示例格式：
                        [{"Question": "车子是'德龙 M3000'车型，（）、（）、（）是电源部分的组成。", "type": "fulling", "Answer": ["蓄电池", "电源总开关", "发电机"]"},
                        {"Question": "对于富勒变速箱，富勒变速箱常见的故障有（）、（）、（）。", "type": "fulling", "Answer": ["换档困难", "变速箱脱档","变速箱掉档"]}]
                        4. 如果是判断题，将题目、空白括号和相应的答案列出来，样式严格遵守下面的示例格式：
                        [{"Question": "车子是'德龙 M3000'车型，发动机是电源部分的组成。（）", "type": "judge", "Answer": "错误""},
                        {"Question": "车子是'德龙 M3000'车型，发电机G102是电源部分的组成。（）", "type": "judge", "Answer": "正确"}]
                        5. 如果是问答题，将题目和相应的答案列出来，样式严格遵守下面的示例格式：
                        [{"Question": "车子是'德龙 M3000'车型，电源部分的组成有哪些？", "type": "QA", "Answer": "电源部分有蓄电池、电源总开关、发电机"},
                        {"Question": "对于富勒变速箱，有哪些常见的故障？", "type": "QA", "Answer": "富勒变速箱常见的故障有换档困难、变速箱脱档、变速箱掉档"}]
                        6. 注意：只输出内容，不要加其他语句。
                        7. 如果在图片最下面试题不完整，则该条题目不输出。
                        """
                },
                {
                    "type": "image_url",
                    "image_url": {"url": url}
                }
            ],
        }]

    result = client.chat.completions.create(
        model="/mnt/ddata1/models/Qwen2.5-VL-32B-Instruct",
        messages=messages,
        temperature=0.01,
        top_p=0.001,
        max_tokens=4096*2,
        use_stream=use_stream
    )
    answer = result.choices[0].message.content
    if answer:
        try:
            answer = re.sub(r'\s+', '', answer)
            answer = answer.replace('"，', '", ').replace('}，', '}, ')
            if answer[:3] != '[{"':
                first_occurrence_position = answer.find('{"')
                answer = '[' + answer[first_occurrence_position:]
            if answer[-3:] != '"}]':
                last_occurrence_position = answer.rfind('},')
                answer = answer[:last_occurrence_position+1]+']'
                content = json.loads(answer)
                return BaseResponse(code=200,msg="生成成功",data=content)
        except Exception as e:
            return BaseResponse(code=-1,msg="生成解析失败",data=e)
    else:
        print("Error:", answer.status_code)
        return BaseResponse(code=-1,msg="生成失败",data={})

class ParsePdfExam(BaseModel):
    file_url:str

def parse_pdf_exam(params:ParsePdfExam):
    # openai.api_base = "http://192.168.5.210:8002/v1"
    # openai.api_key = "EMPTY"

    client = OpenAI(
    base_url="http://192.168.5.210:8002/v1",
    api_key="EMPTY"
    )

    file_url = params.file_url
    use_stream=False

    try:
        response = requests.get(file_url)
        response.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"文件下载失败: {str(e)}")

    root_path= os.path.abspath('.')
    upload_dir = root_path + "/uploads/"
    fn = file_url.split("/")[-1]
    temp_file = f"{upload_dir}/{fn}"

    with open(temp_file, 'wb') as f:
        f.write(response.content)
    
    pdf = fitz.open(temp_file)
    content = ""
    for pd in pdf:
        content += pd.get_text()

    prompt = """
            1. 你是一个内容提取专家，下面给你一段文字，将其中所有的试题以标准'json'格式结构化的形式进行输出, 输出格式为python格式，最外层为一个python list，在list里面每个问答对为一个python dict。
            2. 如果是选择题，将题目、选项和相应的答案列出来，样式严格遵守下面的示例格式：
            [{"Question": "车子是'德龙 M3000'车型，哪一项是电源部分的组成", "type": "choice", "Options": ["A.蓄电池 G100、G101", "B.电源总开关 S4", "C. 发电机 G102", "D.发动机"] , "Answer": "ABC"},
            {"Question": "对于富勒变速箱，富勒变速箱常见的故障有哪些？", "type": "choice", "Options": ["A. 换档困难", "B. 变速箱脱档", "C. 变速箱破损", "D.变速箱掉档"], "Answer": "ABD"}]
            3. 如果是填空题，将题目、空白括号和相应的答案列出来，如果有多个空白括号，答案以list输出，样式严格遵守下面的示例格式：
            [{"Question": "车子是'德龙 M3000'车型，（）、（）、（）是电源部分的组成。", "type": "fulling", "Answer": ["蓄电池", "电源总开关", "发电机"]"},
            {"Question": "对于富勒变速箱，富勒变速箱常见的故障有（）、（）、（）。", "type": "fulling", "Answer": ["换档困难", "变速箱脱档","变速箱掉档"]}]
            4. 如果是判断题，将题目、空白括号和相应的答案列出来，样式严格遵守下面的示例格式：
            [{"Question": "车子是'德龙 M3000'车型，发动机是电源部分的组成。（）", "type": "judge", "Answer": "错误""},
            {"Question": "车子是'德龙 M3000'车型，发电机G102是电源部分的组成。（）", "type": "judge", "Answer": "正确"}]
            5. 如果是问答题，将题目和相应的答案列出来，样式严格遵守下面的示例格式：
            [{"Question": "车子是'德龙 M3000'车型，电源部分的组成有哪些？", "type": "QA", "Answer": "电源部分有蓄电池、电源总开关、发电机"},
            {"Question": "对于富勒变速箱，有哪些常见的故障？", "type": "QA", "Answer": "富勒变速箱常见的故障有换档困难、变速箱脱档、变速箱掉档"}]
            6. 注意：只输出内容，不要加其他语句。
            """

    messages = [{"role": "system", "content": content},
        {"role": "user", "content": prompt}]

    result = client.chat.completions.create(
        model="/mnt/ddata1/models/Qwen2.5-32B-Instruct/",
        messages=messages,
        # max_tokens=32768*2,
        temperature=0.8,
        presence_penalty=1.2,
        top_p=0.8,
        use_stream=use_stream
    )
    answer = result.choices[0].message.content
    print(answer)
    if answer:
        try:
            # answer = re.sub(r'\s+', '', answer)
            # answer = answer.replace('"，', '", ').replace('}，', '}, ')
            # if answer[:3] != '[{"':
            #     first_occurrence_position = answer.find('{"')
            #     answer = '[' + answer[first_occurrence_position:]
            # if answer[-3:] != '"}]':
            #     last_occurrence_position = answer.rfind('},')
            #     answer = answer[:last_occurrence_position+1]+']'
                content = json.loads(answer)
                print(content)
                return BaseResponse(code=200,msg="生成成功",data=content)
        except Exception as e:
            return BaseResponse(code=-1,msg="生成解析失败",data=e)
    else:
        print("Error:", answer.status_code)
        return BaseResponse(code=-1,msg="生成失败",data={})



def filter_json(json_str):
    if str(json_str).startswith("```json"):
        json_str= json_str[len("```json"):]
    if str(json_str).startswith("```"):
        json_str= json_str[len("```"):]
    if str(json_str).endswith("```json"):
        json_str= json_str[:-7]
    if str(json_str).endswith("```"):
        json_str= json_str[:-3]
    return json_str
    
class GenerateParams(BaseModel):
    context:str = None
    
def generate_qa_pairs(params:GenerateParams):

    client = OpenAI(
    base_url=GENERATE_MODEL_SERVER["base_url"],
    api_key=GENERATE_MODEL_SERVER["api_key"]
    )

    use_stream=False
    
    # if tiltle:
    #     context =tiltle+"\n"+context
        
    messages = [
        {
            "role": "system",
            "content": "仔细阅读用户给出文字，写出尽可能多关于文字内容的问答对。问答应尽量包含细节，比如数字、定义、流程，概念等,问题答案必须明确来自于用户当前给出内容。  \
                       输出格式为Json List,key为question、answer，不需要以```开始 \
                       输出前请仔细检查要生成的内容，如果答案不是来源于用户给出这段文字，该问答不能作为输出结果。"
                           
        },
        {
            "role": "user",
            "content": params.context
        }
    ]
    
    response = client.chat.completions.create(
        model=GENERATE_MODEL_SERVER["model_name"],
        messages=messages,
        stream=use_stream,
        max_tokens=2048,
        temperature=0.4,
        presence_penalty=1.2,
        top_p=0.8,
    )
    if response:
        if use_stream:
            for chunk in response:
                print(chunk)
        else:
            content = response.choices[0].message.content
            json_content = json.loads(content)
            
            return BaseResponse(code=200,msg="成功",data=json_content)
    else:
        print("Error:", response.status_code)
        return BaseResponse(code=-1,msg="失败")

def generate_keywords(params:GenerateParams):

    client = OpenAI(
    base_url=GENERATE_MODEL_SERVER["base_url"],
    api_key=GENERATE_MODEL_SERVER["api_key"]
    )

    use_stream=False
    # if tiltle:
    #     context =tiltle+"\n"+context
        
    messages = [
        {
            "role": "system",
            "content": "仔细阅读用户给出文字，抽取文档中关键字信息。  \
                       输出格式为Json List,不需要以```开始。如: \
                       \"['第三代核电技术','SYSTEM 80+']\" \
                       "
        },
        {
            "role": "user",
            "content": params.context
        }
    ]
    response = client.chat.completions.create(
        model=GENERATE_MODEL_SERVER["model_name"],
        messages=messages,
        stream=use_stream,
        max_tokens=2048,
        temperature=0.4,
        presence_penalty=1.2,
        top_p=0.8,
    )
    if response:
        if use_stream:
            for chunk in response:
                print(chunk)
        else:
            content = response.choices[0].message.content
            print("content",content)
            json_content = json.loads(content)
            return BaseResponse(code=200,msg="成功",data=json_content)
    else:
        print("Error:", response.status_code)
        return BaseResponse(code=-1,msg="失败")

def generate_abstract(params:GenerateParams):

    client = OpenAI(
    base_url=GENERATE_MODEL_SERVER["base_url"],
    api_key=GENERATE_MODEL_SERVER["api_key"]
    )

    use_stream=False
    # if tiltle:
    #     context =tiltle+"\n"+context
        
    messages = [
        {
            "role": "system",
            "content": "仔细阅读用户给出文字，输出这段文字的摘要信息。\n\n \
                 输出格式Json，key为abstract。不需要以```开始,如：\
                    \"{'abstract':'中国核电技术有'}\" \
                 "
            
        },
        {
            "role": "user",
            "content": params.context
        }
    ]
    response = client.chat.completions.create(
        model=GENERATE_MODEL_SERVER["model_name"],
        messages=messages,
        stream=use_stream,
        max_tokens=2048,
        temperature=0.4,
        presence_penalty=1.2,
        top_p=0.8,
    )
    if response:
        if use_stream:
            for chunk in response:
                print(chunk)
        else:
            content = response.choices[0].message.content
            json_content = json.loads(content)
            return BaseResponse(code=200,msg="成功",data=json_content)
    else:
        print("Error:", response.status_code)
        return BaseResponse(code=-1,msg="失败")

    
def generate_query_intent_s(historys,query,keywords):

    client = OpenAI(
    base_url=GENERATE_MODEL_SERVER["base_url"],
    api_key=GENERATE_MODEL_SERVER["api_key"]
    )

    use_stream=False
    # if tiltle:
    #     context =tiltle+"\n"+context
    # 请根据对话记录对当前用户问题进行优化改写以便详细、清楚表达当前问题真实意图，去除问题中指示代词和简称。
    history_context = ""
    historys = historys[:-1]
    for history in historys:
        if len(history_context) >0:
            history_context +="\n"
        history_context+= "'助手'：" if history.role =="assistant" else "'用户'："
        history_context+= "'"+history.content+"'"
    # print(history_context)
    system_prompt = """请先判断当前用户问题是否与历史对话相关：1. 如果当前问题包含指示代词（如"这个"、"那里"、"它"等）或上下文依赖，或者是对前面问题的跟进，请进行改写。2. 如果当前问题是全新的、独立的问题，与历史对话无关，请直接返回原问题，不要改写。当需要改写时，请将用户问题中的指示代词、缩写以及不具体的时间表述替换为明确和具体的名称。注意我们需要的是一个高层次的意图，不需要直接回答用户的问题，不需要添加礼貌用词。结果以JSON格式输出，key为'改写后内容',不需要以```或者```json开头"""
    if keywords:
        system_prompt +="""以下是该领域缩略词对照表：\n缩略语：详细名称\n-----------------"""
        for pair in keywords:
            system_prompt+="\n"+pair[0]+":"+pair[1]
       
    messages = [
        {
            "role": "system",
            # 请依据所提供的“对话内容”，重新表述“当前用户的问题”，确保其表达意图更为清晰。在此过程中，请将用户问题中的指示代词、缩写以及不具体的时间表述替换为明确和具体的细节，以此确保能够精确传达用户所希望表达的确切意图。
            # "content":"""请根据'对话内容'，重新表述“当前用户的问题”。请将用户问题中的指示代词、缩写以及不具体的时间表述替换为明确和具体的细节。注意我们需要的是一个高层次的意图，不需要直接回答用户的问题。结果以JSON格式输出，key为'改写后内容',不需要以```或者```json开头 \
            #         """    
            #  "content":"""你是领域专家，请根据'对话内容'，重写'当前用户的问题'。请将用户问题中的指示代词、缩写以及不具体的时间表述替换为明确和具体的名称。注意我们需要的是一个高层次的意图，不需要直接回答用户的问题。结果以JSON格式输出，key为'改写后内容',不需要以```或者```json开头 \
            #         以下是该领域缩略词对照表：
            #         缩略语：详细名称
            #         -----------------
            #         协会：中国核能行业协会，
            #         核协：中国核能行业协会，
            #         核能行业协会：中国核能行业协会，
            #         数字协会：中国核能行业协会数字协会，
            #         团标：团体标准
            #         我国：中国，
            #         法人：法人代表，
            #         当年：2024年，
            #         当前：2024年9月13日
            #         """    
            "content": system_prompt
        },
        {
            "role": "user",
            "content": "对话内容：\n"+history_context+"\n\n当前用户的问题："+query
        }
    ]

    print(query)
    
    response = client.chat.completions.create(
        model=GENERATE_MODEL_SERVER["model_name"],
        messages=messages,
        stream=use_stream,
        max_tokens=4096,
        temperature=0.4,
        presence_penalty=1.2,
        top_p=0.8,
    )

    
    if response:
        if use_stream:
            for chunk in response:
                print(chunk)
        else:
            try:
                content = response.choices[0].message.content
                content = filter_json(content)
                print(">>>>content",content)
                
                json_content = json.loads(content)
                return BaseResponse(code=200,msg="成功",data=json_content)
            except:
                print("Error:", "parse error")
                return BaseResponse(code=-1,msg="失败",data={})  
    else:
        print("Error:", response.status_code)
        return BaseResponse(code=-1,msg="失败",data={})

class GenerateQueryIntentParams(BaseModel):
    historys:list
    query:str
    
def generate_query_intent(params:GenerateQueryIntentParams):

    return generate_query_intent_s(params.historys,params.query)  
    
class GenerateParagraphParams(BaseModel):
    name:str = None  # 设备名称
    type:str = None  # 设备型号
    kb_ids:list  # 知识选择
    template_config:dict  # 模板选择

def generate_paragraph(params:GenerateParagraphParams):
    # openai.api_base = GENERATE_MODEL_SERVER["base_url"]
    # openai.api_key = GENERATE_MODEL_SERVER["api_key"]
    client = OpenAI(
    base_url=GENERATE_MODEL_SERVER["base_url"],
    api_key=GENERATE_MODEL_SERVER["api_key"]
    )

    use_stream=True
    # 新增根据id查询，前台可选择多个数据库
    # 文档生成，新增加数据库检索、prompt调整
    name = params.name
    type = params.type
    kb_ids = params.kb_ids

    title = params.template_config.get("title")

    # 获取完整title
    temp = []
    if len(title.split(";"))>1:
        for i in title.split(";"):
            if len(i.split())>1:
                temp.append(i.split()[1])
            else:
                temp.append(i)
        title = "的".join(temp)

    else:
        if len(title.split())>1:
            title = title.split()[1]
        else:
            title = title

    # 章节内容要求
    content_prompt = params.template_config.get("content_req")

    # query格式：章名 + 的 + 节名 + 有什么， + 内容要求
    # query查询数据库获取context
    docs = []
    query = title + "有什么，" + content_prompt
    for kb_id in kb_ids:
        d = search_docs_by_id(query, kb_id, top_k=VECTOR_SEARCH_TOP_K, score_threshold=SCORE_THRESHOLD).data
        if len(d)>0:
            docs.extend(d)
    #最相关三个
    if len(docs)>0:
        docs.sort(key=lambda doc:doc.score)
        docs = docs[:3]

    context = ""
    for i in docs:
        context += i.page_content
        context += "\n"

    user_prompt = ""
    if type:
        user_prompt += f"设备类型：{type}\n"
    if name:
        user_prompt += f"设备型号：{name}\n"

    if not user_prompt:
        user_prompt = "请根据以下要求生成内容：\n"
        
    # 内容要求
    if content_prompt:
        user_prompt += "内容要求：" + content_prompt

    if context:
        user_prompt += f"\n\n以下是相关参考资料，请仅作为背景知识参考，不要直接复制：\n{context}"
        user_prompt += "\n\n重要提示：请基于上述参考资料的核心思想，结合文档要求，用您自己的语言重新组织和表达内容。避免直接复制参考资料中的原文，而是要进行理解、整合和创新表达。"
    else:
        user_prompt += "\n\n注意：请根据文档名称和简介，结合您的知识进行内容创作。"

    # 限制
    negative_prompt = params.template_config.get("negative_req")
    if negative_prompt:
        user_prompt += "\n注意请勿输出以下内容：" + negative_prompt
    
    # system prompt：用户、材料要求
    # user prompt：主题、要求、参考资料、限制、目的
    system_content= ""
    if params.template_config.get("role"):
        system_content+=params.template_config.get("role")
    if params.template_config.get("fromat_req"):
        system_content +="\n"
        system_content += "  输出内容要求："+params.template_config.get("fromat_req")


    print("system_content",system_content)
    print("user_content",user_prompt)
    messages = [
        {
            "role": "system",
            "content": system_content
        },
        {
            "role": "user",
            "content": user_prompt
        }
    ]
    
    response = client.chat.completions.create(
        model=GENERATE_MODEL_SERVER["model_name"],
        messages=messages,
        stream=use_stream,
        max_tokens=4096,
        temperature=0.8,
        presence_penalty=1.2,
        top_p=0.9,
    )
    if response:
        if use_stream:
            # for chunk in response:
            #     print(chunk)
            async def stream_response(response):
                for chunk in response:                  
                    # ck = chunk["choices"][0]["delta"]["content"]
                    ck=chunk.choices[0].delta.content
                    import asyncio
                    await asyncio.sleep(0.0001)  
                    yield "data:{}\n\n".format(ck)
            return StreamingResponse(stream_response(response),media_type="text/event-stream")
        else:
            content = response.choices[0].message.content
            return BaseResponse(code=200,msg="成功",data={"result":content})
    else:
        print("Error:", response.status_code)
        return BaseResponse(code=-1,msg="失败")


class GenerateCourseDirectoryParams(BaseModel):
    kb_name:str
    file_name:str

def generate_course_directory(params:GenerateCourseDirectoryParams):
    client = OpenAI(
    base_url=GENERATE_MODEL_SERVER["base_url"],
    api_key=GENERATE_MODEL_SERVER["api_key"]
    )

    use_stream=False
    # 获取知识库
    kb = KBServiceFactory.get_service_by_name(params.kb_name)
    if kb is None:
        return BaseResponse(code=500, msg=f"数据库不存在")
    # 获取文档
    text_list = kb.list_docs(params.file_name)
    result = []
    for t in text_list:
        title = t.metadata['titles']
        if title != '':
            result.append(title)
    # 拼接所有title
    new_out = set(result)
    input_str = '，'.join(e for e in new_out)
    if len(input_str) > 9000:                # Todo glm4-9b-chat 只有8192  后面换glm4-9b-chat-1M
        input_str = input_str[:9000]
    messages = [
        {
            "role": "system",
            "content":"你是一个文档专家，请根据下面可能的标题内容，整理出一个完整的目录结构，结果要宏观，内容要简洁准确，不要有重复，目录的层级最多只有3层，第一层标题为第几章。注意，只输出目录，不要其他内容。"     
        },
        {
            "role": "user",
            "content": input_str
        }
    ]
    response = client.chat.completions.create(
        model=GENERATE_MODEL_SERVER["model_name"],
        messages=messages,
        stream=use_stream,
        max_tokens=8192,
        temperature=0.8,
        presence_penalty=1.2,
        top_p=0.8,
    )
    
    if response:
        if use_stream:
            for chunk in response:
                print(chunk)
        else:
            content = response.choices[0].message.content
            return BaseResponse(code=200,msg="成功",data=content)
    else:
        print("Error:", response.status_code)
        return BaseResponse(code=-1,msg="失败",data={})

class GenerateCourseAbstractParams(BaseModel):
    kb_name:str
    file_name:str

def generate_course_abstract(params:GenerateCourseAbstractParams):
    client = OpenAI(
    base_url=GENERATE_MODEL_SERVER["base_url"],
    api_key=GENERATE_MODEL_SERVER["api_key"]
    )

    use_stream=False
    # 获取知识库
    kb = KBServiceFactory.get_service_by_name(params.kb_name)
    if kb is None:
        return BaseResponse(code=500, msg=f"数据库不存在")
    # 获取文档
    text_list = kb.list_docs(params.file_name)
    result = []
    for t in text_list:
        title = t.metadata['titles']
        if title != '':
            result.append(title)
    # 拼接所有title
    new_out = set(result)
    input_str = '，'.join(e for e in new_out)
    if len(input_str) > 9000:                # Todo glm4-9b-chat 只有8192  后面换glm4-9b-chat-1M
        input_str = input_str[:9000]
    messages = [
        {
            "role": "system",
            "content":"你是一个文档专家，请根据下面的文档内容，生成一段摘要，内容要详尽准确，不要有重复，以“本材料”作为开头。"     
        },
        {
            "role": "user",
            "content": input_str
        }
    ]
    response = client.chat.completions.create(
        model=GENERATE_MODEL_SERVER["model_name"],
        messages=messages,
        stream=use_stream,
        max_tokens=8192,
        temperature=0.8,
        presence_penalty=1.2,
        top_p=0.8,
    )
    if response:
        if use_stream:
            for chunk in response:
                print(chunk)
        else:
            content = response.choices[0].message.content
            return BaseResponse(code=200,msg="成功",data=content)
    else:
        print("Error:", response.status_code)
        return BaseResponse(code=-1,msg="失败",data={})

class GenerateCourseExamParams(BaseModel):
    context: str

def generate_course_exam(params:GenerateCourseExamParams):

    result = generate_course_exam_chunk(params.context)
    pass

def generate_course_exam_chunk(context, exam_type):

    client = OpenAI(
    base_url=GENERATE_MODEL_SERVER["base_url"],
    api_key=GENERATE_MODEL_SERVER["api_key"]
    )

    use_stream=False
    INSTRUCTION = "接下来我会给你一段内容，在内容后会跟随一段指令，请严格按照指令执行。\n\n"
    
    # 根据context长度确定生成题目数量
    question_count = 3
    
    # 问答题
    PROMPT_QA = f"""\n接下来是指令
    1. 你是一个专业的题目生成专家，你需要根据提供的内容准确理解其专业领域，确保生成的题目符合该领域的专业标准，并确保回答是正确的。
    2. 你的任务是根据我给出的内容，生成适合作为大模型微调的问答对数据集，你需要把这次对话的内容与前面对话的内容结合起来理解。
    3. 内容格式参考pdf格式，忽略和图片有关的信息。
    4. Question为情景加问题，情景部分需要描述问题所在的场景以及条件。答案要全面，问题和答案需要来源于提供的内容，内容要更丰富。
    5. 情景要详细准确且全面有辨识度，答案需要和情景和问题强相关。
    6. 请生成{question_count}个问答对。
    7. 输出格式为python格式，最外层为一个python list，在list里面每个问答对为一个python dict。
    8. 以下生成问答对示例，你必须根据严格遵守问答对示例格式：
    [{{"Question": "车子是德龙 M3000 车型，电源部分主要包括哪些", "Answer": "德龙 M3000 车型的电源部分主要包括蓄电池 G100、G101，电源总开关 S4，发电机 G102，以及两路保险丝盒 F604、F605。"}},
    {{"Question": "对于富勒变速箱，富勒变速箱常见的故障有哪些", "Answer": "1换档困难\n一般对刚接触装有富勒变速箱的汽车时，常反映该车起步不好挂档。2变速箱脱(掉)档\n汽车在运行中某一档位经常掉档，特别是在急加速(突然施加负荷)或突然减\n速(丢油门)时较为明显。"}}]
    9. 用于分割Question和Answer的逗号需要用英文逗号字符表示。"""

    # 单选题
    PROMPT_CHOICE = f"""\n接下来是指令
    1. 你是一个专业的题目生成专家，你需要根据提供的内容准确理解其专业领域，确保生成的题目符合该领域的专业标准并严格按照预设的题目格式生成，并确保回答是正确的。
    2. 你的任务是根据我给出的内容，生成考试题目，形式是单项选择题。
    3. Question为题目描述，必须严格按照示例格式：题目内容\nA.选项A\nB.选项B\nC.选项C\nD.选项D，情景部分需要描述问题所在的场景以及条件。
    4. Answer为上面问题的正确答案，应当对应选项中的一个，只需要输出对应正确答案的A、B、C、D选项即可，问题和答案需要来源于提供的内容。
    5. 情景要详细准确且全面有辨识度，答案需要和情景和问题强相关。
    6. 请生成{question_count}个选择题。
    7. 输出格式为python格式，最外层为一个python list，在list里面每个问答对为一个python dict。
    8. 以下生成问答对示例，你必须根据严格遵守问答对示例格式(**重要：题目内容和选项之间必须用"\n"连接,完整的选项及选项内容与下一个选项之间也必须用"\n"连接。)：
    [{{"Question": "航空活塞式发动机的主要机件不包括\nA.活塞\nB.曲杆\nC.轴承\nD.机匣", "Answer": "D"}},
    {{"Question": "对于富勒变速箱，富勒变速箱常见的故障有哪些？\nA. 换档困难\nB. 变速箱脱档\nC. 变速箱掉档\nD.以上都是", "Answer": "D"}}]
    9. 用于分割Question和Answer的逗号需要用英文逗号字符表示。"""

    # 判断题
    PROMPT_JUDGEMENT = f"""\n接下来是指令
    1. 你是一个专业的题目生成专家，你需要根据提供的内容准确理解其专业领域，确保生成的题目符合该领域的专业标准，并确保回答是正确的。
    2. 你的任务是根据我给出的内容，生成考试题目，形式是判断题。
    3. Question为情景和问题的陈述，为一个陈述句，情景部分需要描述问题所在的场景以及条件
    4. Answer为上面问题的判断，只可输出"正确"或者"错误"，不要输出其他内容。问题和答案需要来源于提供的内容。
    5. 情景要详细准确且全面有辨识度，答案需要和情景和问题强相关。
    6. 请生成{question_count}个判断题。
    7. 输出格式为python格式，最外层为一个python list，在list里面每个问答对为一个python dict。
    8. 以下生成问答对示例，你必须根据严格遵守问答对示例格式：
    [{{"Question": "车子是德龙 M3000 车型，发动机是电源部分的组成。", "Answer": "错误"}},
    {{"Question": "对于富勒变速箱，换档困难是富勒变速箱常见的故障。", "Answer": "正确"}}]
    9. 用于分割Question和Answer的逗号需要用英文逗号字符表示。"""

    # 根据题目类型选择对应的提示词
    if exam_type == "选择题":
        PROMPT = PROMPT_CHOICE
    elif exam_type == "判断题":
        PROMPT = PROMPT_JUDGEMENT
    elif exam_type == "问答题":
        PROMPT = PROMPT_QA

    messages = [
        {
            "role": "system",
            "content": INSTRUCTION     
        },
        {
            "role": "user",
            "content": context + PROMPT
        }
    ]
    response = client.chat.completions.create(
        model=GENERATE_MODEL_SERVER["model_name"],
        messages=messages,
        stream=use_stream,
        max_tokens=4096,
        temperature=0.8,
        presence_penalty=1.2,
        top_p=0.8,
    )
    if response:
        json_content = response.choices[0].message.content
        print("content",json_content)
        # json_content = json.loads(content)
        try:
            json_content = re.sub(r'\s+', '', json_content)
            json_content = json_content.replace('"，', '", ').replace('}，', '}, ')
            if json_content[:3] != '[{"':
                first_occurrence_position = json_content.find('{"')
                json_content = '[' + json_content[first_occurrence_position:]
            if json_content[-3:] != '"}]':
                last_occurrence_position = json_content.rfind('},')
                json_content = json_content[:last_occurrence_position+1]+']'
            return json.loads(json_content)
        except:
            return ""
    else:
        print("Error:", response.status_code)
        return ""


from server.db.repository.test_case_repository import test_case_detail

class GenerateExamScoreParams(BaseModel):
    output:str
    test_case_id:int

def generate_exam_score(params:GenerateExamScoreParams):
    client = OpenAI(
    base_url=GENERATE_MODEL_SERVER["base_url"],
    api_key=GENERATE_MODEL_SERVER["api_key"]
    )

    use_stream = False
    PROMPT = """请充当公正的评判者，评价人工智能助手对下面显示的用户问题的回答质量。您的评估应考虑正确性和有意义。您将获得参考答案和助理回答。您的工作是评估助理回答的质量。
    1. 在进行评估之前，请先比较助理的答案和参考答案。不要让答案的长度影响您的评估。
    2. 重点关注参考答案里的数值、组成、步骤等，关注参考答案和助理回答的要点而不是构成结果的组成词，注意要分析参考答案和助理回答之间的相似度，用数值来衡量。
    3. 您的输出应该是 0~100 之间的分数，其中 0 表示助理的回答与参考答案完全不同相似度为0，100 表示助理的回答与参考答案含义一致相似度100%。
    4. 注意：只输出分数，不要输出分析过程和解释。 
    5. 以下是一些示例：
    参考答案：一架飞机要起飞了。助理回答：一架飞机正在起飞。分数：100
    参考答案：一个男人在切面包。助理回答：一个人在切洋葱。分数：40
    参考答案：一个男人在划独木舟。助理回答：一个人在弹竖琴。分数：0
    参考答案：一个男人开着他的车。助理回答：一个男人在开车。分数：80
    参考答案：三个男孩在跳舞。助理回答：孩子们在跳舞。分数：60
    参考答案：一个人一只手握着一只小动物。助理回答：一个男人在炫耀一只小猴子。分数：20
    参考答案：A。助理回答：一个男人在炫耀一只小猴子。分数：0
    参考答案：一个人一只手握着一只小动物。助理回答：A。分数：0
    \n
    """
    PROMPT1 = "请结合文本语义，对以下两段文本进行相似度计算，不要因为文本的长度而影响相似度的计算。\n 您的输出应该是 0~100 之间的分数，其中 0 表示文本一与文本二相似度为0，100 表示文本一与文本二相似度100%。\n 注意：只输出分数，不要输出分析过程和解释。"
    # 查answer
    db_obj = test_case_detail(params.test_case_id, is_detail=True)
    if db_obj["code"] != 0:
        return BaseResponse(code=-1, msg="试题不存在", data={})
    
    question_data = db_obj["data"]
    question_type = question_data["question_type"]
    answer = question_data["answer"]

    if question_type in ["选择题", "判断题"]:
        if params.output.strip() == answer.strip():
            score = 100
        else:
            score = 0
        return BaseResponse(code=200, msg="成功", data=score)
    
    else:
        messages = [
            {
                "role": "system",
                "content": "请严格按照指令执行。\n\n"     
            },
            {
                "role": "user",
                "content": PROMPT + "参考答案：{}, 助理回答：{} 分数：".format(answer, params.output)
                # "content": PROMPT1 + "文本一：{}, 文本二：{}，二者文本相似度为：".format(answer, params.output)
            }
        ]
        print(messages)
        response = client.chat.completions.create(
            model=GENERATE_MODEL_SERVER["model_name"],
            messages=messages,
            stream=use_stream,
            max_tokens=4096,
            temperature=0.8,
            presence_penalty=1.2,
            top_p=0.8
            # top_k=1
        )
        score = 0
        if response:
            content = response.choices[0].message.content
            print("content",content)
            json_content = re.sub(r'\s+', '', content)
            score = re.findall(r"\d+\.?\d*", json_content)
            score = int(score[0])
            return BaseResponse(code=200,msg="成功",data=score)
        else:
            print("Error:", response.status_code)
            return BaseResponse(code=-1,msg="失败",data={})

# 给学生id和考核QA的id查询考题和得分组成exam_result  
def generate_train_proposal(exam_result):
    client = OpenAI(
    base_url=GENERATE_MODEL_SERVER["base_url"],
    api_key=GENERATE_MODEL_SERVER["api_key"]
    )

    use_stream = False
    messages = [
        {
            "role": "system",
            "content":"请严格按照指令执行。\n\n"      
        },
        {
            "role": "user",
            "content": "你是一个装备维修领域的培训老师，请根据下面这个学生的考试题回答情况，分析其学习的薄弱点，并给出培训建议，培训建议的内容一定不要出现题目的题号，类似于“第一道题目”，“第一组题目”都不能出现。下面是该学生的考题及得分：\n {}你给出的培训建议是：".format(exam_result)
        }
    ]
    response = client.chat.completions.create(
        model=GENERATE_MODEL_SERVER["model_name"],
        messages=messages,
        stream=use_stream,
        max_tokens=4096,
        temperature=0.8,
        presence_penalty=1.2,
        top_p=0.8,
    )
    if response:
        if use_stream:
            for chunk in response:
                print(chunk)
        else:
            content = response.choices[0].message.content
            print("content",content)
            # json_content = json.loads(content)
            return BaseResponse(code=200,msg="成功",data=content)
    else:
        print("Error:", response.status_code)
        return BaseResponse(code=-1,msg="失败",data={})

from server.http_api.user_api import token_check
from fastapi import Depends
from server.db.repository.test_case_repository import get_qa_by_vsid
from typing import Optional
from server.db.repository.knowledge_file_repository import get_file_detail

class PagegetqaParams(BaseModel):
    file_name:str
    page_no: Optional[int] = None
    kb_name:str
    qa_count: Optional[int] = None

def page_get_qa(params:PagegetqaParams):
     
    kb = KBServiceFactory.get_service_by_name(params.kb_name)

    if kb is None:
        return BaseResponse(code=200, msg="无知识库", data={})
    
    file_info = get_file_detail(kb_name=params.kb_name, file_name=params.file_name)
    
    if file_info and file_info.get("qa_status") == "未生成":
        return BaseResponse(code=200, msg="问答对未生成", data=[])
    
    qa_pairs = []
    
    if params.page_no is None:
        from server.db.repository.test_case_repository import get_qa_by_kb_and_file
        
        qa_response = get_qa_by_kb_and_file(params.kb_name, params.file_name)
        if qa_response["code"] == 0:
            for qa in qa_response["data"]:
                question = qa.get("question")
                answer = qa.get("answer")
                if question and answer:
                    qa_pairs.append({"question": question, "answer": answer})
    else:
        docs = kb.list_docs(params.file_name)
        for doc in docs:
            if doc:
                content_pos = doc.metadata.get("content_pos", [])
                for content in content_pos:
                    if content.get("page_no") == params.page_no:
                        vs_id = doc.metadata.get("vs_id")
                        qa_response = get_qa_by_vsid(vs_id=vs_id)
                        if qa_response["code"] == 0:
                            for qa in qa_response["data"]:
                                question = qa.get("question")
                                answer = qa.get("answer")
                                if question and answer:
                                    qa_pairs.append({"question": question, "answer": answer})

    if params.qa_count is not None:
        qa_pairs = qa_pairs[:min(params.qa_count, len(qa_pairs))]
        
    return BaseResponse(code=200, msg="成功", data=qa_pairs)

from fastapi import File, Form, Body, Query, UploadFile
from urllib.parse import urlencode
import os
import shutil

def logo_get(
    file: UploadFile = File(..., description="上传文件"),
) -> BaseResponse:

    project_root = os.getcwd()

    logo_dir = os.path.join(project_root, "img")
    if not os.path.exists(logo_dir):
        os.makedirs(logo_dir)

    file_location = os.path.join(logo_dir, file.filename)

    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    _image_filename = os.path.basename(file_location)
    # 使用相对路径
    file_location_relative = os.path.join("img", file.filename)
    _image_url_request_parameters = urlencode({"filepath": file_location_relative, "filename": _image_filename})
    _image_url = f"knowledge_base/download_img?" + _image_url_request_parameters

    return BaseResponse(code=200, msg="文件上传成功", data={"download_url": _image_url})


class GenerateExamScoreNewParams(BaseModel):
    output: str # 用户答案
    answer: str # 参考答案

def generate_exam_score_new(params:GenerateExamScoreNewParams):
    client = OpenAI(
    base_url=GENERATE_MODEL_SERVER["base_url"],
    api_key=GENERATE_MODEL_SERVER["api_key"]
    )

    use_stream = False
    PROMPT = """请充当公正的评判者，评价人工智能助手对下面显示的用户问题的回答质量。您的评估应考虑正确性和有意义。您将获得参考答案和用户回答。您的工作是评估用户回答的质量。
    1. 在进行评估之前，请先比较助理的答案和参考答案。不要让答案的长度影响您的评估。
    2. 重点关注参考答案里的数值、组成、步骤等，关注参考答案和用户回答的要点而不是构成结果的组成词，注意要分析参考答案和用户回答之间的相似度，用数值来衡量。
    3. 您的输出应该是 0~100 之间的分数，其中 0 表示用户回答与参考答案完全不同相似度为0，100 表示用户回答与参考答案含义一致相似度100%。
    4. 注意：先输出分数，然后换行输出分析得分点和解释。 
    5. 以下是一些示例：
    参考答案：一架飞机要起飞了。用户回答：一架飞机正在起飞。分数：100 分析：用户回答的“一架飞机”和答案中“一架飞机”一致；“要起飞”和“正在起飞”含义一致。所以得100分。
    参考答案：一个男人在切面包。用户回答：一个人在切洋葱。分数：40 分析：用户回答“一个人”，而答案是“一个男人”，不够准确；用户回答是“切洋葱”，而答案是“切面包”，动作是对的但是主体错误。所以得40分。
    参考答案：一个男人在划独木舟。用户回答：一个人在弹竖琴。分数：0 分析：用户回答“一个人”，而答案是“一个男人”，不够准确；用户回答是“弹竖琴”，而答案是“划独木舟”，动作和主体都是错误得。所以得0分。
    参考答案：一个男人开着他的车。用户回答：一个男人在开车。分数：80 分析：用户回答的“一个男人”和答案中“一个男人”一致；用户回答是“在开车”，答案是“开着他的车”，用户的回答没有说明是谁的车。所以得80分。
    参考答案：三个男孩在跳舞。用户回答：孩子们在跳舞。分数：60 分析：用户回答是“孩子们”，答案中是“三个男孩”，回答没有指明性别也没有指明人数；用户回答和答案都是“在跳舞”。所以得60分。
    参考答案：一个人一只手握着一只小动物。用户回答：一个男人在炫耀一只小猴子。分数：20 分析：用户回答“一个人”，而答案是“一个男人”，不够准确；“炫耀一只小猴子”和“手握着一只小动物”含义不一致但是有一点点类似。所以得20分。
    参考答案：A。用户回答：一个男人在炫耀一只小猴子。分数：0 分析：用户回答的内容和答案完全不一样，语义也完全不一样。所以得0分。
    参考答案：一个人一只手握着一只小动物。用户回答：A。分数：0 分析：用户回答的内容和答案完全不一样，语义也完全不一样。所以得0分。
    \n
    """

    messages = [
        {
            "role": "system",
            "content": "请严格按照指令执行。\n\n"      
        },
        {
            "role": "user",
            "content": PROMPT + "参考答案：{}, 助理回答：{} 分数：".format(params.answer, params.output)
        }
    ]
    print(messages)
    response = client.chat.completions.create(
        model=GENERATE_MODEL_SERVER["model_name"],
        messages=messages,
        stream=use_stream,
        max_tokens=4096,
        temperature=0.8,
        presence_penalty=1.2,
        # top_p=0.8,
        top_k=1
    )
    score = 0
    if response:
        content = response.choices[0].message.content
        print("content",content)
        # json_content = re.sub(r'\s+', '', content)
        score = content.split("分析：")[0].strip()
        score_new = re.sub(r'\s+', '', score)
        analyse = content.split("分析：")[-1].strip()
        # score = re.findall(r"\d+\.?\d*", json_content)
        res = {"score": score, "analyse": analyse}
        return BaseResponse(code=200,msg="打分成功",data=res)
    else:
        print("Error:", response.status_code)
        return BaseResponse(code=-1,msg="打分失败",data={})

class GenerateCourseExamNewParams(BaseModel):
    num: int
    context: str
    exam_type: str   # choice/multi_choice/filling/judgement/QA

def generate_course_exam_new(params:GenerateCourseExamNewParams):
    client = OpenAI(
    base_url=GENERATE_MODEL_SERVER["base_url"],
    api_key=GENERATE_MODEL_SERVER["api_key"]
    )

    context = params.context
    use_stream=False
    exam_num = params.num
    INSTRUCTION = "接下来我会给你一段内容，在内容后会跟随一段指令，请严格按照指令执行。\n\n"
    # 简答
    PROMPT1 = """\n接下来是指令
    1. 你是一个装备维修方面专家，你需要确保你的回答是正确的。
    2. 你的任务是根据我给出的内容，生成适合作为大模型微调的问答对数据集，你需要把这次对话的内容与前面对话的内容结合起来理解，生成问答对的数量必须是{}。""".format(exam_num)
    PROMPT1 += """
    3. 内容格式参考pdf格式，忽略和图片有关的信息。
    4. Question为情景加问题，情景部分需要描述问题所在的场景以及条件。答案要全面，问题和答案需要来源于提供的内容，内容要更丰富。
    5. 情景要详细准确且全面有辨识度，答案需要和情景和问题强相关。
    6. 输出格式为python格式，最外层为一个python list，在list里面每个问答对为一个python dict。
    7. 以下生成问答对示例，你必须根据严格遵守问答对示例格式：
    [{"Question": "车子是德龙 M3000 车型，电源部分主要包括哪些", "Answer": "德龙 M3000 车型的电源部分主要包括蓄电池 G100、G101，电源总开关 S4，发电机 G102，以及两路保险丝盒 F604、F605。"},
    {"Question": "对于富勒变速箱，富勒变速箱常见的故障有哪些", "Answer": "1换档困难\n一般对刚接触装有富勒变速箱的汽车时，常反映该车起步不好挂档。2变速箱脱(掉)档\n汽车在运行中某一档位经常掉档，特别是在急加速(突然施加负荷)或突然减\n速(丢油门)时较为明显。"}]
    8. 用于分割Question和Answer的逗号需要用英文逗号字符表示。"""

    # 单选
    PROMPT2 = """\n\n接下来是指令
    1. 你是一个装备维修方面专家，你需要确保你的回答是正确的。
    2. 你的任务是根据我给出的内容，生成考试题目，形式是单项选择题，生成题目的数量必须是{}。""".format(exam_num)
    PROMPT2 += """
    3. Question为情景加问题，情景部分需要描述问题所在的场景以及条件
    4. Options为上面问题的侯选答案，对应A、B、C、D4个选项。
    5. Answer为上面问题的正确答案，应当对应选项中的一个，只需要输出对应正确答案的A、B、C、D选项即可，问题和答案需要来源于提供的内容。
    6. 情景要详细准确且全面有辨识度，答案需要和情景和问题强相关。
    7. 输出格式为python格式，最外层为一个python list，在list里面每个问答对为一个python dict。
    8. 以下生成问答对示例，你必须根据严格遵守问答对示例格式：
    [{"Question": "车子是德龙 M3000 车型，哪一项不是电源部分的组成", "Options": ["A.蓄电池 G100、G101", "B.电源总开关 S4", "C. 发电机 G102", "D.发动机"] , "Answer": "D"},
    {"Question": "对于富勒变速箱，富勒变速箱常见的故障有哪些？", "Options": ["A. 换档困难", "B. 变速箱脱档", "C. 变速箱掉档", "D.以上都是"], "Answer": "D"}]
    9. 用于分割Question和Answer的逗号需要用英文逗号字符表示。"""

    # 多选
    PROMPT3 = """\n\n接下来是指令
    1. 你是一个装备维修方面专家，你需要确保你的回答是正确的。
    2. 你的任务是根据我给出的内容，生成考试题目，形式是多项选择题，生成题目的数量必须是{}。""".format(exam_num)
    PROMPT3 += """
    3. Question为情景加问题，情景部分需要描述问题所在的场景以及条件
    4. Options为上面问题的侯选答案，对应A、B、C、D4个选项。
    5. Answer为上面问题的正确答案，应当对应Options中的多个选项，Answer的个数必须是2个或3个或4个，只需要输出对应正确答案的A、B、C、D选项即可，问题和答案需要来源于提供的内容。
    6. 情景要详细准确且全面有辨识度，答案需要和情景和问题强相关。
    7. 输出格式为python格式，最外层为一个python list，在list里面每个问答对为一个python dict。
    8. 以下生成问答对示例，你必须根据严格遵守问答对示例格式：
    [{"Question": "车子是德龙 M3000 车型，哪一项是电源部分的组成", "Options": ["A.蓄电池 G100、G101", "B.电源总开关 S4", "C. 发电机 G102", "D.发动机"] , "Answer": "ABC"},
    {"Question": "对于富勒变速箱，富勒变速箱常见的故障有哪些？", "Options": ["A. 换档困难", "B. 变速箱脱档", "C. 变速箱破损", "D.变速箱掉档"], "Answer": "ABD"}]
    9. 用于分割Question和Answer的逗号需要用英文逗号字符表示。"""

    # 判断
    PROMPT4 = """\n\n接下来是指令
    1. 你是一个专家，你需要确保你的回答是正确的。
    2. 你的任务是根据我给出的内容，生成考试题目，形式是判断题，生成题目的数量必须是{}。""".format(exam_num)
    PROMPT4 += """
    3. Question为情景和问题的陈述，为一个陈述句，情景部分需要描述问题所在的场景以及条件
    4. Answer为上面问题的判断，只可输出“正确”或者“错误”，不要输出其他内容。问题和答案需要来源于提供的内容。
    5. 情景要详细准确且全面有辨识度，答案需要和情景和问题强相关。
    6. 输出格式为python格式，最外层为一个python list，在list里面每个问答对为一个python dict。
    7. 以下生成问答对示例，你必须根据严格遵守问答对示例格式：
    [{"Question": "车子是德龙 M3000 车型，发动机是电源部分的组成。", "Answer": "错误"},
    {"Question": "对于富勒变速箱，换档困难是富勒变速箱常见的故障。", "Answer": "正确"}]
    8. 用于分割Question和Answer的逗号需要用英文逗号字符表示。"""

    # 填空
    PROMPT5 = """\n\n接下来是指令
    1. 你是一个专家，你需要确保你的回答是正确的。
    2. 你的任务是根据我给出的内容，生成考试题目，形式是填空题，生成题目的数量必须是{}。""".format(exam_num)
    PROMPT5 += """
    3. Question为情景和问题陈述，为一个陈述句，情景部分需要描述问题所在的场景以及条件，问题中去除部分内容以空括号()代替。
    4. Answer为上面填空部分的回答，以list形式输出，每一个元素对应Question中一个空括号()，不要输出其他内容。问题和答案需要来源于提供的内容。
    5. 情景要详细准确且全面有辨识度，答案需要和情景和问题强相关。
    6. 输出格式为python格式，最外层为一个python list，在list里面每个问答对为一个python dict。
    7. 以下生成问答对示例，你必须根据严格遵守问答对示例格式：
    [{"Question": "车子是德龙 M3000 车型，（）、（）、（）是电源部分的组成。", "Answer": ["蓄电池", "电源总开关", "发电机"]"},
    {"Question": "对于富勒变速箱，富勒变速箱常见的故障有（）、（）、（）。", "Answer": ["换档困难", "变速箱脱档","变速箱掉档"]}]
    8. 用于分割Question和Answer的逗号需要用英文逗号字符表示。"""

    if params.exam_type == "QA":
        PROMPT = PROMPT1
    elif params.exam_type == "choice":
        PROMPT = PROMPT2
    elif params.exam_type == "multi_choice":
        PROMPT = PROMPT3
    elif params.exam_type == "judgement":
        PROMPT = PROMPT4
    elif params.exam_type == "filling":
        PROMPT = PROMPT5
    else:
        return BaseResponse(code=-1,msg="未知题目类型",data=e)

    messages = [
        {
            "role": "system",
            "content": INSTRUCTION     
        },
        {
            "role": "user",
            "content": context + PROMPT
        }
    ]
    response = client.chat.completions.create(
        model=GENERATE_MODEL_SERVER["model_name"],
        messages=messages,
        stream=use_stream,
        max_tokens=4096,
        temperature=0.8,
        presence_penalty=1.2,
        top_p=0.8,
    )
    if response:
        json_content = response.choices[0].message.content
        # print("content",json_content)
        # json_content = json.loads(content)
        try:
            json_content = re.sub(r'\s+', '', json_content)
            json_content = json_content.replace('"，', '", ').replace('}，', '}, ')
            if json_content[:3] != '[{"':
                first_occurrence_position = json_content.find('{"')
                json_content = '[' + json_content[first_occurrence_position:]
            if json_content[-3:] != '"}]':
                last_occurrence_position = json_content.rfind('},')
                json_content = json_content[:last_occurrence_position+1]+']'
            # return json.loads(json_content)
            # print(json_content)
            content = json.loads(json_content)
            return BaseResponse(code=200,msg="生成成功",data=content)
        except Exception as e:
            return BaseResponse(code=-1,msg="生成解析失败",data=e)
    else:
        print("Error:", response.status_code)
        return BaseResponse(code=-1,msg="生成失败",data={})

from configs.model_config import MODEL_PATH

def list_embedding_model()-> BaseResponse:
    embedding_models = list(MODEL_PATH.get("embed_model", {}).keys()) 
    return BaseResponse(code=200, msg="成功", data=embedding_models)

from document_loaders.mypdfloader import progress_queue

class ProgressParams(BaseModel):
    kb_name: str =  None
    file_name: str = None

def get_progress(params:ProgressParams):
    kb_name = params.kb_name
    file_name = params.file_name
    if file_name.lower().endswith(('.doc', '.docx')):
        file_name = file_name.rsplit('.', 1)[0] + '.pdf'
        
    def generate(kb_name=None, file_name=None):
        while True:
            progress = progress_queue.get()
            print(f"Received progress: {progress}")

            if (kb_name is None or progress.get("kb_name") == kb_name) and (file_name is None or progress.get("file_name") == file_name):
                yield f"data:{json.dumps(progress, ensure_ascii=False)}\n\n"

            if progress.get("progress") == "100.00%":
                break

    return StreamingResponse(generate(kb_name, file_name), media_type='text/event-stream')

from server.db.repository.knowledge_file_repository import get_docs_detail,add_abstract_to_db

class GenerateChapterAbstractParams(BaseModel):
    kb_name: str
    file_name: str

def generate_chapter_abstract(params: GenerateChapterAbstractParams):

    use_stream = False

    kb_name = params.kb_name
    file_name = params.file_name
    if file_name.lower().endswith(('.doc', '.docx')):
        file_name = file_name.rsplit('.', 1)[0] + '.pdf'

    docs = get_docs_detail(kb_name, file_name)
    if not docs:
        return BaseResponse(code=500, msg="未找到相关文档")

    docs.sort(key=lambda x: x["metadata"]["content_pos"][0]["page_no"])

    content_by_title = {}
    pending_content = []
    for doc in docs:
        metadata = doc["metadata"]
        page_content = doc["page_content"]
        titles = metadata.get("titles", "")

        if "#" in titles:
            title = titles.split("#")[0]
        else:
            title = titles.strip()

        if not title:
            pending_content.append(page_content)
        else:
            if pending_content:
                if title not in content_by_title:
                    content_by_title[title] = []
                content_by_title[title].extend(pending_content)
                pending_content = []

            if title not in content_by_title:
                content_by_title[title] = []
            content_by_title[title].append(page_content)
    
    if pending_content:
        last_title = list(content_by_title.keys())[-1] if content_by_title else "未分类章节"
        if last_title not in content_by_title:
            content_by_title[last_title] = []
        content_by_title[last_title].extend(pending_content)

    result = []
    for title, contents in content_by_title.items():
        combined_content = "\n".join(contents)
        abstracts = []

        # 如果内容超过5000 tokens，分段处理
        if len(combined_content) > 5000:
            chunks = [combined_content[i:i + 5000] for i in range(0, len(combined_content), 5000)]
            for chunk in chunks:
                abstract = get_summary_from_model(chunk, title, use_stream)
                if abstract:
                    abstracts.append(abstract)
            # 对分段摘要进行整合生成连贯的章节摘要
            combined_abstract = get_summary_from_model(" ".join(abstracts), title, use_stream)
        else:
            combined_abstract = get_summary_from_model(combined_content, title, use_stream)

        if combined_abstract:
            result.append({"titles": title, "page_content": combined_abstract})

    full_content = "\n".join(item["page_content"] for item in result)
    full_abstract = ""

    if len(full_content) > 5000:
        chunks = [full_content[i:i + 5000] for i in range(0, len(full_content), 5000)]
        full_abstract_parts = []
        for chunk in chunks:
            part_abstract = get_summary_from_model(chunk, "全文摘要", use_stream)
            if part_abstract:
                full_abstract_parts.append(part_abstract)
        full_abstract = get_summary_from_model(" ".join(full_abstract_parts), "全文摘要", use_stream)

    else:
        full_abstract = get_summary_from_model(full_content, "全文摘要", use_stream)

    result = {"titles": "全文摘要", "page_content": full_abstract}
    # result.append({"titles": "全文摘要", "page_content": full_abstract})
    # add_abstract_to_db(params.kb_name, params.file_name, result)
    
    return BaseResponse(code=200, msg="成功", data=result)

def get_summary_from_model(content, title, use_stream):
    """
    调用模型生成摘要
    """

    client = OpenAI(
    base_url=GENERATE_MODEL_SERVER["base_url"],
    api_key=GENERATE_MODEL_SERVER["api_key"]
    )

    messages = [
        {
            "role": "system",
            "content": f"你是一个文档专家，请根据以下内容生成一段围绕主题'{title}'的摘要。摘要需要准确、连贯且不能超过500字。"
        },
        {
            "role": "user",
            "content": content
        }
    ]
    
    try:
        response = client.chat.completions.create(
            model=GENERATE_MODEL_SERVER["model_name"],
            messages=messages,
            stream=use_stream,
            max_tokens=8192,
            temperature=0.8,
            presence_penalty=1.2,
            top_p=0.8,
        )

        if response:
            if use_stream:
                for chunk in response:
                    print(chunk)
            else:
                return response.choices[0].message.content
        else:
            print("Error: No response from model.")
            return ""
    except Exception as e:
        print(f"Error during model call: {e}")
        return ""

from version_update import (
    # migrate_eval_history,
    # migrate_course_table,
    # migrate_knowledge_base_table,
    # migrate_knowledge_file_table,
    # migrate_file_doc_table,
    # migrate_test_case_table,
    # update_knowledge_file_with_test_case_count,
    # update_file_doc_page_content,
    file_layout
)

# def run_all_migrations():
#     """
#     调用所有数据库迁移函数，按顺序完成数据库更新
#     """
#     try:
#         migrate_eval_history()
#         migrate_course_table()
#         migrate_knowledge_base_table()
#         migrate_knowledge_file_table()
#         migrate_file_doc_table()
#         migrate_test_case_table()
#         update_knowledge_file_with_test_case_count()
#         update_file_doc_page_content()

#         return {"code": 0, "msg": "所有数据库迁移完成"}

#     except Exception as e:
#         return {"code": 500, "msg": "数据库迁移失败", "error": str(e)}

from typing import Optional


def layout_file(
        file: UploadFile = File(..., description="上传单个文件"),
        page_start: Optional[int] = Body(None, description="起始页"),
        page_end: Optional[int] = Body(None, description="结束页"),
) -> BaseResponse:
    
    project_root = os.getcwd()
    
    filename_without_ext = os.path.splitext(file.filename)[0]
    
    input_dir = os.path.join(project_root, "layout_file", filename_without_ext, "input")
    output_dir = os.path.join(project_root, "layout_file", filename_without_ext, "output")
    image_dir = os.path.join(project_root, "layout_file", filename_without_ext, "image")
    
    for dir_path in [input_dir, output_dir, image_dir]:
        if os.path.exists(dir_path):
            for file_item in os.listdir(dir_path):
                file_path_to_remove = os.path.join(dir_path, file_item)
                if os.path.isfile(file_path_to_remove):
                    os.remove(file_path_to_remove)
                elif os.path.isdir(file_path_to_remove):
                    shutil.rmtree(file_path_to_remove)
    
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(image_dir, exist_ok=True)

    file_path = os.path.join(input_dir, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    result = file_layout(file_path, page_start, page_end, output_dir, filename_without_ext)

    return BaseResponse(code=200, msg="成功", data=result)

from server.http_api.user_api import admin_token_check
from server.utils import get_prompt_template
from configs import (LLM_MODELS,VECTOR_SEARCH_TOP_K,SCORE_THRESHOLD,LLM_MODELS,ONLINE_LLM_MODEL,GENERATE_MODEL_SERVER)

def get_chat_default_config(current_user_dict=Depends(admin_token_check)):
    prompt = get_prompt_template("knowledge_base_chat", "default")
    temperature = 0.95
    score_threshold = SCORE_THRESHOLD
    top_k = VECTOR_SEARCH_TOP_K

    Infer_server_api = [
        {"model_title": model, **ONLINE_LLM_MODEL[model]}
        for model in LLM_MODELS
        if model in ONLINE_LLM_MODEL
    ]
    
    gen_server_api = GENERATE_MODEL_SERVER
    
    chat_default_config={
        "prompt": prompt,
        "temperature": temperature,
        "score_threshold": score_threshold,
        "top_k": top_k,
        "history_len": 6,
        "Infer_server_api": Infer_server_api,
        "gen_server_api": gen_server_api
    }

    return {"code": 0, "msg": "获取默认配置成功", "data":chat_default_config}

if __name__ == "__main__":
    # simple_chat(use_stream=True)
    # function_chat(use_stream=False)
    # context = "非动能安全先进核电厂AP1000\n0.1.1世界核电的发展简史\n核电厂已经历了50余年的发展历史，核电厂的开发与建设开始于20世纪50年代。1954年，前苏联建成电功率为5MW的实验性核电厂；1957年，美国建成电功率为90 MW的希平港原型核电厂；这些成就证明了利用核能发电的技术是可行的。国际上把上述实验性和原型核电机组称为第一代核电机组。" \
    #           "20世纪60年代后期，在试验性和原型核电机组基础上，陆续建成电功率在300 MW以上的压水堆、沸水堆、重水堆等核电机组，它们在进一步证明核能发电技术可行性的同时，使核电的经济性也得以证明，它可与火电、水电相竞争。" \
    #           "20世纪70年代，因石油涨价引发的能源危机促进了核电的发展，目前世界上商业运行的400多台核电机组绝大部分是在这段时期建成的，它们称为第二代核电机组，其中压水堆(PWR、VVER)和沸水堆(BWR) 占了大部分。" \
    #           "1979年以前，人们普遍认为核电是安全、清洁的能源。由于1979年和1986年先后发生在三里岛和切尔诺贝利核电厂的严重事故，使社会公众开始对核电安全性产生了疑虑，电力投资者也放慢了对核电的投资步伐，核电发展进入低潮。但中国、法国、日本和韩国等国家发展核电的方针仍然没有改变，认为核电厂的安全性是能够改进、提高的。" \
    #           "20世纪80年代，虽然美国撤销了不少拟建的核电项目，但没有放弃发展核电事业的可行性研究。美国能源部和电力研究院的研究结果认为：以已有的核电经验和技术水平为基础，美国能够设计出新一代核电机组，其安全性能为社会公众和电力投资者所认可，其经济性具备参与市场竞争的能力。进而美国电力研究院于90年代出台了“先进轻水堆用户要求”文件，即URD文件(UtilityRequirementsDocument),用一系列定量指标来规范核电厂的安全性和经济性。" \
    #           "随后，欧洲出台的“欧洲用户对轻水堆核电厂的要求”,即EUR(EuropeanUtilityRequirements)文件，也表达了与URD文件相同或相似的看法。国际原子能机构也对其推荐的核安全法规(NUSS系列)进行了修订补充，进一步明确了防范与缓解严重事故、提高安全可靠性和改善人因工程等方面的要求。" \
    #           "世界400多台核电机组至今累积了12000多堆·年的运行经验，切尔诺贝利事故发生后的20多年间，世界上的核电机组无重大事故发生，这说明核电厂改进措施已见成效，核电安全性和经济性都有所提高。但公众和用户对发展核电仍有疑虑，还必须着力解决以下问题" \
    #           "(1)进一步降低堆芯熔化和放射性向环境释放的风险，使发生严重事故的概率减小到极致，以消除社会公众的顾虑；" \
    #           "(2)进一步减少核废物(特别是强放射性和长寿命核废物)的排放量，寻求更佳的核废物处理方案，减少对人员和环境的放射性影响；" \
    #           "(3)降低核电厂每单位千瓦的造价，缩短建设周期，提高机组热效率和可利用率，延长寿期，以进一步改善其经济性。" \
    #           "美国URD文件、欧洲EUR文件和国际原子能机构NUSS建议法规修订的第二版就是主要依据上述目标而提出的。国际上通常把满足URD文件或EUR文件的核电机组称为第三代核电机组，第三代是在第二代技术的基础上进行改进的，采用了可以马上推向市场的成熟技术，包括：ABWR、SYSTEM 80+、AP600、AP1000、EPR等。上述前四种堆型获得了美国核监管委员会(USNuclearRegulatoryCommission,NRC)的设计批准，可以申请建造和运行，EPR的设计也获得法国核安全当局认可。目前，只有两台第三代的ABWR在日本运行。" \
    #           "与此同时，为了从更长远的核能的可持续发展着想，以美国为首的一些工业发达国家已经联合起来组成“第四代国际核能论坛”(GenerationIVInterna-tionalNuclearEnergyForum,GIFIV),进行第四代核能利用系统的研究和开发。第四代是指安全性和经济性都更加优越，废物量极少，无需厂外应急，并具有防核扩散能力的核能利用系统。在候选的六种四代堆型(钠冷快堆、气冷快堆、铅冷快堆、极高温气冷堆、熔盐堆和超临界水堆)中，有技术基础和有具体发展计划的是极高温气冷堆和钠冷快堆。美法日共同投资的钠冷快堆原型机组预计在21世纪中叶建成。美国优先开发的极高温气冷堆原型机组，将在2030年后(尚无具体项目和时间)建成。核电厂发展的阶段见图0.1。" \
    #           "第三代 + 革新型设计第三代第三代改进型设计第二代第一代先进轻水堆商用动力堆早期原型堆" \
    #           "-经济性更好" \
    #           "-安全性更好" \
    #           "-ABWR" \
    #           "-废物最少" \
    #           "-CANDU 6 -" \
    #           "-防止核扩散" \
    #           "-PWRs" \
    #           "-System 80+ ACR1000" \
    #           "-希平港(美)" \
    #           "-BWRs -AP600 -AP1000" \
    #           "-德累斯顿，费米一号(美)" \
    #           "-CANDU -ARWR" \
    #           "-MagnoxEEPSRBWR" \
    #           "1950 1960 1970 1980 1990 2000 2010 2020 2030(icn" \
    #           "(icnGenIII+ GenIV" \
    #           "图0.1 核电厂发展的阶段"

    # result = generate_qa_pairs(context)
    # result = generate_keywords(context)
    # result = generate_abstract(context)
    
    result = generate_query_intent(GenerateQueryIntentParams(context="",query="EQ1108现在还装备部队吗？"))
    result = generate_query_intent(GenerateQueryIntentParams(context="",query="X5000重卡发动机冒烟"))
    result = generate_query_intent(GenerateQueryIntentParams(context="",query="L3000S卡车无法启动？"))
    result = generate_query_intent(GenerateQueryIntentParams(context="",query="今天吃了吗？"))
    result = generate_query_intent(GenerateQueryIntentParams(context="",query="杭州天气怎么样？"))
    result = generate_query_intent(GenerateQueryIntentParams(context="",query="能介绍一下杭州吗？"))
    result = generate_query_intent(GenerateQueryIntentParams(context="",query="能帮给我一张AP1000的原理图吗"))
    result = generate_query_intent(GenerateQueryIntentParams(context="",query="核电厂的设计图？"))
    
    # print(result)
    # result = result.data
    # for r in result:
    #     print("q",r["question"])
    #     print("a", r["answer"])
    # request_block()
    
    # role= "你是一位严谨的课程设计专家，请根据以下要求撰写课程方案章节正文。"
    # background= "你要写的内容是《汽车维修专业国家技能人才培养工学一体化课程设置方案》的某些章节内容正文"
    # # subject= "一、适用范围"
    # # content_req= "- 以’本方案‘开始\n - 包含方案的适用范围(初中起点三年中级、高中起点三年高级、初中起点五年高级、高中起点四年预备技师、初中起点六年预备技师 )"
    # # format= "文本为辅，表格为主"
    # # subject= "三、课程设置"
    # # content_req= "说明课程的类别和课程名称\n 课程类别包含公共，专业基础，工学一体化，选修等四大类。"
    # # format= "表格,以markdown形式的html"
    # subject= "四、教学安排建议"
    # content_req= "- 教学安排建议是对范围内课程进行学时和教学安排表。\
    # - 首先需要思考该方案的针对哪些专业, 每个专业培养计划输出一张教学安排表，\
    # - 教学安排表包含哪些内容\
    # - 每个专业有哪些课程\
    # - 每门课程属于什么课程类别，安排在那个学期教学\
    # - 内容详细"
    # format= "表格"
    # example= None
    # negative_req = None
    # ref ="- 该方案的主要覆盖初中起点三年中级、高中起点三年高级两个专业 \
    #       - 教学安排表包含课程类别，课程名称，学时，安排的学期四个表头 \
    #       - 课程类别包含公共，专业基础，工学一体化，选修等四大类 \
    # "
    # result = generate_paragraph(role,background,subject,content_req,format,example,negative_req,ref)
    # print(result)
