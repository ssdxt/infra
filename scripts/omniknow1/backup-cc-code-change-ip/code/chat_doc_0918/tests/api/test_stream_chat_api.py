import requests
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))
from configs import BING_SUBSCRIPTION_KEY
from server.utils import api_address

from pprint import pprint


api_base_url = api_address()


def dump_input(d, title):
    print("\n")
    print("=" * 30 + title + "  input " + "="*30)
    pprint(d)


def dump_output(r, title):
    print("\n")
    print("=" * 30 + title + "  output" + "="*30)
    for line in r.iter_content(None, decode_unicode=True):
        print(line, end="", flush=True)


headers = {
    'accept': 'application/json',
    'Content-Type': 'application/json',
}

data = {
    "query": "请用100字左右的文字介绍自己",
    "history": [
        {
            "role": "user",
            "content": "你好"
        },
        {
            "role": "assistant",
            "content": "你好，我是人工智能大模型"
        }
    ],
    "stream": True,
    "temperature": 0.7,
}


def test_chat_fastchat(api="/chat/fastchat"):
    url = f"{api_base_url}{api}"
    data2 = {
        "stream": True,
        "messages": data["history"] + [{"role": "user", "content": "推荐一部科幻电影"}]
    }
    dump_input(data2, api)
    response = requests.post(url, headers=headers, json=data2, stream=True)
    dump_output(response, api)
    assert response.status_code == 200


def test_chat_chat(api="/chat/chat"):
    url = f"{api_base_url}{api}"
    dump_input(data, api)
    response = requests.post(url, headers=headers, json=data, stream=True)
    dump_output(response, api)
    assert response.status_code == 200

from communicate import chat,get_new_task_id
conversation_task_id = None
def get_chatglm_answer(chatglm_query):
    global conversation_task_id
    if conversation_task_id == None:
        conversation_task_id = get_new_task_id()
    chatglm_answer = chat(chatglm_query,conversation_task_id)
    if len(chatglm_answer)==0:
        conversation_task_id = None
    return chatglm_answer
    
def test_knowledge_chat(query,api="/chat/knowledge_base_chat"):
    url = f"{api_base_url}{api}"
    # print("url",url)
    # query = "传动轴故障表现是什么"
    data = {
        "query": query,
        "knowledge_base_name": "lb_test",
        "history": [
        ],
        "stream": True
    }
    dump_input(data, api)
    response = requests.post(url, headers=headers, json=data, stream=True)
    print("\n")
    print("=" * 30 + api + "  output" + "="*30)
    
    answer = ""
    for line in response.iter_content(None, decode_unicode=True):
        # print("line",repr(line))
        data = json.loads(line)
        if "answer" in data:
            answer +=str(data["answer"])
            print(data["answer"], end="", flush=True)
    print("\n")
    pprint(data)
    import csv
    with open("tests/test_firefly-baichuan2-13b-chat-0127-mix-1150-x50000.csv","a") as csvfile: 
        writer = csv.writer(csvfile)
        context = None
        if data.get("ref_docs") != None:
            context = "\n".join([doc["page_content"] for doc in data["ref_docs"]])
        elif data.get("ref_images") != None:
            context =''
        if len(context)>0:
            chatglm_query = """你是一个汽车维修专家，请结合下面的 '已知信息' 回答问题。直接输出答案即可，不用附带任何上下文。答案简洁、合理，避免重复;字数控制在 '100' 字以内。\n已知信息：'{}'\n问题：'{}'\n 回答：""".format(context,query)
        else:
            chatglm_query = """问题：{} \n回答：""".format(query)
        # chatglm_answer = get_chatglm_answer(chatglm_query)
        writer.writerow([query,context,chatglm_query,answer.strip()])

    # assert "ref_docs" in data and len(data["ref_docs"]) >= 0
    # assert response.status_code == 200


def test_search_engine_chat(api="/chat/search_engine_chat"):
    global data

    data["query"] = "室温超导最新进展是什么样？"

    url = f"{api_base_url}{api}"
    for se in ["bing", "duckduckgo"]:
        data["search_engine_name"] = se
        dump_input(data, api + f" by {se}")
        response = requests.post(url, json=data, stream=True)
        if se == "bing" and not BING_SUBSCRIPTION_KEY:
            data = response.json()
            assert data["code"] == 404
            assert data["msg"] == f"要使用Bing搜索引擎，需要设置 `BING_SUBSCRIPTION_KEY`"

        print("\n")
        print("=" * 30 + api + f" by {se}  output" + "="*30)
        for line in response.iter_content(None, decode_unicode=True):
            data = json.loads(line)
            if "answer" in data:
                print(data["answer"], end="", flush=True)
        assert "docs" in data and len(data["docs"]) > 0
        pprint(data["docs"])
        assert response.status_code == 200
        
if __name__ == "__main__":
    with open("tests/验证数据集_x5000.txt") as f:
        lines  = f.readlines()
        for lineno,query in enumerate(lines):
            print("---lineno---",str(lineno))
            if lineno<0:
                continue
            
            test_knowledge_chat(query.strip())
    pass
    # test_knowledge_chat("WP10H系列发动机的技术规格是怎样的，它包括哪些重要的技术数据")
