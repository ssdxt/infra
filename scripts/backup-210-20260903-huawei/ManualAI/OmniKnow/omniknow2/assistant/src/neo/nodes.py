import json
import logging
from functools import partial
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.types import Command

from src.agents import create_agent
from src.config.agents import AGENT_LLM_MAP
from src.config.configuration import Configuration
from src.llms.llm import get_llm_by_type, get_llm_token_limit_by_type
from src.prompts.template import apply_prompt_template
from src.subagents.tabular.sql_database import get_sql_toolkit
from src.tools import (
    get_kb_files_tool,
    get_retriever_tool,
    python_repl_tool,
    read_full_tabular_file,
)
from src.utils.context_manager import ContextManager, validate_message_content
from src.utils.json_utils import sanitize_tool_response

from .state import NeoState
from .types import StepType
from .utils import (
    FACT_CHECK_SUMMARY_MAX_CLAIMS,
    _build_scheduler_finish_handoff,
    _build_scheduler_prompt_state,
    _build_grounding_report,
    _build_resource_catalog,
    _claim_to_prompt_payload,
    _completed_steps_for_type,
    _fallback_fact_check_review,
    _format_fact_check_observation_digest,
    _format_fact_check_report_for_prompt,
    _format_resource_catalog_for_prompt,
    _format_resources_for_prompt,
    _get_citation_factor,
    _invoke_fact_check_summary_with_retries,
    _invoke_scheduler_with_retries,
    _preserve_core_fields,
    _resolve_claim_citations,
    _resources_for_agent,
    _resources_for_tabular_execution,
    _run_preprocess,
    _set_runtime_agent_name,
    _should_run_fact_check,
    is_user_message,
)

logger = logging.getLogger(__name__)

SCHEDULER_MAX_SUBAGENT_CALLS = 3
NEO_PROMPT_LOCALE = "zh-CN"


def _get_message_text(message: Any) -> str:
    """Best-effort extraction of message text from dict or LangChain message."""
    if isinstance(message, dict):
        content = message.get("content", "")
    else:
        content = getattr(message, "content", "")

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
        return "\n".join(part for part in parts if part)
    return str(content or "")


def _is_summary_message(message: Any) -> bool:
    """Return True when the message is a persisted final summary answer."""
    if isinstance(message, dict):
        role = (message.get("role") or "").lower()
        name = (message.get("name") or "").lower()
    else:
        role = (getattr(message, "type", "") or getattr(message, "role", "") or "").lower()
        name = (getattr(message, "name", "") or "").lower()

    return role in {"ai", "assistant"} and name == "summarize"


def _filter_conversation_history_for_summary(
    messages: list[Any],
    final_answer: str = "",
) -> list[Any]:
    """Keep only end-user questions and persisted summary answers."""
    filtered_messages: list[Any] = []

    for message in messages or []:
        content = _get_message_text(message).strip()
        if not content:
            continue
        if is_user_message(message):
            filtered_messages.append(HumanMessage(content=content))
            continue
        if _is_summary_message(message):
            filtered_messages.append(AIMessage(content=content, name="summarize"))

    final_answer = (final_answer or "").strip()
    if final_answer:
        filtered_messages.append(AIMessage(content=final_answer, name="summarize"))

    return filtered_messages


def _is_chinese_locale(locale: str) -> bool:
    normalized = (locale or "").replace("_", "-").lower()
    return normalized.startswith("zh")


def _inject_runtime_instruction(messages: list[Any], instruction: str) -> None:
    if not instruction:
        return

    insert_at = 0
    if messages:
        first = messages[0]
        if (
            isinstance(first, dict)
            and first.get("role") == "system"
        ) or isinstance(first, SystemMessage):
            insert_at = 1

    messages.insert(insert_at, SystemMessage(content=instruction))


