from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage,AIMessageChunk
from langchain_core.runnables import RunnableLambda
from typing import TypedDict, Annotated, Literal
from operator import add
import asyncio
import json
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import uvicorn
import re

host = "0.0.0.0"
port = 8561
RECURSION_LIMIT = 50
LLM_BASE_URL = "http://127.0.0.1:10006/v1"
# LLM_MODEL = "Qwen3-30B-A3B-Instruct-2507"
LLM_MODEL = "glm-4"
LLM_API_KEY = "none"
# uri = "sqlite:///data.db"
# uri = "sqlite:////mnt/ddata2/cc007/omniknow2/parser/rag/data.db"
# uri = "sqlite://///deploy/code/chat_doc_85/knowledge_base/excel.db"
uri = "sqlite:////deploy/code/chat_doc_85/knowledge_base/ttttt/excel_ttttt.db"

# "/deploy/code/chat_doc_85/knowledge_base/ttttt/excel_ttttt.db"


app = FastAPI(
    title="SQL Query Agent API",
    description="将自然语言问题转换为 SQL 查询并执行的 API",
    version="1.0.0"
)

class IntentResult(TypedDict):
    need_db: bool
    
# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


llm = ChatOpenAI(
        base_url=LLM_BASE_URL,
        openai_api_key=LLM_API_KEY,
        # model="qwen3-next-80b-a3b-instruct",
        model = LLM_MODEL,
        timeout=60.0,
        max_retries=10,
        temperature=0.2,
        extra_body={"enable_thinking":False}
        # model_kwargs={
        #     "chat_template_kwargs": {
        #         "enable_thinking": False
        #     }
        # }
    )



today_date = datetime.now().strftime("%Y-%m-%d")


system_prompt_template = """
你是一个**专门与 SQL 数据库交互的专家。**
今天的日期为 {today_date}.

你的任务是：
根据用户的问题，**生成语法正确的 {dialect} SQL 查询语句**，执行查询，并基于查询结果返回答案。

# 查询规则
- 除非用户明确指定返回的示例数量，否则查询结果最多返回 {top_k} 条。
- 可以根据相关列对结果进行排序，以返回最有代表性、最有意义的数据。
- 禁止使用 SELECT *，只能查询与问题直接相关的列。
- 严禁执行任何 DML 或 DDL 语句，包括但不限于：INSERT、UPDATE、DELETE、DROP。

# 查询流程（必须严格遵循）
1. 首先查看数据库中已有的表，以了解可查询的内容（不得跳过此步骤）。
2. 查询最相关表的 schema（表结构），明确字段信息。
3. 在此基础上构建 SQL 查询语句。
4. 在执行前仔细检查 SQL 语句的正确性。
5. 如果执行过程中出现错误，必须重写查询语句并重新尝试。

# *工具调用规范（重要）**
在调用任何工具时，参数必须以 JSON 对象（字典）形式传递，而不是普通字符串。
例如：
- sql_db_list_tables: 使用空字符串作为输入，但以 {{"tool_input": ""}} 格式传递
- sql_db_schema: 以 {{"table_names": "table1, table2"}} 格式传递表名
- sql_db_query_checker: 以 {{"query": "SELECT * FROM table"}} 格式传递 SQL
- sql_db_query: 以 {{"query": "SELECT * FROM table"}} 格式传递 SQL

始终确保工具调用参数正确格式化为 JSON 对象，而不是普通字符串。
"""


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    last_query_tables: list[str]  # 存储最后查询的表名列表
    

def _fix_tool_calls_args(tool_calls):
    """修复工具调用中的 args 格式，确保是字典"""
    if not tool_calls:
        return tool_calls
    
    fixed_calls = []
    for tool_call in tool_calls:
        if isinstance(tool_call, dict):
            args = tool_call.get("args")
            tool_name = tool_call.get("name", "")
            
            # 如果 args 不是字典，修复它
            if not isinstance(args, dict):
                if isinstance(args, str):
                    # 字符串参数，根据工具类型创建正确的字典
                    if tool_name == "sql_db_list_tables":
                        fixed_args = {"tool_input": ""}
                    elif tool_name == "sql_db_schema":
                        fixed_args = {"table_names": args if args else ""}
                    elif tool_name in ["sql_db_query", "sql_db_query_checker"]:
                        fixed_args = {"query": args if args else ""}
                    else:
                        fixed_args = {}
                else:
                    # 其他类型，创建默认格式
                    if tool_name == "sql_db_list_tables":
                        fixed_args = {"tool_input": ""}
                    elif tool_name == "sql_db_schema":
                        fixed_args = {"table_names": ""}
                    elif tool_name in ["sql_db_query", "sql_db_query_checker"]:
                        fixed_args = {"query": ""}
                    else:
                        fixed_args = {}
                
                tool_call["args"] = fixed_args
            fixed_calls.append(tool_call)
        else:
            fixed_calls.append(tool_call)
    
    return fixed_calls


