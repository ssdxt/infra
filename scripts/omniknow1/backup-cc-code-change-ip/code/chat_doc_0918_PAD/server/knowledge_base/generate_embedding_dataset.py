import sys
sys.path.append('/mnt/ddata/chat_doc')
from fastapi import File, Form, Body
from server.knowledge_base.kb_service.base import KBServiceFactory
from pydantic import BaseModel
from server.utils import BaseResponse
import os
import json
import openai
import re
from server.knowledge_base.kb_doc_api import list_doc_block
from server.knowledge_base.kb_doc_api import search_docs
from openai import OpenAI
from configs.model_config import GENERATE_MODEL_SERVER

# base_url = "http://192.168.21.111:10005/v1"
# openai.api_key = "EMPTY"
# openai.api_base = base_url


def generate_embedding_dataset(
        kb_name: str = Body(..., description="知识库名称", examples=["测试"]),
        file_name: str = Body(..., description="文档名称", examples=["非能动安全先进核电厂ap1000.pdf"]),
        output_file: str = Body(..., description="输出路径", examples=["你好"]),
        llm_generate: bool = Body(False, description="是否使用llm生成"),
):

    client = OpenAI(
        base_url=GENERATE_MODEL_SERVER["base_url"],
        api_key=GENERATE_MODEL_SERVER["api_key"]
        )
    # all_blocks = []
    # for file in file_name:
    #     blocks = list_doc_block(kb_name=kb_name, file_name=file).data
    #     blocks = blocks['blocks']
    #     all_blocks.extend(blocks)
    all_blocks = list_doc_block(kb_name=kb_name, file_name=file_name).data
    all_blocks = all_blocks['blocks']

    if os.path.exists(output_file):
        os.remove(output_file)


    for blocks in all_blocks:
        chunk_tent = blocks.page_content

        
        for block in blocks.metadata['test_cases']:
            docs = []
            question = block['question']
            # print(question)
            # print(kb_name)
            d = search_docs(question, kb_name, 10, score_threshold=100).data

            if len(d)>0:
                docs.extend(d)

            #最不相关三个，做为负样本对
            if len(docs)>0:
                docs.sort(key=lambda doc:doc.score)
                # 据说后续最多用 top2 做检索，这里我就用top789
                docs = docs[-4:]
            
            neg_list = [i.page_content for i in docs]

            if chunk_tent in neg_list:
                neg_list.remove(chunk_tent)
            else:
                neg_list.pop(0)
            
            new_data = {"query":question, "pos": [chunk_tent], "neg": neg_list}

            with open(output_file, 'a', encoding='utf-8') as outfile:
                json.dump(new_data, outfile, ensure_ascii=False)
                outfile.write('\n')
            if llm_generate:
                INSTRUCTION = "接下来我会给你一段内容，在内容后会跟随一段指令，请严格按照指令执行。\n\n"
                PROMPT = """\n接下来是指令
                        1. 假设你是一位专业的文字编辑。请对这句话进行同义句改写。
                        1. 使用不同的词语和句式。
                        2. 保持句子原意不变。
                        3. 输出格式为python格式，最外层为一个python list，在list里面为一个python dict，其中Content为原句，Answer为改写后的语句。
                        4. 以下为输出示例，严格按照该格式进行输出：
                        [{"Content": "安全壳喷淋系统如何帮助降低安全壳内的压力和温度", "Answer": ["安全壳内部的压力和温度是如何通过喷淋系统得到有效降低的","喷淋系统在降低安全壳内压力和温度方面发挥了什么作用"]}]
                        [{"Content": "为什么“华龙一号”的安全注入系统设置了中压注入子系统", "Answer": [""华龙一号"核电机组为何在安全注入系统中配置了中压注入子系统","中压注入子系统作为"华龙一号"安全注入系统的一部分,其设置目的是什么"]}]
                        [{"Content": "安全壳喷淋系统在什么情况下会不可用", "Answer": ["在何种条件下安全壳喷淋系统会失去功能","什么样的情况会导致安全壳喷淋系统无法正常运行"]}]
                        [{"Content": "设计扩展工况的应对有哪些关键要素", "Answer": ["在应对设计扩展工况时,哪些要素被视为至关重要","处理设计扩展工况的过程中,有哪些核心组成部分需要考虑"]}]
                        [{"Content": "为什么需要设置二次侧非能动余热排出系统", "Answer": ["二次侧非能动余热排出系统的设置目的是什么","为何在设计中加入了二次侧非能动余热排出系统这一功能"]}]

                        """
                messages = [
                    {
                        "role": "system",
                        "content": INSTRUCTION     
                    },
                    {
                        "role": "user",
                        "content": question + PROMPT
                    }
                ]


                response = client.chat.completions.create(
                    model=GENERATE_MODEL_SERVER["model_name"],
                    messages=messages,
                    stream=False,
                    max_tokens=4096,
                    temperature=0.8,
                    presence_penalty=1.2,
                    top_p=0.8,
                )
                response2 = response['choices'][0]['message']['content']
                # print(response2)
                same_sentence_pattern = r'"Answer":\s*([[\s\S]*?])'
                same_sentence_match = re.search(same_sentence_pattern, response2)

                if same_sentence_match:
                    # 提取匹配到的列表字符串
                    same_sentence_list_str = same_sentence_match.group(1)
                    
                    try:# 将字符串转换为Python列表
                        answer_list = json.loads(same_sentence_list_str)

                    except:
                        print('llm write response error: ',same_sentence_list_str)
                        print('llm write response error: ',type(same_sentence_list_str))
                
                else:
                    print('该句子转换失败',response2)
                    continue

                for que in answer_list:
                    try:
                        d = search_docs(que, kb_name, 6, score_threshold=100).data
                        if len(d)>0:
                            docs.extend(d)
                        
                        #最不相关三个，做为负样本对
                        if len(docs)>0:
                            docs.sort(key=lambda doc:doc.score)
                            # # 滨哥说后续最多用 top2 做检索，这里我就用top456
                            docs = docs[-4:]
                        
                        neg_list = [i.page_content for i in docs]
                        
                        if chunk_tent in neg_list:
                            neg_list.remove(chunk_tent)
                        else:
                            neg_list.pop(0)

                        new_data = {"query":que, "pos": [chunk_tent], "neg": neg_list}

                        with open(output_file, 'a', encoding='utf-8') as outfile:
                            json.dump(new_data, outfile, ensure_ascii=False)
                            outfile.write('\n')
                        
                    except:
                        print('llm write response error: ',response)
                        continue


kb_name = "测试"
file_name = "非能动安全先进核电厂ap1000.pdf"
output_file = "./new_generate_dataset.jsonl"
generate_embedding_dataset(kb_name,file_name,output_file,llm_generate=True)


# from server.knowledge_base.kb_doc_api import search_docs
# # print(search_docs('什么是ap1000', kb_name, 3, score_threshold=2).data)
# print(search_docs('请问核电厂的发展经历了多少阶段？', kb_name, 3, score_threshold=2).data)