def _build_scheduler_runtime_instruction(locale: str) -> str:
    return (
        "运行时策略更新：`rag` 可以调用 `get_kb_files` 回答知识库文件清单、文件数量、"
        "文件是否存在、精确路径定位等问题。"
        "如果当前目标只是查看知识库有哪些文件、统计文件数量、确认某文件是否存在或返回精确路径，"
        "把 `next_step.step_type` 设为 `rag`。"
        "只有当当前目标是操作知识库表格文件内容，包括读取、筛选、聚合、统计、对比、按 sheet 分析、导出等，"
        "即使还不知道准确路径，也要直接把 `next_step.step_type` 设为 `tabular`。"
        "`tabular` 会先调用 `get_kb_files` 获取准确路径，再使用 `read_full_tabular_file` 把整张表全文读入消息历史，"
        "随后由它自己的 LLM 基于全文推理答案，而不是再用 `pandas` 做筛选、聚合、统计或其他分析。"
        "`rag` 还负责文档语义检索、答案依据提取，以及 PDF/Word 文档及其中表格的检索。"
    )




def _build_subagent_runtime_instruction(agent_name: str, locale: str) -> str:
    if agent_name == "tabular":
        return (
            "运行时策略：遇到知识库 `.csv`、`.xlsx`、`.xls` 文件内容处理任务时，"
            "先调用 `get_kb_files` 获取精确路径，"
            "再调用 `read_full_tabular_file` 把该表格全文读入消息历史，让你基于全文自行推理答案。"
            "对知识库表格文件不要再编写自定义 `pandas` 分析代码，不要做筛选、聚合、统计、对比或摘要式预处理。"
            "如果当前任务只是查看知识库文件清单、确认某文件是否存在、或返回精确路径，"
            "这类动作通常应由 `rag` 使用 `get_kb_files` 完成；只有调度已明确派给你时才直接回答。"
            "数据库资源继续使用 SQL 工具，知识库文件不要误用 SQL 工具。"
        )

    if agent_name == "rag":
        return (
            "运行时策略：你可以调用 `get_kb_files` 处理知识库文件清单、文件数量、"
            "文件存在性判断和精确路径定位。"
            "如果当前步骤只是问知识库有哪些文件、某文件是否存在、或文件路径是什么，直接使用 `get_kb_files` 回答。"
            "如果当前步骤需要读取或分析知识库 `.csv`、`.xlsx`、`.xls` 表格内容，"
            "要明确指出该任务应由 `tabular` 执行。"
            "此外，你仍专注文档语义检索、答案依据提取，以及 PDF/Word 等文档内容检索。"
        )


    return ""


@tool
def handoff_to_scheduler(
    research_topic: str,
    locale: str,
):
    """Handoff the task to the scheduler."""
    return


def _extract_visual3d_payload(content: Any) -> dict[str, Any] | None:
    if isinstance(content, dict):
        payload = content
    elif isinstance(content, str):
        try:
            payload = json.loads(content)
        except Exception:
            return None
    else:
        return None

    if (
        isinstance(payload, dict)
        and payload.get("action") == "postMessage"
        and isinstance(payload.get("message"), dict)
    ):
        return payload
    return None


def _extract_visual3d_observation(messages: list[Any]) -> str | None:
    for message in reversed(messages or []):
        payload = _extract_visual3d_payload(getattr(message, "content", None))
        if payload is not None:
            return json.dumps(payload, ensure_ascii=False)
    return None


def _direct_visual3d_answer(state: NeoState) -> str | None:
    completed_steps = state.get("completed_steps", [])
    if not completed_steps:
        return None

    if any(getattr(step, "step_type", None) != StepType.VISUAL3D for step in completed_steps):
        return None

    for observation in reversed(state.get("observations", [])):
        payload = _extract_visual3d_payload(observation)
        if payload is not None:
            return json.dumps(payload, ensure_ascii=False)

    return None


