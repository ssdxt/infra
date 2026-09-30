import json
import logging
import os
from functools import partial
from pathlib import Path
from typing import Any, Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.types import Command, interrupt
from langgraph.prebuilt import create_react_agent

from src.agents import create_report_subagent
from src.config.agents import AGENT_LLM_MAP
from src.config.configuration import Configuration
from src.config.loader import get_str_env
from src.llms.llm import get_llm_by_type, get_llm_token_limit_by_type
from src.prompts.planner_model import PlanRepoter
from src.prompts.template import apply_reporter_prompt_template, apply_summarize_prompt_template
from src.tools import get_retriever_tool

from src.utils.context_manager import ContextManager, validate_message_content
from src.utils.json_utils import repair_json_output, sanitize_tool_response, load_json, steps_to_markdown, flatten_json_tree
from .types import State
from .utils import (
    get_message_content,
    is_user_message,
)

logger = logging.getLogger(__name__)

REPORT_PROMPT_LOCALE = "zh-CN"


def resolve_report_schema_path(report_style: str) -> Path | None:
    """Resolve an optional schema file for the given report style."""
    schema_dir = (
        Path(__file__).resolve().parents[1]
        / "prompts"
        / "report_generator"
        / "schema"
    )
    candidate = schema_dir / f"{report_style}.json"
    if candidate.exists():
        return candidate
    return None

@tool
def handoff_to_scheduler(
    research_topic: Annotated[str, "The topic of the research task to be handed off."],
    locale: Annotated[str, "The user's detected language locale (e.g., en-US, zh-CN)."],
):
    """Handoff to scheduler agent to do plan."""
    # This tool is not returning anything: we're just using it
    # as a way for LLM to signal that it needs to hand off to scheduler agent
    return


@tool
def handoff_to_chatter(
    research_topic: Annotated[str, "The topic of talks to be handed off."],
    locale: Annotated[str, "The user's detected language locale (e.g., en-US, zh-CN)."],
):
    """Handoff to chat agent to do casual talk."""
    # This tool is not returning anything: we're just using it
    # as a way for LLM to signal that it needs to hand off to scheduler agent
    return


@tool
def handoff_after_clarification(
    locale: Annotated[str, "The user's detected language locale (e.g., en-US, zh-CN)."],
    research_topic: Annotated[
        str, "The clarified research topic based on all clarification rounds."
    ],
):
    """Handoff to scheduler after clarification rounds are complete. Pass all clarification history to scheduler for analysis."""
    return


def preserve_state_meta_fields(state: State) -> dict:
    """
    Extract meta/config fields that should be preserved across state transitions.
    
    These fields are critical for workflow continuity and should be explicitly
    included in all Command.update dicts to prevent them from reverting to defaults.
    
    Args:
        state: Current state object
        
    Returns:
        Dict of meta fields to preserve
    """
    return {
        "locale": state.get("locale", "en-US"),
        "research_topic": state.get("research_topic", ""),
        "clarified_research_topic": state.get("clarified_research_topic", ""),
        "clarification_history": state.get("clarification_history", []),
        "enable_clarification": state.get("enable_clarification", False),
        "max_clarification_rounds": state.get("max_clarification_rounds", 3),
        "clarification_rounds": state.get("clarification_rounds", 0),
        "resources": state.get("resources", []),
    }


def validate_and_fix_plan(plan: dict, enforce_web_search: bool = False) -> dict:
    """
    Validate and fix a plan to ensure it meets requirements.

    Args:
        plan: The plan dict to validate
        enforce_web_search: If True, ensure at least one step has need_search=true

    Returns:
        The validated/fixed plan dict
    """
    if not isinstance(plan, dict):
        # TODO: 怎么调整？
        return plan

    steps = plan.get("steps", [])

    # ============================================================
    # SECTION 1: Repair missing step_type fields (Issue #650 fix)
    # ============================================================
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        
        # Check if step_type is missing or empty
        if "step_type" not in step or not step.get("step_type"):
            step["step_type"] = "writer"
            logger.info(
                f"Repaired missing step_type for step {idx} ({step.get('title', 'Untitled')}): "
            )

    return plan