def _safe_invoke_llm(llm_with_tools, messages):
    """修复工具调用格式错误"""
    try:
        # 先尝试正常调用
        response = llm_with_tools.invoke(messages)
        
        # 修复工具调用格式（如果存在）
        if hasattr(response, "tool_calls") and response.tool_calls:
            fixed_tool_calls = _fix_tool_calls_args(response.tool_calls)
            response.tool_calls = fixed_tool_calls
        
        return response
    except Exception as e:
        error_str = str(e)
        # 检查是否是工具调用格式错误
        if "tool_calls" in error_str and ("args" in error_str or "dict_type" in error_str):
            # 使用 generate 方法获取原始响应并修复
            try:
                result = llm_with_tools.generate([messages])
                generation = result.generations[0][0]
                
                if hasattr(generation, "message"):
                    msg = generation.message
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        fixed_tool_calls = _fix_tool_calls_args(msg.tool_calls)
                        # 创建新的 AIMessage，使用修复后的 tool_calls
                        response = AIMessage(
                            content=msg.content or "",
                            tool_calls=fixed_tool_calls,
                            response_metadata=getattr(msg, "response_metadata", {})
                        )
                        return response
                    else:
                        return msg
                else:
                    return generation
            except Exception as gen_error:
                print(f"Error in generate fallback: {gen_error}")
                # 返回错误消息
                return AIMessage(
                    content="I encountered a format error with tool calls. Please try rephrasing your question."
                )
        else:
            # 其他错误，重新抛出
            raise


def create_planner_node(tools_list, system_prompt_text):
    """创建planner节点：LLM决策调用工具"""
    def planner_node(state: AgentState):
        messages = state["messages"]
        # query_tables = state.get("last_query_tables", [])  # 获取当前表名列表
        
        
        # 添加系统提示（如果还没有）
        if not any(isinstance(msg, SystemMessage) for msg in messages):
            messages = [SystemMessage(content=system_prompt_text)] + messages
        
        # 绑定工具到LLM
        llm_with_tools = llm.bind_tools(tools_list)
        
        try:
            # 安全调用LLM
            response = _safe_invoke_llm(llm_with_tools, messages)
            # return {"messages": [response], "last_query_tables": query_tables}
            return {"messages": [response]}
        except Exception as e:
            print(f"Error in agent_node: {e}")
            error_msg = AIMessage(content=f"Error: {str(e)}")
            return {"messages": [error_msg]}
    return planner_node


def create_tools_node(tools_dict_ref):
    """创建通用工具执行节点：处理所有工具调用"""
    def tools_node(state: AgentState):
        # 从最后一条消息中提取工具调用
        last_message = state["messages"][-1]
        tool_messages = []
        query_tables = state.get("last_query_tables", [])  # 获取当前表名列表
        
        
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                tool_name = tool_call.get("name", "")
                tool_call_id = tool_call.get("id", "")
                args = tool_call.get("args", {})
                
                # 获取对应的工具
                tool = tools_dict_ref.get(tool_name)
                if not tool:
                    tool_messages.append(ToolMessage(
                        content=f"工具 {tool_name} 未找到",
                        tool_call_id=tool_call_id
                    ))
                    continue
                
                # 根据工具类型提取参数并执行
                try:
                    if tool_name == "sql_db_list_tables":
                        # 参数是空字符串
                        result = tool.invoke("")
                    elif tool_name == "sql_db_schema":
                        # 参数是 table_names（字符串）
                        table_list = args.get("table_names", "") if isinstance(args, dict) else str(args)
                        result = tool.invoke(table_list)
                        
                        query_tables = table_list.split(",") if "," in table_list else [table_list]
                    elif tool_name == "sql_db_query_checker":
                        # 参数是 query（字符串）
                        query = args.get("query", "") if isinstance(args, dict) else str(args)
                        result = tool.invoke(query)
                    elif tool_name == "sql_db_query":
                        # 参数是 query（字符串）
                        query = args.get("query", "") if isinstance(args, dict) else str(args)
                        result = tool.invoke(query)
                    else:
                        # 其他工具，直接传递参数
                        result = tool.invoke(args if isinstance(args, dict) else {})
                    
                    tool_messages.append(ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call_id
                    ))
                except Exception as e:
                    tool_messages.append(ToolMessage(
                        content=f"执行工具 {tool_name} 时出错: {str(e)}",
                        tool_call_id=tool_call_id
                    ))
        
        if not tool_messages:
            # return {"messages": []}
            return {"messages": []}
        
        
        # return {"messages": tool_messages}
        return {"messages": tool_messages, "last_query_tables": query_tables}
    return tools_node


def continue_to_running_tools(state: AgentState) -> Literal["tools", "end"]:
    """根据LLM的工具调用决定下一步"""
    last_message = state["messages"][-1]
    
    # 如果最后一条消息没有工具调用，说明LLM已经给出最终答案
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return "end"
    
    # 有工具调用，路由到工具执行节点
    return "tools"