async def coordinator_node(
    state: NeoState, config: RunnableConfig
) -> Command[Literal["scheduler", "__end__"]]:
    logger.info("neo coordinator talking")
    locale = state.get("locale", "zh-CN")
    messages = apply_prompt_template("neo/coordinator", state, locale=NEO_PROMPT_LOCALE)

    if state.get("image_url"):
        # messages.append(HumanMessage(content=f"用户已上传图片，需 `scheduler` 解析"))
        messages.append(HumanMessage(content=f"用户已上传图片"))
        preprocess_summary = await _run_preprocess(state, config)
        messages.append(HumanMessage(content=preprocess_summary))
        goto = "scheduler"
    else:
        goto = "__end__"

    messages.append(SystemMessage(content="注意: 作为 corrdinator 你只负责调用 `handoff_to_scheduler` 转交任务，或者直接回答用户的闲聊问题。"))
    response = (
        get_llm_by_type(AGENT_LLM_MAP["coordinator"])
        .bind_tools([handoff_to_scheduler])
        .invoke(messages)
    )

    research_topic = state.get("research_topic", "")
    final_messages = list(state.get("messages", []))
    if response.tool_calls:
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            if tool_name == "handoff_to_scheduler":
                goto = "scheduler"
                research_topic = tool_args.get("research_topic") or research_topic
                locale = tool_args.get("locale") or locale
                break
    elif not response.content:
        # If the coordinator returns neither tool calls nor text, fall back to
        # the scheduler to avoid ending the turn with an empty response.
        goto = "scheduler"

    if response.content and goto == "__end__":
        final_messages.append(AIMessage(content=response.content, name="coordinator"))
    else:
        goto = "scheduler"

    update = {
        "messages": final_messages,
        "locale": locale,
        "research_topic": research_topic,
        "scheduler_thought": "",
        "task_title": "",
        "observations": [],
        "completed_steps": [],
        "current_step": None,
        "final_answer": "",
        "preprocess_done": False,
        "preprocess_summary": "",
        "resources": Configuration.from_runnable_config(config).resources,
        "image_url": state.get("image_url", ""),
        "user_id": state.get("user_id", "anonymous"),
        "enable_longterm_memory": state.get("enable_longterm_memory", False),
        "fact_check_review": {},
        "fact_check_report": {},
        "grounding_score": 0.0,
    }
    return Command(update=update, goto=goto)