def scheduler_node(
    state: State, config: RunnableConfig
) -> Command[Literal["router", "summarize"]]:
    """Scheduler node that generate the full plan."""
    logger.info("Scheduler generating full plan with locale: %s", state.get("locale", "en-US"))
    configurable = Configuration.from_runnable_config(config)
    plan_iterations = state["plan_iterations"] if state.get("plan_iterations", 0) else 0

    # For clarification feature: use the clarified research topic (complete history)
    messages = apply_reporter_prompt_template("scheduler", state, configurable, REPORT_PROMPT_LOCALE)

    # TODO: schema 后续要传入
    schema_path = resolve_report_schema_path(configurable.report_style)
    if schema_path:
        schema = load_json(str(schema_path))
        # title_nums = count_titles(schema)
        messages.append(HumanMessage(content="参照`模板`:\n{}\n".format(schema)))
        messages.append(SystemMessage(content="CRITICAL: 严格按照上述模板的格式和目录结构，在理解用户请求后，修改主题"))
    else:
        logger.warning(
            "Report schema not found for style '%s'; continuing without schema template.",
            configurable.report_style,
        )
    if configurable.enable_deep_thinking:
        llm = get_llm_by_type("reasoning")
    elif AGENT_LLM_MAP["scheduler"] == "basic":
        llm = get_llm_by_type("basic")
    else:
        llm = get_llm_by_type(AGENT_LLM_MAP["scheduler"])

    # if the plan iterations is greater than the max plan iterations, return the reporter node
    # TODO: 超过标题个数就取消，最好改成别的如全文撰写完成标记
    if plan_iterations >= 1: 
        return Command(
            update=preserve_state_meta_fields(state),
            goto="summarize"
        )

    full_response = ""
    if AGENT_LLM_MAP["scheduler"] == "basic" and not configurable.enable_deep_thinking:
        response = llm.invoke(messages)
        if hasattr(response, "model_dump_json"):
            full_response = response.model_dump_json(indent=4, exclude_none=True)
        else:
            full_response = get_message_content(response) or ""
    else:
        response = llm.stream(messages)
        for chunk in response:
            full_response += chunk.content
    logger.info(f"Current state messages: {state['messages']}")
    logger.info(f"Scheduler response: {full_response}")

    # Validate explicitly that respkan'wonse content is valid JSON before proceeding to parse it
    if not full_response.strip().startswith('{') and not full_response.strip().startswith('['):
        logger.warning("Scheduler response does not appear to be valid JSON")
        if plan_iterations > 0:
            return Command(
                update=preserve_state_meta_fields(state),
                goto="summarize"
            )
        else:
            return Command(
                update=preserve_state_meta_fields(state),
                goto="__end__"
            )

    try:
        curr_plan = json.loads(repair_json_output(full_response))
        # Need to extract the plan from the full_response
        curr_plan_content = extract_plan_content(curr_plan)
        # load the current_plan
        curr_plan = json.loads(repair_json_output(curr_plan_content))
        curr_plan["steps"] = flatten_json_tree(curr_plan["steps"])
    except json.JSONDecodeError:
        logger.warning("Scheduler response is not a valid JSON")
        if plan_iterations > 0:
            return Command(
                update=preserve_state_meta_fields(state),
                goto="summarize"
            )
        else:
            return Command(
                update=preserve_state_meta_fields(state),
                goto="__end__"
            )
    # Validate and fix plan to ensure web search requirements are met
    if isinstance(curr_plan, dict):
        curr_plan = validate_and_fix_plan(curr_plan, configurable.enforce_web_search)

    return Command(
        update={ 
            "messages": [AIMessage(content=str(curr_plan), name="scheduler")],
            "current_plan": str(curr_plan),
            **preserve_state_meta_fields(state),
        },
        goto="router",
    )


