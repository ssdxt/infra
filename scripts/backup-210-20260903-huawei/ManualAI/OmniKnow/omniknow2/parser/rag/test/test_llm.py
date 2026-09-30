from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
from typing import TypedDict, Annotated, Literal
from operator import add
import json

uri = "sqlite:///data.db"
db = SQLDatabase.from_uri(uri)


llm = ChatOpenAI(
    base_url="http://127.0.0.1:6420/v1",
    openai_api_key="none",
    # model="qwen3-next-80b-a3b-instruct",
    model = "Qwen3-30B-A3B-Instruct-2507",
    timeout=60.0,
    max_retries=10,
    temperature=0.5
    )

toolkit = SQLDatabaseToolkit(db=db, llm=llm)
tools = toolkit.get_tools()

# 创建工具字典，方便根据名称查找
tools_dict = {tool.name: tool for tool in tools}

for tool in tools:
    print(f"{tool.name}: {tool.description}\n")
    
"""
sql_db_query：此工具的输入是详细且正确的 SQL 查询语句，输出是数据库结果。如果查询语句不正确，则会返回错误消息。如果返回错误，请重写查询语句，检查查询语句，然后重试。如果您遇到"字段列表中存在未知列 'xxxx'"的问题，请使用 sql_db_schema 查询正确的表字段。
sql_db_schema：此工具的输入是以逗号分隔的表列表，输出是这些表的模式和示例行。请务必先调用 sql_db_list_tables 确认表实际存在！示例输入：table1, table2, table3
sql_db_list_tables：输入为空字符串，输出是数据库中以逗号分隔的表列表。
sql_db_query_checker：在执行查询之前，使用此工具再次检查查询语句是否正确。在执行 sql_db_query 查询之前，请务必使用此工具！
"""

system_prompt = """
You are an agent designed to interact with a SQL database.
Given an input question, create a syntactically correct {dialect} query to run,
then look at the results of the query and return the answer. Unless the user
specifies a specific number of examples they wish to obtain, always limit your
query to at most {top_k} results.

You can order the results by a relevant column to return the most interesting
examples in the database. Never query for all the columns from a specific table,
only ask for the relevant columns given the question.

You MUST double check your query before executing it. If you get an error while
executing a query, rewrite the query and try again.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the
database.

To start you should ALWAYS look at the tables in the database to see what you
can query. Do NOT skip this step.

Then you should query the schema of the most relevant tables.

IMPORTANT: When calling tools, you MUST provide the arguments as a JSON object (dictionary).
For example:
- sql_db_list_tables: use empty string as input, but pass it as {{"tool_input": ""}}
- sql_db_schema: pass table names as {{"table_names": "table1, table2"}}
- sql_db_query_checker: pass SQL as {{"query": "SELECT * FROM table"}}
- sql_db_query: pass SQL as {{"query": "SELECT * FROM table"}}

Always ensure tool call arguments are properly formatted as JSON objects, not plain strings.
""".format(
    dialect=db.dialect,
    top_k=5,
)


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


def list_tables_node(state: AgentState):
    """获取表列表节点"""
    # 从最后一条消息中提取工具调用
    last_message = state["messages"][-1]
    tool_call_id = None
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            if tool_call.get("name") == "sql_db_list_tables":
                tool_call_id = tool_call.get("id")
                break
    
    if not tool_call_id:
        tool_call_id = "list_tables"
    
    tool = tools_dict.get("sql_db_list_tables")
    if not tool:
        return {"messages": [ToolMessage(content="工具 sql_db_list_tables 未找到", tool_call_id=tool_call_id)]}
    
    # 执行工具，参数是空字符串
    result = tool.invoke("")
    
    return {"messages": [ToolMessage(content=str(result), tool_call_id=tool_call_id)]}