async def scheduler_node(
    state: NeoState, config: RunnableConfig
) -> Command[Literal["subagent", "fact_check", "summarize", "__end__", "scheduler"]]:
    logger.info("neo scheduler planning dynamically")
    locale = state.get("locale", "zh-CN")
    # preprocess_summary = await _run_preprocess(state, config)
    # scheduler_state = _build_scheduler_prompt_state(state, preprocess_summary)

    # TODO: 已将 preprocess 转移到 coordinator 下，后续考虑长效记忆的位置
    preprocess_summary = ""
    scheduler_state = _build_scheduler_prompt_state(state, preprocess_summary)
    # The scheduler replans from structured step outputs, not raw tool payloads.
    # Keep large tabular tool messages out of the scheduler prompt to avoid
    # unnecessary context blow-up after full-table reads.
    scheduler_state["messages"] = []
    invoke_messages = apply_prompt_template(
        "neo/scheduler",
        scheduler_state,
        Configuration.from_runnable_config(config),
        NEO_PROMPT_LOCALE,
    )
    # system prompt插到第一位
    _inject_runtime_instruction(
        invoke_messages,
        _build_scheduler_runtime_instruction(locale),
    )
    rag_resources = _resources_for_agent(state.get("resources", []), "rag")
    tabular_resources = _resources_for_tabular_execution(state.get("resources", []))
    visul3d_resources = _resources_for_agent(state.get("resources", []), "visual3d")
    circuit_resources = _resources_for_agent(state.get("resources", []), "circuit")
    completed_steps = list(state.get("completed_steps", []))
    subagent_call_count = len(completed_steps)
    remaining_subagent_calls = max(
        0,
        SCHEDULER_MAX_SUBAGENT_CALLS - subagent_call_count,
    )

    if rag_resources:
        invoke_messages.append(
            HumanMessage(content=f"共有 {len(rag_resources)} 个知识库连接方式, 分别是: {rag_resources}")
        )
    if tabular_resources:
        if _is_chinese_locale(locale):
            invoke_messages.append(
                HumanMessage(
                    content=(
                        f"`tabular` 当前可处理 {len(tabular_resources)} 个资源"
                        f"（含数据库连接与可定位的知识库表格文件来源）: {tabular_resources}"
                    )
                )
            )
        else:
            invoke_messages.append(
                HumanMessage(
                    content=(
                        f"`tabular` can currently operate on {len(tabular_resources)} resources "
                        f"(database connectors and knowledge-base spreadsheet sources): {tabular_resources}"
                    )
                )
            )
    if visul3d_resources:
        invoke_messages.append(
            HumanMessage(content=f"共有 {len(visul3d_resources)} 个3D资源库，可以展示对应的模型和动画, 分别是: {visul3d_resources}")
        )

    if circuit_resources:
        invoke_messages.append(
            HumanMessage(content=f"共有 {len(circuit_resources)} 个电路图资源库, 分别是: {circuit_resources}")
        )

    if _is_chinese_locale(locale):
        invoke_messages.append(
            HumanMessage(
                content=(
                    f"运行约束：本轮最多只能调用子智能体 {SCHEDULER_MAX_SUBAGENT_CALLS} 次。"
                    f"当前已调用 {subagent_call_count} 次，剩余 {remaining_subagent_calls} 次。"
                    "如果剩余次数为 0，必须停止继续派发新的子智能体并直接收尾。"
                )
            )
        )
    else:
        invoke_messages.append(
            HumanMessage(
                content=(
                    "Runtime constraint: this turn may call subagents at most "
                    f"{SCHEDULER_MAX_SUBAGENT_CALLS} times. "
                    f"{subagent_call_count} calls have already been used and "
                    f"{remaining_subagent_calls} remain. "
                    "If the remaining budget is 0, do not dispatch another subagent and wrap up instead."
                )
            )
        )

    decision = _invoke_scheduler_with_retries(
        invoke_messages,
        locale,
        state,
        get_llm_by_type(AGENT_LLM_MAP["scheduler"]),
    )

    if decision.locale:
        locale = decision.locale

    if decision.next_step:
        if subagent_call_count >= SCHEDULER_MAX_SUBAGENT_CALLS:
            next_node = "fact_check" if _should_run_fact_check(state) else "summarize"
            observations = list(state.get("observations", []))
            if _is_chinese_locale(locale):
                observations.append(
                    f"[SCHEDULER_HANDOFF] 已达到子智能体调用上限 {SCHEDULER_MAX_SUBAGENT_CALLS} 次。"
                    "请基于当前已完成步骤和观察结果直接收尾，不要继续派发新的子智能体。"
                )
            else:
                observations.append(
                    f"[SCHEDULER_HANDOFF] The subagent-call limit of {SCHEDULER_MAX_SUBAGENT_CALLS} "
                    "has been reached. Wrap up from the completed steps and observations instead of "
                    "dispatching another subagent."
                )

            return Command(
                update={
                    **_preserve_core_fields(state),
                    "locale": locale,
                    "scheduler_thought": decision.thought,
                    "task_title": decision.title
                    or state.get("task_title", "")
                    or state.get("research_topic", ""),
                    "preprocess_done": True,
                    "preprocess_summary": preprocess_summary,
                    "current_step": None,
                    "observations": observations,
                },
                goto=next_node,
            )

        return Command(
            update={
                **_preserve_core_fields(state),
                "locale": locale,
                "scheduler_thought": decision.thought,
                "task_title": decision.title or state.get("task_title", "") or state.get("research_topic", ""),
                "preprocess_done": True,
                "preprocess_summary": preprocess_summary,
                "current_step": decision.next_step,
            },
            goto="subagent",
        )

    next_node = "fact_check" if _should_run_fact_check(state) else "summarize"
    observations = list(state.get("observations", []))
    direct_answer = (decision.direct_answer or "").strip()
    if direct_answer:
        observations.append(f"[SCHEDULER_DIRECT_ANSWER] {direct_answer}")

    handoff = "" if direct_answer else _build_scheduler_finish_handoff(state)
    if handoff:
        observations.append(f"[SCHEDULER_HANDOFF] {handoff}")

    return Command(
        update={
            **_preserve_core_fields(state),
            "locale": locale,
            "scheduler_thought": decision.thought,
            "task_title": decision.title or state.get("research_topic", ""),
            "preprocess_done": True,
            "preprocess_summary": preprocess_summary,
            "current_step": None,
            "observations": observations,
        },
        goto=next_node,
    )