def extract_plan_content(plan_data: str | dict | Any) -> str:
    """
    Safely extract plan content from different types of plan data.
    
    Args:
        plan_data: The plan data which can be a string, AIMessage, or dict
        
    Returns:
        str: The plan content as a string (JSON string for dict inputs, or 
    extracted/original string for other types)
    """
    if isinstance(plan_data, str):
        # If it's already a string, return as is
        return plan_data
    elif hasattr(plan_data, 'content') and isinstance(plan_data.content, str):
        # If it's an AIMessage or similar object with a content attribute
        logger.debug(f"Extracting plan content from message object of type {type(plan_data).__name__}")
        return plan_data.content
    elif isinstance(plan_data, dict):
        # If it's already a dictionary, convert to JSON string
        # Need to check if it's dict with content field (AIMessage-like)
        if "content" in plan_data:
            if isinstance(plan_data["content"], str):
                logger.debug("Extracting plan content from dict with content field")
                return plan_data["content"]
            if isinstance(plan_data["content"], dict):
                logger.debug("Converting content field dict to JSON string")
                return json.dumps(plan_data["content"], ensure_ascii=False)
            else:
                logger.warning(f"Unexpected type for 'content' field in plan_data dict: {type(plan_data['content']).__name__}, converting to string")
                return str(plan_data["content"])
        else:
            logger.debug("Converting plan dictionary to JSON string")
            return json.dumps(plan_data)
    else:
        # For any other type, try to convert to string
        logger.warning(f"Unexpected plan data type {type(plan_data).__name__}, attempting to convert to string")
        return str(plan_data)


def router_node(
    state: State, config: RunnableConfig
) -> Command[Literal["scheduler", "manager", "summarize", "__end__"]]:
    current_plan = state.get("current_plan", "")
    # check if the plan is auto accepted
    auto_accepted_plan = state.get("auto_accepted_plan", False)
    # auto_accepted_plan = True # 这里原来有个打断的动作，先保留这个入口
    if not auto_accepted_plan:
        feedback = interrupt("Please Review the Plan.")

        # Handle None or empty feedback
        if not feedback:
            logger.warning(f"Received empty or None feedback: {feedback}. Returning to scheduler for new plan.")
            return Command(
                update=preserve_state_meta_fields(state),
                goto="scheduler"
            )

        # Normalize feedback string
        feedback_normalized = str(feedback).strip().upper()

        # if the feedback is not accepted, return the planner node
        if feedback_normalized.startswith("[EDIT_PLAN]"):
            logger.info(f"Plan edit requested by user: {feedback}")
            return Command(
                update={
                    "messages": [
                        HumanMessage(content=feedback, name="feedback"),
                    ],
                    **preserve_state_meta_fields(state),
                },
                goto="scheduler",
            )
        elif feedback_normalized.startswith("[ACCEPTED]"):
            logger.info("Plan is accepted by user.")
        else:
            logger.warning(f"Unsupported feedback format: {feedback}. Please use '[ACCEPTED]' to accept or '[EDIT_PLAN]' to edit.")
            return Command(
                update=preserve_state_meta_fields(state),
                goto="scheduler"
            )

    # if the plan is accepted, run the following node
    plan_iterations = state["plan_iterations"] if state.get("plan_iterations", 0) else 0
    goto = "manager"
    try:
        # Safely extract plan content from different types (string, AIMessage, dict)
        original_plan = current_plan
        
        # Repair the JSON output
        current_plan = repair_json_output(current_plan)
        # parse the plan to dict
        current_plan = json.loads(current_plan)
        current_plan_content = extract_plan_content(current_plan)
        
        # increment the plan iterations
        plan_iterations += 1
        # parse the plan
        new_plan =  json.loads(repair_json_output(current_plan_content))
        new_plan["steps"] = flatten_json_tree(new_plan["steps"])
        # Validate and fix plan to ensure web search requirements are met
        configurable = Configuration.from_runnable_config(config)
        new_plan = validate_and_fix_plan(new_plan, configurable.enforce_web_search)
    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"Failed to parse plan: {str(e)}. Plan data type: {type(current_plan).__name__}")
        if isinstance(current_plan, dict) and "content" in original_plan:
            logger.warning(f"Plan appears to be an AIMessage object with content field")
        if plan_iterations > 1:  # the plan_iterations is increased before this check
            return Command(
                update=preserve_state_meta_fields(state),
                goto="summarize"
            )
        else:
            return Command(
                update=preserve_state_meta_fields(state),
                goto="__end__"
            )

    # Build update dict with safe locale handling
    update_dict = {
        "current_plan": PlanRepoter.model_validate(new_plan),
        "plan_iterations": plan_iterations,
        **preserve_state_meta_fields(state),
    }
    
    # Only override locale if new_plan provides a valid value, otherwise use preserved locale
    if new_plan.get("locale"):
        update_dict["locale"] = new_plan["locale"]
    
    return Command(
        update=update_dict,
        goto=goto,
    )