# ========== 构建图 ==========
def build_graph(tools_list, tools_dict_ref, system_prompt_text):
    graph = StateGraph(AgentState)
    
    planner = create_planner_node(tools_list, system_prompt_text)
    tools = create_tools_node(tools_dict_ref)
    
    graph.add_node("planner", planner)
    graph.add_node("tools", tools)
    graph.add_edge(START, "planner")
    graph.add_conditional_edges(
        "planner",
        continue_to_running_tools,
        {
            "tools": "tools",
            "end": END,
        }
    )
    
    # 工具执行后回到planner节点，形成ReAct循环
    graph.add_edge("tools", "planner")
    
    return graph.compile()


async def run_agent(question: str="", db_path: str = None):    
    # question = "分析一下从8号到20号电动机表的频率的变化趋势"
    question = "分析一下日期从8号到20号员工的频率的变化趋势"
    db_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/data.db"
    # db_path = "sqlite:////deploy/code/chat_doc_85/knowledge_base/ttttt/excel_ttttt.db"
    
    # 根据db_path创建数据库连接
    # 确保路径格式正确
    if not db_path.startswith("sqlite://"):
        # 如果路径以 / 开头，使用三个斜杠；否则使用四个斜杠
        if db_path.startswith("/"):
            uri_path = f"sqlite:///{db_path}"  # sqlite:///path/to/db.db
        else:
            uri_path = f"sqlite://{db_path}"  # sqlite:///relative/path/db.db
    else:
        uri_path = db_path

    
    # 创建数据库连接和工具
    current_db = SQLDatabase.from_uri(uri_path)
    current_toolkit = SQLDatabaseToolkit(db=current_db, llm=llm)
    current_tools = current_toolkit.get_tools()
    current_tools_dict = {tool.name: tool for tool in current_tools}
    print(f"Tools available: {[tool.name for tool in current_tools]}")
    # 创建系统提示
    current_system_prompt = system_prompt_template.format(
        today_date=today_date,
        dialect=current_db.dialect,
        top_k=100,
    )
    
    # 构建图
    current_graph = build_graph(current_tools, current_tools_dict, current_system_prompt)
        
    initial_state: AgentState = {
        "messages": [
            SystemMessage(content=current_system_prompt),
            HumanMessage(content=question)
        ],
        "last_query_tables": []
    }
    
    final_tables = []  # 用于存储最终的表名
    
    try:
        # data = json.dumps({"type": "message", "content": "已收到您的问题，正在查询相关数据…"}, ensure_ascii=False)
        # yield f"data: {data}\n\n"
        
        async for agent, payload in current_graph.astream(
            initial_state,
            # stream_mode="values",
            stream_mode=["messages", "updates"],
            config={"recursion_limit": RECURSION_LIMIT}
        ):
            # print('agent',agent)
            # print('payload',payload)
            if agent == "messages":
                msg = payload[0]
                
                # 获取元数据，检查是否来自 tools 节点
                metadata = payload[1] if len(payload) > 1 else {}
                langgraph_node = metadata.get('langgraph_node', '')
                
                if isinstance(msg, AIMessageChunk) and msg.content and langgraph_node != 'tools':                
                    print(msg.content, end="", flush=True)
                    # print(msg)
                    
                    # data = json.dumps({"type": "message", "content": msg.content}, ensure_ascii=False)
                    # yield f"data: {data}\n\n"

            elif agent == "updates":
                if isinstance(payload, dict):
                    tools_payload = payload.get("tools",{})
                    if tools_payload and "last_query_tables" in tools_payload:
                        final_tables = tools_payload.get("last_query_tables", [])
                        # print(final_tables)
    
                elif isinstance(payload, list):
                    for item in payload:
                        if isinstance(item, dict) and "last_query_tables" in item:
                            final_tables = item.get("last_query_tables", [])

        # yield f"data: {json.dumps({'type': 'finished', 'tables': final_tables}, ensure_ascii=False)}\n\n"
        print(f"data: {json.dumps({'type': 'finished', 'tables': final_tables}, ensure_ascii=False)}\n\n")
        
    except Exception as e:
        error_data = json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False)
        # yield f"data: {error_data}\n\n"
        print(f"data: {error_data}\n\n")


class QueryRequest(BaseModel):
    """查询请求模型"""
    question: str
    db_path: str  # 数据库路径

class IntentRequest(BaseModel):
    query: str
    
@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "message": "SQL Query Agent API is running"}


@app.post("/query_db")
async def query_db(request: QueryRequest):
    """
    流式查询接口
    
    使用 Server-Sent Events (SSE) 格式返回结果
    
    参数:
    - question: 自然语言问题
    - db_path: 数据库文件路径（例如：/mnt/ddata2/cc007/data.db）
    """
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    
    if not request.db_path or not request.db_path.strip():
        raise HTTPException(status_code=400, detail="数据库路径不能为空")
    
    try:
        # 返回流式响应
        return StreamingResponse(
            run_agent(request.question, request.db_path),
            media_type="text/event-stream",
            # headers={
            #     "Cache-Control": "no-cache",
            #     "Connection": "keep-alive",
            #     "X-Accel-Buffering": "no"
            # }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")



if __name__ == "__main__":
    asyncio.run(run_agent())
   
    # uvicorn.run(app, host=host, port=port)    