async def _execute_step(
    state: NeoState,
    config: RunnableConfig,
    agent_name: str,
    prompt_name: str,
    default_tools: list,
) -> Command[Literal["scheduler"]]:
    current_step = state.get("current_step")
    if not current_step:
        return Command(update=_preserve_core_fields(state), goto="scheduler")

    _set_runtime_agent_name(config, agent_name)

    configurable = Configuration.from_runnable_config(config)
    locale = state.get("locale", "zh-CN")
    if agent_name == "tabular":
        agent_resources = _resources_for_tabular_execution(state.get("resources", []))
    else:
        agent_resources = _resources_for_agent(state.get("resources", []), agent_name)
    mcp_servers = {}
    enabled_tools = {}

    if configurable.mcp_settings:
        for server_name, server_config in configurable.mcp_settings["servers"].items():
            if server_config["enabled_tools"] and agent_name in server_config["add_to_agents"]:
                mcp_servers[server_name] = {
                    k: v
                    for k, v in server_config.items()
                    if k in ("transport", "command", "args", "url", "env", "headers")
                }
                for tool_name in server_config["enabled_tools"]:
                    enabled_tools[tool_name] = server_name

    loaded_tools = default_tools[:]
    if mcp_servers:
        client = MultiServerMCPClient(mcp_servers)
        all_tools = await client.get_tools()
        for tool_item in all_tools:
            if tool_item.name in enabled_tools:
                loaded_tools.append(tool_item)

    llm_token_limit = get_llm_token_limit_by_type(AGENT_LLM_MAP[agent_name])
    pre_model_hook = None
    if agent_name != "tabular":
        pre_model_hook = partial(ContextManager(llm_token_limit, 3).compress_messages)
    agent = create_agent(
        agent_name,
        agent_name,
        loaded_tools,
        prompt_name,
        pre_model_hook=pre_model_hook,
        locale=NEO_PROMPT_LOCALE,
    )

    completed_steps = state.get("completed_steps", [])
    completed_text = "\n\n".join(
        [
            f"## {step.title}\n{step.execution_res or ''}"
            for step in completed_steps
            if step.execution_res
        ]
    )
    history_messages = list(state.get("messages", []))
    agent_input = {
        "messages": history_messages
        + [
            HumanMessage(
                content=(
                    f"# User Task\n{state.get('research_topic', '')}\n\n"
                    f"# Task Title\n{state.get('task_title', '')}\n\n"
                    f"# Resources\n{_format_resources_for_prompt(agent_resources)}\n\n"
                    f"# Preprocess\n{state.get('preprocess_summary', '')}\n\n"
                    f"# Completed Findings\n{completed_text or 'None'}\n\n"
                    f"# Current Step\nTitle: {current_step.title}\n"
                    f"Description: {current_step.description}\n"
                    f"Type: {current_step.step_type.value}"
                )
            )
        ]
    }
    _inject_runtime_instruction(
        agent_input["messages"],
        _build_subagent_runtime_instruction(agent_name, locale),
    )

    try:
        agent_input["messages"] = validate_message_content(agent_input["messages"])
        result = await agent.ainvoke(
            input=agent_input,
            config={"recursion_limit": config.get("recursion_limit", 25)},
        )
        result_messages = result.get("messages", [])
        last_content = str(result_messages[-1].content) if result_messages else ""
        if agent_name == "visual3d":
            response_content = sanitize_tool_response(
                _extract_visual3d_observation(result_messages)
                or last_content
            )
        else:
            response_content = sanitize_tool_response(last_content)
    except Exception as exc:
        logger.exception("neo %s execution failed", agent_name)
        response_content = f"[ERROR] {agent_name}: {exc}"
        result = {"messages": [AIMessage(content=response_content, name=agent_name)]}

    executed_step = current_step.model_copy(update={"execution_res": response_content})
    completed = list(state.get("completed_steps", [])) + [executed_step]

    return Command(
        update={
            **_preserve_core_fields(state),
            "messages": result.get("messages", []),
            "completed_steps": completed,
            "current_step": None,
            "observations": list(state.get("observations", [])) + [response_content],
        },
        goto="scheduler",
    )


