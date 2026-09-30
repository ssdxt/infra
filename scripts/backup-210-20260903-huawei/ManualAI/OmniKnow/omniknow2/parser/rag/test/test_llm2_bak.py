from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage,AIMessageChunk
from langchain_core.runnables import RunnableLambda
from typing import TypedDict, Annotated, Literal
from operator import add
import json
from datetime import datetime


uri = "sqlite:///data.db"
db = SQLDatabase.from_uri(uri)

llm = ChatOpenAI(
    base_url="http://127.0.0.1:6420/v1",
    openai_api_key="none",
    # model="qwen3-next-80b-a3b-instruct",
    model = "Qwen3-30B-A3B-Instruct-2507",
    timeout=60.0,
    max_retries=10,
    temperature=0.2
    )

toolkit = SQLDatabaseToolkit(db=db, llm=llm)
tools = toolkit.get_tools()

# 创建工具字典，方便根据名称查找
tools_dict = {tool.name: tool for tool in tools}

today_date = datetime.now().strftime("%Y-%m-%d")

system_prompt = """
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
""".format(
    today_date=today_date,
    dialect=db.dialect,
    top_k=100,
)

# system_prompt = """
# You are an agent designed to interact with a SQL database.
# Today's date is {today_date}.

# Given an input question, create a syntactically correct {dialect} query to run,
# then look at the results of the query and return the answer. Unless the user
# specifies a specific number of examples they wish to obtain, always limit your
# query to at most {top_k} results.

# You can order the results by a relevant column to return the most interesting
# examples in the database. Never query for all the columns from a specific table,
# only ask for the relevant columns given the question.

# You MUST double check your query before executing it. If you get an error while
# executing a query, rewrite the query and try again.

# DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the
# database.

# To start you should ALWAYS look at the tables in the database to see what you
# can query. Do NOT skip this step.

# Then you should query the schema of the most relevant tables.

# IMPORTANT: When calling tools, you MUST provide the arguments as a JSON object (dictionary).
# For example:
# - sql_db_list_tables: use empty string as input, but pass it as {{"tool_input": ""}}
# - sql_db_schema: pass table names as {{"table_names": "table1, table2"}}
# - sql_db_query_checker: pass SQL as {{"query": "SELECT * FROM table"}}
# - sql_db_query: pass SQL as {{"query": "SELECT * FROM table"}}

# Always ensure tool call arguments are properly formatted as JSON objects, not plain strings.
# """.format(
#     today_date=today_date,
#     dialect=db.dialect,
#     top_k=100,
# )


# ========== 定义状态 ==========
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# ========== 定义节点 ==========
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
    """安全调用LLM，修复工具调用格式错误"""
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


def agent_node(state: AgentState):
    """Agent节点：LLM决策调用工具"""
    messages = state["messages"]
    
    # 添加系统提示（如果还没有）
    if not any(isinstance(msg, SystemMessage) for msg in messages):
        messages = [SystemMessage(content=system_prompt)] + messages
    
    # 绑定工具到LLM
    llm_with_tools = llm.bind_tools(tools)
    
    try:
        # 安全调用LLM
        response = _safe_invoke_llm(llm_with_tools, messages)
        return {"messages": [response]}
    except Exception as e:
        print(f"Error in agent_node: {e}")
        error_msg = AIMessage(content=f"Error: {str(e)}")
        return {"messages": [error_msg]}


def tools_node(state: AgentState):
    """通用工具执行节点：处理所有工具调用"""
    # 从最后一条消息中提取工具调用
    last_message = state["messages"][-1]
    tool_messages = []
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_call_id = tool_call.get("id", "")
            args = tool_call.get("args", {})
            
            # 获取对应的工具
            tool = tools_dict.get(tool_name)
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
        return {"messages": []}
    
    return {"messages": tool_messages}


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """根据LLM的工具调用决定下一步"""
    last_message = state["messages"][-1]
    
    # 如果最后一条消息没有工具调用，说明LLM已经给出最终答案
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return "end"
    
    # 有工具调用，路由到工具执行节点
    return "tools"


# ========== 构建图 ==========
def build_graph():
    """构建SQL Agent图"""
    graph = StateGraph(AgentState)
    
    # 添加节点
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    
    # 设置入口
    graph.add_edge(START, "agent")
    
    # 添加条件边：根据工具调用路由
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END,
        }
    )
    
    # 工具执行后回到agent节点，形成ReAct循环
    graph.add_edge("tools", "agent")
    
    return graph.compile()


# 创建agent图
agent = build_graph()

# ========== 测试 ==========
if __name__ == "__main__":
    question = "分析一下从8号到20号电动机的频率的变化趋势"
    # question = "分析一下日期从8号到20号员工的频率的变化趋势"
    
    # 使用stream模式
    # for step in agent.stream(
    for agent, payload in agent.stream(
        # {"messages": [HumanMessage(content=question)]},
        {
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=question),
            ]
        },
        # stream_mode="values",
        stream_mode=["messages", "updates"],
        
        config={"recursion_limit": 50}
    ):
        if agent == "messages":
            msg = payload[0]
            # 获取元数据，检查是否来自 tools 节点
            metadata = payload[1] if len(payload) > 1 else {}
            langgraph_node = metadata.get('langgraph_node', '')
            
            # 只打印来自 planner 节点的消息，不打印来自 tools 节点的消息（避免输出 SQL 查询语句）
            if isinstance(msg, AIMessageChunk) and msg.content and langgraph_node != 'tools':
                print(msg.content, end="", flush=True)
            # if isinstance(msg, AIMessageChunk) and msg.content:
            #     print(msg.content, end="", flush=True)
        # if step.get("messages"):
        #     step["messages"][-1].pretty_print()