def coordinator_node(
    state: State, config: RunnableConfig
) -> Command[Literal["scheduler", "coordinator", "__end__"]]:
    """Coordinator node that communicate with customers and handle clarification."""
    logger.info("Coordinator talking.")
    configurable = Configuration.from_runnable_config(config)

    initial_topic = state.get("research_topic", "")
    clarified_topic = initial_topic
    
    # ============================================================
    # BRANCH 1: Clarification DISABLED (Legacy Mode)
    # ============================================================
    messages = apply_reporter_prompt_template("coordinator", state, configurable, REPORT_PROMPT_LOCALE)
    messages.append(
        {
            "role": "system",
            "content": """CRITICAL: Clarification is DISABLED. \nYou can call handoff_to_scheduler tool or handoff_to_chatter with the user's query as-is. \nIf user seems to want to chat or summary lastest result, call handoff_to_chatter.\nIf user seems to want to do rag or search or tooling, call handoff_to_scheduler.\nDo NOT ask questions or mention needing more information.""",
        }
    )

    tools = [handoff_to_scheduler, handoff_to_chatter]
    response = (
        get_llm_by_type(AGENT_LLM_MAP["coordinator"])
        .bind_tools(tools)
        .invoke(messages)
    )

    goto = "__end__"
    locale = state.get("locale", "zh-CN")
    logger.info(f"Coordinator locale: {locale}")
    research_topic = state.get("research_topic", "")

    # Process tool calls for legacy mode
    if response.tool_calls:
        try:
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})

                if tool_name == "handoff_to_chatter":
                    # ============================================================
                    # New Feature: Casual Chatter
                    # ============================================================
                    state_messages = list(state.get("messages", []))                        
                    logger.info("Handing off to casual chatter")
                    logger.info("Coordinator remains.")
                    goto = "__end__ "
                    
                # else:
                if tool_name == "handoff_to_scheduler":
                    logger.info("Handing off to scheduler")
                    goto = "scheduler"

                    # Extract research_topic if provided
                    if tool_args.get("research_topic"):
                        research_topic = tool_args.get("research_topic")
                    break

        except Exception as e:
            logger.error(f"Error processing tool calls: {e}")
            goto = "scheduler"
    
    # ============================================================
    # Final: Build and return Command
    # ============================================================
    messages = list(state.get("messages", []) or [])
    if response.content:
        messages.append(HumanMessage(content=response.content, name="coordinator"))

    # Process tool calls for BOTH branches (legacy and clarification)
    if response.tool_calls:
        try:
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name", "")
                tool_args = tool_call.get("args", {})

                if tool_name in ["handoff_to_scheduler"]:
                    logger.info("Handing off to scheduler")
                    goto = "scheduler"

                    if tool_args.get("research_topic"):
                        research_topic = tool_args["research_topic"]
                    logger.info(
                        "Using research topic for handoff: %s", research_topic
                    )
                    break

        except Exception as e:
            logger.error(f"Error processing tool calls: {e}")
            goto = "scheduler"
    else:
        # No tool calls detected - fallback to scheduler instead of ending
        logger.warning(
            "LLM didn't call any tools. This may indicate tool calling issues with the model. "
            "Falling back to scheduler to ensure research proceeds."
        )
        # Log full response for debugging
        logger.debug(f"Coordinator response content: {response.content}")
        logger.debug(f"Coordinator response object: {response}")
        # Fallback to scheduler to ensure workflow continues
        goto = "scheduler"

    # Apply background_investigation routing if enabled (unified logic)
    if goto == "scheduler" and state.get("enable_background_investigation"):
        # goto = "background_investigator"
        raise Exception("background_investigator not implemented yet")

    # Set default values for state variables (in case they're not defined in legacy mode)

    clarified_research_topic_value = clarified_topic or research_topic

    # clarified_research_topic: Complete clarified topic with all clarification rounds
    return Command(
        update={
            "messages": messages,
            "locale": locale,
            "research_topic": research_topic,
            "clarified_research_topic": clarified_research_topic_value,
            "resources": configurable.resources,
            "goto": goto,
        },
        goto=goto,
    )