async def _load_rag_tools(state: NeoState) -> list:
    tools = []
    rag_resources = _resources_for_agent(state.get("resources", []), "rag")
    kb_files_tool = get_kb_files_tool(rag_resources, include_unbound=False)
    if kb_files_tool:
        tools.append(kb_files_tool)
    retriever_tool = get_retriever_tool(rag_resources)
    if retriever_tool:
        tools.append(retriever_tool)
    return tools


async def _load_tabular_tools(state: NeoState) -> list:
    tools = [read_full_tabular_file, python_repl_tool]
    rag_resources = _resources_for_agent(state.get("resources", []), "rag")
    kb_files_tool = get_kb_files_tool(rag_resources, include_unbound=False)
    if kb_files_tool:
        tools.insert(0, kb_files_tool)
    try:
        sql_tools = get_sql_toolkit(_resources_for_agent(state.get("resources", []), "tabular"))
        tools.extend(sql_tools)
    except Exception as exc:
        logger.warning("neo tabular toolkit init failed: %s", exc)
    return tools


async def _load_visual3d_tools(state: NeoState) -> list:
    from src.subagents.visual3d.commander import get_visual3d_tool

    return [get_visual3d_tool(_resources_for_agent(state.get("resources", []), "visual3d"))]


async def _load_circuit_tools(state: NeoState) -> list:
    from src.subagents.circuit.circuit_rag import get_circuit_tool

    circuit_resources = _resources_for_agent(state.get("resources", []), "circuit")

    return [get_circuit_tool(collection_name=circuit_resource.uri) for circuit_resource in circuit_resources]

subagents = {
    "rag": {
        "prompt_name": "neo/rag",
        "tool_loader": _load_rag_tools,
    },
    "tabular": {
        "prompt_name": "neo/tabular",
        "tool_loader": _load_tabular_tools,
    },
    "visual3d": {
        "prompt_name": "neo/visual3d",
        "tool_loader": _load_visual3d_tools,
    },
    "circuit": {
        "prompt_name": "neo/circuit",
        "tool_loader": _load_circuit_tools,
    },
}

async def subagent_node(state: NeoState, config: RunnableConfig) -> Command[Literal["scheduler"]]:
    current_step = state.get("current_step")
    if not current_step:
        return Command(update=_preserve_core_fields(state), goto="scheduler")

    agent_name = current_step.step_type.value
    _set_runtime_agent_name(config, agent_name)

    subagent = subagents.get(agent_name)
    if not subagent:
        logger.warning("neo subagent '%s' is not configured", agent_name)
        response_content = f"[ERROR] Unsupported subagent: {agent_name}"
        executed_step = current_step.model_copy(update={"execution_res": response_content})
        completed = list(state.get("completed_steps", [])) + [executed_step]
        return Command(
            update={
                **_preserve_core_fields(state),
                "messages": [AIMessage(content=response_content, name=agent_name)],
                "completed_steps": completed,
                "current_step": None,
                "observations": list(state.get("observations", [])) + [response_content],
            },
            goto="scheduler",
        )

    tools = await subagent["tool_loader"](state)
    return await _execute_step(
        state,
        config,
        agent_name=agent_name,
        prompt_name=subagent["prompt_name"],
        default_tools=tools,
    )


