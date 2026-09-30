# from langchain_openai import ChatOpenAI
# from langchain_core.messages import HumanMessage, SystemMessage
# from typing import TypedDict

# class IntentResult(TypedDict):
#     need_db: bool

# llm = ChatOpenAI(
#     base_url="http://127.0.0.1:10005/v1",
#     openai_api_key="none",
#     model="Qwen3-30B-A3B-Instruct-2507",
#     max_retries=10,
#     temperature=0.0,  # 意图识别
# )

# structured_llm = llm.with_structured_output(IntentResult)

# INTENT_SYSTEM_PROMPT = """
# 你是一个【意图识别器】，只负责判断用户问题是否需要通过【数据库查询】才能回答。

# 【需要数据库查询】的典型情况：
# - 查询表数据
# - 统计、聚合、筛选、排序
# - 时间范围、数量、频率、趋势、排行
# - 明显依赖结构化数据（数据库 / 表格）

# 【不需要数据库查询】的情况：
# - 常识性问题
# - 概念解释
# - 不依赖具体数据

# 请【只返回 JSON】，不要输出任何解释性文字。
# JSON 格式必须严格如下（只能 true 或 false）：

# {
#   "need_db": boolean
# }
# """


# async def intent_recognize(query: str) -> IntentResult:
#     """
#     异步判断用户问题是否需要数据库查询
#     适合 LangGraph / FastAPI / 并发场景
#     """
#     messages = [
#         SystemMessage(content=INTENT_SYSTEM_PROMPT),
#         HumanMessage(content=query),
#     ]

#     try:
#         result = await structured_llm.ainvoke(messages)

#         if not isinstance(result, dict) or "need_db" not in result:
#             raise ValueError("Invalid structured output")

#         return result

#     except Exception as e:
#         return {"need_db": False,"error": f"LLM调用失败或输出解析失败: {str(e)}"}


# if __name__ == "__main__":
#     import asyncio

#     async def main():
#         res = await intent_recognize(
#             "分析一下从8号到20号电动机表的频率的变化趋势"
#         )
#         print(res)

#     asyncio.run(main())

# import httpx
# import asyncio
# from typing import Dict, Any
# INTENT_URL = "http://127.0.0.1:8561/intent_db"

# async def call_intent_api(query: str) -> Dict[str, Any]:
#     async with httpx.AsyncClient(timeout=120.0) as client:
#         resp = await client.post(
#             INTENT_URL,
#             json={
#                 "query": query
#             }
#         )
#         resp.raise_for_status()
#         return resp.json()


# async def main():
#     res = await call_intent_api(
#         "分析一下从8号到20号电动机表的频率的变化趋势"
#     )
#     print(type(res))
#     print("result:", res)


# if __name__ == "__main__":
#     asyncio.run(main())

import json
from openai import OpenAI

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


def intent_is_db(query):

    client = OpenAI(
        base_url="http://127.0.0.1:10005/v1",
        api_key="none"
        )

    use_stream=False
    system_prompt = """
你是一个【意图识别器】，只负责判断用户问题是否需要通过【数据库查询】才能回答。

【需要数据库查询】的典型情况：
- 查询表数据
- 统计、聚合、筛选、排序
- 时间范围、数量、频率、趋势、排行
- 明显依赖结构化数据（数据库 / 表格）

【不需要数据库查询】的情况：
- 常识性问题
- 概念解释
- 不依赖具体数据

请【只返回 JSON】，不要输出任何解释性文字。
JSON 格式必须严格如下（只能 true 或 false）：

{
  "need_db": boolean
}
"""
    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": "用户问题为："+query
        }
    ]

    response = client.chat.completions.create(
        model="Qwen3-30B-A3B-Instruct-2507",
        messages=messages,
        stream=use_stream,
        max_tokens=4096,
        temperature=0,
        presence_penalty=1.2,
        top_p=0.8,
    )
    content = response.choices[0].message.content
    content = filter_json(content)
    
    json_content = json.loads(content)
    
    print(json_content)
    print(type(json_content))
    

intent_is_db("分析一下从8号到20号电动机表的频率的变化趋势")