def manager_node(state: State):
    """Research team node that collaborates on tasks."""
    logger.info("Manager is collaborating on tasks.")
    logger.debug("Entering manager_node - coordinating sub-agents")
    pass    



async def _execute_agent_step(
    state: State, agent, agent_name: str, config: RunnableConfig = None
) -> Command[Literal["manager"]]:
    """Helper function to execute a step using the specified agent."""
    logger.debug(f"[_execute_agent_step] Starting execution for agent: {agent_name}")
    
    current_plan = state.get("current_plan")
    plan_title = current_plan.title
    observations = state.get("observations", [])
    logger.debug(f"[_execute_agent_step] Plan title: {plan_title}, observations count: {len(observations)}")

    # Find the first unexecuted step
    current_step = None
    completed_steps = []
    for idx, step in enumerate(current_plan.steps):
        # TODO: 加入对 children 的解析
        if not step.execution_res:
            current_step = step
            logger.debug(f"[_execute_agent_step] Found unexecuted step at index {idx}: {step.title}")
            break
        else:
            completed_steps.append(step)

    if not current_step:
        logger.warning(f"[_execute_agent_step] No unexecuted step found in {len(current_plan.steps)} total steps")
        return Command(
            update=preserve_state_meta_fields(state),
            goto="manager"
        )
    # completed_steps
    logger.info(f"[_execute_agent_step] Executing step: {current_step.title}, agent: {agent_name}")
    logger.debug(f"[_execute_agent_step] Completed steps so far: {len(completed_steps)}")

    # 完成 step 的内容占用太多 token, 不传入上下文
    # Format completed steps information
    # completed_steps_info = ""
    # if completed_steps:
    #     completed_steps_info = "# Completed Research Steps\n\n"
    #     for i, step in enumerate(completed_steps):
    #         completed_steps_info += f"## Completed Step {i + 1}: {step.title}\n\n"
    #         completed_steps_info += f"<finding>\n{step.execution_res}\n</finding>\n\n"

    # Prepare the input for the agent with completed steps info
    agent_input = {
        "messages": [
            HumanMessage(
                # content=f"# Research Topic\n\n{plan_title}\n\n{completed_steps_info}# Current Step\n\n## Title\n\n{current_step.title}\n\n## Description\n\n{current_step.description}\n\n## Locale\n\n{state.get('locale', 'en-US')}"
                content=f"# Research Topic\n\n{plan_title}## Title\n\n{current_step.title}\n\n## Description\n\n{current_step.description}\n\n## Locale\n\n{state.get('locale', 'en-US')}"
            )
        ]
    }
    config['configurable']['step_id'] = current_step.id

    # Add citation reminder for researcher agent
    if agent_name == "writer":
        if state.get("resources"):
            resources_info = "**The user mentioned the following resource files:**\n\n"
            for resource in state.get("resources"):
                resources_info += f"- {resource.title} ({resource.description})\n"

            agent_input["messages"].append(
                HumanMessage(
                    content=resources_info
                    + "\n\n"
                    + "You MUST use the **local_search_tool** to retrieve the information from the resource files.",
                )
            )

        agent_input["messages"].append(
            HumanMessage(
                content="IMPORTANT: DO NOT include inline citations in the text. Instead, track all sources and include a References section at the end using link reference format. Include an empty line between each citation for better readability. Use this format for each reference:\n- [Source Title](URL)\n\n- [Another Source](URL)",
                name="system",
            )
        )

    # Invoke the agent
    default_recursion_limit = 100
    try:
        env_value_str = os.getenv("AGENT_RECURSION_LIMIT", str(default_recursion_limit))
        parsed_limit = int(env_value_str)

        if parsed_limit > 0:
            recursion_limit = parsed_limit
            logger.info(f"Recursion limit set to: {recursion_limit}")
        else:
            logger.warning(
                f"AGENT_RECURSION_LIMIT value '{env_value_str}' (parsed as   {parsed_limit}) is not positive. "
                f"Using default value {default_recursion_limit}."
            )
            recursion_limit = default_recursion_limit
    except ValueError:
        raw_env_value = os.getenv("AGENT_RECURSION_LIMIT")
        logger.warning(
            f"Invalid AGENT_RECURSION_LIMIT value: '{raw_env_value}'. "
            f"Using default value {default_recursion_limit}."
        )
        recursion_limit = default_recursion_limit

    logger.info(f"Agent input: {agent_input}")
    
    # Validate message content before invoking agent
    try:
        validated_messages = validate_message_content(agent_input["messages"])
        agent_input["messages"] = validated_messages
    except Exception as validation_error:
        logger.error(f"Error validating agent input messages: {validation_error}")
    
    # Apply context compression to prevent token overflow (Issue #721)
    llm_token_limit = get_llm_token_limit_by_type(AGENT_LLM_MAP[agent_name])
    if llm_token_limit:
        token_count_before = sum(
            len(str(msg.content).split()) for msg in agent_input.get("messages", []) if hasattr(msg, "content")
        )
        compressed_state = ContextManager(llm_token_limit, preserve_prefix_message_count=3).compress_messages(
            {"messages": agent_input["messages"]}
        )
        agent_input["messages"] = compressed_state.get("messages", [])
        token_count_after = sum(
            len(str(msg.content).split()) for msg in agent_input.get("messages", []) if hasattr(msg, "content")
        )
        logger.info(
            f"Context compression for {agent_name}: {len(compressed_state.get('messages', []))} messages, "
            f"estimated tokens before: ~{token_count_before}, after: ~{token_count_after}"
        )
    
    try:
        result = await agent.ainvoke(
            input=agent_input, config={"recursion_limit": recursion_limit}
        )
    except Exception as e:
        import traceback

        error_traceback = traceback.format_exc()
        error_message = f"Error executing {agent_name} agent for step '{current_step.title}': {str(e)}"
        logger.exception(error_message)
        logger.error(f"Full traceback:\n{error_traceback}")
        
        # Enhanced error diagnostics for content-related errors
        if "Field required" in str(e) and "content" in str(e):
            logger.error(f"Message content validation error detected")
            for i, msg in enumerate(agent_input.get('messages', [])):
                logger.error(f"Message {i}: type={type(msg).__name__}, "
                            f"has_content={hasattr(msg, 'content')}, "
                            f"content_type={type(msg.content).__name__ if hasattr(msg, 'content') else 'N/A'}, "
                            f"content_len={len(str(msg.content)) if hasattr(msg, 'content') and msg.content else 0}")

        detailed_error = f"[ERROR] {agent_name.capitalize()} Agent Error\n\nStep: {current_step.title}\n\nError Details:\n{str(e)}\n\nPlease check the logs for more information."
        current_step.execution_res = detailed_error

        return Command(
            update={
                "messages": [
                    HumanMessage(
                        content=detailed_error,
                        name=agent_name,
                    )
                ],
                "observations": observations + [detailed_error],
                **preserve_state_meta_fields(state),
            },
            goto="manager",
        )

    # Process the result
    response_content = result["messages"][-1].content
    
    # Sanitize response to remove extra tokens and truncate if needed
    response_content = sanitize_tool_response(str(response_content))
    
    logger.debug(f"{agent_name.capitalize()} full response: {response_content}")

    # Update the step with the execution result
    current_step.execution_res = response_content
    logger.info(f"Step '{current_step.title}' execution completed by {agent_name}")

    # Include all messages from agent result to preserve intermediate tool calls/results
    # This ensures multiple web_search calls all appear in the stream, not just the final result
    agent_messages = result.get("messages", [])
    logger.debug(
        f"{agent_name.capitalize()} returned {len(agent_messages)} messages. "
        f"Message types: {[type(msg).__name__ for msg in agent_messages]}"
    )
    
    # Count tool messages for logging
    tool_message_count = sum(1 for msg in agent_messages if isinstance(msg, ToolMessage))
    if tool_message_count > 0:
        logger.info(
            f"{agent_name.capitalize()} agent made {tool_message_count} tool calls. "
            f"All tool results will be preserved and streamed to frontend."
        )

    return Command(
        update={
            "messages": agent_messages,
            "observations": observations + [response_content],
            **preserve_state_meta_fields(state),
        },
        goto="manager",
    )