def summary_node(state: NeoState, config: RunnableConfig) -> Command[Literal["__end__"]]:
    logger.info("neo summary writing final answer")

    locale = state.get("locale", "zh-CN")
    configurable = Configuration.from_runnable_config(config)
    invoke_messages = apply_prompt_template("neo/summary", state, configurable, NEO_PROMPT_LOCALE)
    scheduler_thought = (state.get("scheduler_thought") or "").strip()
    if scheduler_thought:
        invoke_messages.append(
            HumanMessage(
                content=f"# Scheduler Thought\n{scheduler_thought}",
                name="scheduler",
            )
        )
    observation_messages = [
        HumanMessage(content=f"Finding:\n{item}", name="observation")
        for item in state.get("observations", [])
    ]
    if state.get("fact_check_report"):
        observation_messages.append(
            HumanMessage(
                content=(
                    "# Fact Check Report\n"
                    f"{_format_fact_check_report_for_prompt(state['fact_check_report'])}"
                ),
                name="fact_check",
            )
        )
    llm_token_limit = get_llm_token_limit_by_type(AGENT_LLM_MAP["summarize"])
    compressed_state = ContextManager(llm_token_limit).compress_messages(
        {"messages": observation_messages}
    )
    invoke_messages += compressed_state.get("messages", [])
    response = get_llm_by_type(AGENT_LLM_MAP["summarize"]).invoke(invoke_messages)
    response_content = str(response.content)
    compact_messages = _filter_conversation_history_for_summary(
        list(state.get("messages", [])),
        response_content,
    )
    return Command(
        update={
            "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *compact_messages],
            "final_answer": response_content,
        },
        goto="__end__",
    )


def fact_check_node(state: NeoState, config: RunnableConfig) -> Command[Literal["summarize"]]:
    logger.info("neo fact check validating cited draft")
    locale = state.get("locale", "zh-CN")
    configurable = Configuration.from_runnable_config(config)
    rag_resources = _resources_for_agent(state.get("resources", []), "rag")
    rag_steps = _completed_steps_for_type(state, StepType.RAG)
    resource_catalog = _build_resource_catalog(rag_resources)
    evidence_texts = [step.execution_res for step in rag_steps if step.execution_res]
    summary_state = {
        "messages": [],
        "locale": locale,
        "research_topic": state.get("research_topic", ""),
        "task_title": state.get("task_title", ""),
        "resource_catalog_prompt": _format_resource_catalog_for_prompt(resource_catalog),
        "fact_check_observation_digest": _format_fact_check_observation_digest(evidence_texts),
        "max_claims": FACT_CHECK_SUMMARY_MAX_CLAIMS,
    }
    invoke_messages = apply_prompt_template(
        "neo/fact_check_summary",
        summary_state,
        configurable,
        NEO_PROMPT_LOCALE,
    )
    observation_messages = [
        HumanMessage(content=f"Finding:\n{item}", name="observation")
        for item in evidence_texts
    ]
    llm_token_limit = get_llm_token_limit_by_type(AGENT_LLM_MAP["summarize"])
    compressed_state = ContextManager(llm_token_limit).compress_messages(
        {"messages": observation_messages}
    )
    invoke_messages += compressed_state.get("messages", [])
    summary_model = get_llm_by_type(AGENT_LLM_MAP["summarize"])
    draft = _invoke_fact_check_summary_with_retries(
        invoke_messages,
        resource_catalog=resource_catalog,
        evidence_texts=evidence_texts,
        locale=locale,
        summary_llm=summary_model,
    )

    claim_payloads = []
    for idx, claim in enumerate(draft.claims):
        citation_resolution = _resolve_claim_citations(
            claim.citation_ids,
            resource_catalog,
            claim.text,
            evidence_texts,
        )
        claim_payload = _claim_to_prompt_payload(
            idx,
            claim,
            citation_resolution["resolved_citation_ids"],
        )
        claim_payload["citation_factor"] = _get_citation_factor(
            exact_citation_ids=citation_resolution["exact_citation_ids"],
            alias_citation_ids=citation_resolution["alias_citation_ids"],
            context_citation_ids=citation_resolution["context_citation_ids"],
            invalid_citation_ids=citation_resolution["invalid_citation_ids"],
        )
        claim_payloads.append(claim_payload)

    review = _fallback_fact_check_review(claim_payloads, evidence_texts)

    report = _build_grounding_report(draft, review, resource_catalog, evidence_texts)

    return Command(
        update={
            **_preserve_core_fields(state),
            "fact_check_review": review.model_dump(),
            "fact_check_report": report,
            # TODO: 多方案，至少 80%
            "grounding_score": report.get("grounding_score", 0.0),
        },
        goto="summarize",
    )