def get_schema_node(state: AgentState):
    """获取Schema节点"""
    # 从最后一条消息中提取工具调用的参数
    last_message = state["messages"][-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # 找到 sql_db_schema 的调用
        for tool_call in last_message.tool_calls:
            if tool_call.get("name") == "sql_db_schema":
                # 参数名是 table_names
                table_list = tool_call.get("args", {}).get("table_names", "")
                tool_call_id = tool_call.get("id", "schema")
                tool = tools_dict.get("sql_db_schema")
                if tool:
                    result = tool.invoke(table_list)
                    return {"messages": [ToolMessage(content=str(result), tool_call_id=tool_call_id)]}
    
    return {"messages": [ToolMessage(content="未找到有效的表名参数", tool_call_id="schema")]}


def check_sql_node(state: AgentState):
    """SQL检查节点"""
    # 从最后一条消息中提取工具调用的参数
    last_message = state["messages"][-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # 找到 sql_db_query_checker 的调用
        for tool_call in last_message.tool_calls:
            if tool_call.get("name") == "sql_db_query_checker":
                query = tool_call.get("args", {}).get("query", "")
                tool_call_id = tool_call.get("id", "check_sql")
                tool = tools_dict.get("sql_db_query_checker")
                if tool:
                    result = tool.invoke(query)
                    return {"messages": [ToolMessage(content=str(result), tool_call_id=tool_call_id)]}
    
    return {"messages": [ToolMessage(content="未找到有效的SQL查询参数", tool_call_id="check_sql")]}


def execute_sql_node(state: AgentState):
    """执行SQL节点"""
    # 从最后一条消息中提取工具调用的参数
    last_message = state["messages"][-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # 找到 sql_db_query 的调用
        for tool_call in last_message.tool_calls:
            if tool_call.get("name") == "sql_db_query":
                query = tool_call.get("args", {}).get("query", "")
                tool_call_id = tool_call.get("id", "execute_sql")
                tool = tools_dict.get("sql_db_query")
                if tool:
                    result = tool.invoke(query)
                    return {"messages": [ToolMessage(content=str(result), tool_call_id=tool_call_id)]}
    
    return {"messages": [ToolMessage(content="未找到有效的SQL查询参数", tool_call_id="execute_sql")]}


def should_continue(state: AgentState) -> Literal["list_tables", "get_schema", "check_sql", "execute_sql", "end"]:
    """根据LLM的工具调用决定下一步"""
    last_message = state["messages"][-1]
    
    # 如果最后一条消息没有工具调用，说明LLM已经给出最终答案
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return "end"
    
    # 根据工具名称路由到不同的节点
    tool_call = last_message.tool_calls[0]
    tool_name = tool_call.get("name", "")
    
    if tool_name == "sql_db_list_tables":
        return "list_tables"
    elif tool_name == "sql_db_schema":
        return "get_schema"
    elif tool_name == "sql_db_query_checker":
        return "check_sql"
    elif tool_name == "sql_db_query":
        return "execute_sql"
    else:
        # 未知工具，结束
        return "end"


# ========== 构建图 ==========
def build_graph():
    """构建SQL Agent图"""
    graph = StateGraph(AgentState)
    
    # 添加节点
    graph.add_node("agent", agent_node)
    graph.add_node("list_tables", list_tables_node)
    graph.add_node("get_schema", get_schema_node)
    graph.add_node("check_sql", check_sql_node)
    graph.add_node("execute_sql", execute_sql_node)
    
    # 设置入口
    graph.add_edge(START, "agent")
    
    # 添加条件边：根据工具调用路由
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "list_tables": "list_tables",
            "get_schema": "get_schema",
            "check_sql": "check_sql",
            "execute_sql": "execute_sql",
            "end": END,
        }
    )
    
    # 工具执行后回到agent节点，形成ReAct循环
    graph.add_edge("list_tables", "agent")
    graph.add_edge("get_schema", "agent")
    graph.add_edge("check_sql", "agent")
    graph.add_edge("execute_sql", "agent")
    
    return graph.compile()


# 创建agent图
agent = build_graph()

# ========== 测试 ==========
if __name__ == "__main__":
    question = "分析一下从4号到20号都有哪些人在"
    
    # 使用stream模式
    for step in agent.stream(
        {"messages": [HumanMessage(content=question)]},
        stream_mode="values",
    ):
        if step.get("messages"):
            step["messages"][-1].pretty_print()