async def _setup_and_execute_agent_step(
    state: State,
    config: RunnableConfig,
    agent_type: str,
    default_tools: list,
) -> Command[Literal["manager"]]:
    """Helper function to set up an agent with appropriate tools and execute a step.

    This function handles the common logic for both writer_node and coder_node:
    1. Configures MCP servers and tools based on agent type
    2. Creates an agent with the appropriate tools or uses the default agent
    3. Executes the agent on the current step

    Args:
        state: The current state
        config: The runnable config
        agent_type: The type of agent ("researcher" or "coder")
        default_tools: The default tools to add to the agent

    Returns:
        Command to update state and go to manager
    """
    configurable = Configuration.from_runnable_config(config)
    mcp_servers = {}
    enabled_tools = {}
    
    # Extract MCP server configuration for this agent type
    if configurable.mcp_settings:
        for server_name, server_config in configurable.mcp_settings["servers"].items():
            if (
                server_config["enabled_tools"]
                and agent_type in server_config["add_to_agents"]
            ):
                mcp_servers[server_name] = {
                    k: v
                    for k, v in server_config.items()
                    if k in ("transport", "command", "args", "url", "env", "headers")
                }
                for tool_name in server_config["enabled_tools"]:
                    enabled_tools[tool_name] = server_name

    # Create and execute agent with MCP tools if available
    if mcp_servers:
        client = MultiServerMCPClient(mcp_servers)
        loaded_tools = default_tools[:]
        all_tools = await client.get_tools()
        for tool in all_tools:
            if tool.name in enabled_tools:
                tool.description = (
                    f"Powered by '{enabled_tools[tool.name]}'.\n{tool.description}"
                )
                loaded_tools.append(tool)

        llm_token_limit = get_llm_token_limit_by_type(AGENT_LLM_MAP[agent_type])
        pre_model_hook = partial(ContextManager(llm_token_limit, 3).compress_messages)
        agent = create_report_subagent(
            agent_type,
            agent_type,
            loaded_tools,
            agent_type,
            pre_model_hook,
            interrupt_before_tools=configurable.interrupt_before_tools,
            locale=REPORT_PROMPT_LOCALE,
        )
        return await _execute_agent_step(state, agent, agent_type, config)
    else:
        # Use default tools if no MCP servers are configured
        llm_token_limit = get_llm_token_limit_by_type(AGENT_LLM_MAP[agent_type])
        pre_model_hook = partial(ContextManager(llm_token_limit, 3).compress_messages)
        agent = create_report_subagent(
            agent_type,
            agent_type,
            default_tools,
            agent_type,
            pre_model_hook,
            interrupt_before_tools=configurable.interrupt_before_tools,
            locale=REPORT_PROMPT_LOCALE,
        )
         
        return await _execute_agent_step(state, agent, agent_type, config)


async def writer_node(
    state: State, config: RunnableConfig
) -> Command[Literal["manager"]]:
    """writer node that write docs"""
    logger.info("writer node is working.")
    logger.debug(f"[writer_node] Starting writer agent")
    

    
    configurable = Configuration.from_runnable_config(config)
    logger.debug(f"[writer_node] Max search results: {configurable.max_search_results}")
    
    # 取消 web search tool 和 crawl tool, 所有的 搜索都需要走 retriever tool
    tools = []
    retriever_tool = get_retriever_tool(state.get("resources", []))
    if retriever_tool:
        logger.debug(f"[writer_node] Adding retriever tool to tools list")
        tools.insert(0, retriever_tool)
    # TODO: 增加文本配图
    # image_tool = get_image_search_by_text_tool()
    # tools.append(image_tool)

    logger.info(f"[writer_node] writer tools count: {len(tools)}")
    logger.debug(f"[writer_node] writer tools: {[tool.name if hasattr(tool, 'name') else str(tool) for tool in tools]}")
    logger.info(f"[writer_node] enforce_researcher_search is set to: {configurable.enforce_researcher_search}")
    
    return await _setup_and_execute_agent_step(
        state,
        config,
        "writer",
        tools,
    )


def summary_node(state: State, config: RunnableConfig):
    """Summarizer node that write a final report."""
    logger.info("Summarizer write final report")
    configurable = Configuration.from_runnable_config(config)
    # TODO: 按照 plan 的结构修改
    # steps_to_markdown(state, '.', 'output.md')
    i = -1
    for current_step in state.get("current_plan").steps:
        # 按照 plan 的结构再遍历润色一次，保证逻辑通顺，总章节是子章节的总结
        i += 1
        if current_step.children_ids:
            config['configurable']['step_id'] = current_step.id
            child_res = "\n\n".join([
                                        f"{s.title}\n{s.execution_res[:1000]}..."
                                        for child_id in current_step.children_ids          
                                        for s in state.get("current_plan").steps   
                                        if s.id == child_id
                                    ])
            invoke_messages = [apply_reporter_prompt_template("summarize", state, configurable, REPORT_PROMPT_LOCALE)[0]]
            invoke_messages.append(HumanMessage(content=f"`父章节标题与内容`:\n\n{current_step.title}\n{current_step.execution_res}"))
            invoke_messages.append(HumanMessage(content=f"`子章节标题与内容`:\n\n{child_res}"))
            response = get_llm_by_type(AGENT_LLM_MAP["summarize"]).invoke(invoke_messages)
            state.get("current_plan").steps[i].execution_res = response.content       
            
        pass
    import time

    steps_to_markdown(state, '.', f'output-{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}.md')
    response_content = "已完成润色。"
    logger.info(f"summarize response: {response_content}")

    return Command(
        update={
                "messages": [
                AIMessage(
                    content=response_content,
                    name="summarize",
                )
            ]
        },
        goto="__end__"
    )
