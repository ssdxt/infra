import dataclasses
import os
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape
from langgraph.prebuilt.chat_agent_executor import AgentState
from langchain_core.messages import AIMessage, HumanMessage

from src.config.configuration import Configuration

# Initialize Jinja2 environment
env = Environment(
    loader=FileSystemLoader(os.path.dirname(__file__)),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)


def get_prompt_template(prompt_name: str, locale: str = "zh-CN") -> str:
    """
    Load and return a prompt template using Jinja2 with locale support.

    Args:
        prompt_name: Name of the prompt template file (without .md extension)
        locale: Language locale (e.g., zh-CN, zh-CN). Defaults to zh-CN

    Returns:
        The template string with proper variable substitution syntax
    """
    try:
        # Normalize locale format
        normalized_locale = locale.replace("-", "_") if locale and locale.strip() else "zh_CN"
        
        # Try locale-specific template first (e.g., researcher.zh_CN.md)
        try:
            template = env.get_template(f"{prompt_name}.{normalized_locale}.md")
            return template.render()
        except TemplateNotFound:
            # Fallback to English template if locale-specific not found
            template = env.get_template(f"{prompt_name}.md")
            return template.render()
    except Exception as e:
        raise ValueError(f"Error loading template {prompt_name} for locale {locale}: {e}")


def apply_prompt_template(
    prompt_name: str, state: AgentState, configurable: Configuration = None, locale: str = "zh-CN"
) -> list:
    """
    Apply template variables to a prompt template and return formatted messages.

    Args:
        prompt_name: Name of the prompt template to use
        state: Current agent state containing variables to substitute
        configurable: Configuration object with additional variables
        locale: Language locale for template selection (e.g., zh-CN, zh-CN)

    Returns:
        List of messages with the system prompt as the first message
    """
    # Convert state to dict for template rendering
    state_vars = {
        "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        **state,
    }

    # Add configurable variables
    if configurable:
        state_vars.update(dataclasses.asdict(configurable))

    try:
        # Normalize locale format
        normalized_locale = locale.replace("-", "_") if locale and locale.strip() else "zh_CN"
        
        # Try locale-specific template first
        try:
            template = env.get_template(f"{prompt_name}.{normalized_locale}.md")
        except TemplateNotFound:
            # Fallback to English template
            template = env.get_template(f"{prompt_name}.md")
        
        system_prompt = template.render(**state_vars)
        return [{"role": "system", "content": system_prompt}] + state["messages"]
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name} for locale {locale}: {e}")

def apply_reporter_prompt_template(
    prompt_name: str, state: AgentState, configurable: Configuration = None, locale: str = "zh-CN"
) -> list:
    """
    Apply template variables to a prompt template and return formatted messages.

    Args:
        prompt_name: Name of the prompt template to use
        state: Current agent state containing variables to substitute
        configurable: Configuration object with additional variables
        locale: Language locale for template selection (e.g., zh-CN, zh-CN)

    Returns:
        List of messages with the system prompt as the first message
    """
    # Convert state to dict for template rendering
    state_vars = {
        "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        **state,
    }

    # Add configurable variables
    if configurable:
        state_vars.update(dataclasses.asdict(configurable))

    try:
        # Normalize locale format
        normalized_locale = locale.replace("-", "_") if locale and locale.strip() else "zh_CN"
        
        # Try locale-specific template first
        try:
            template = env.get_template(f"report_generator/{prompt_name}.{normalized_locale}.md")
        except TemplateNotFound:
            # Fallback to English template
            template = env.get_template(f"report_generator/{prompt_name}.md")
        
        system_prompt = template.render(**state_vars)
        return [{"role": "system", "content": system_prompt}] + state["messages"]
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name} for locale {locale}: {e}")

def apply_scheduler_prompt_template(
    prompt_name: str, state: AgentState, configurable: Configuration = None, locale: str = "zh-CN"
) -> list:
    """
    Apply template variables to a prompt template and return formatted messages.

    Args:
        prompt_name: Name of the prompt template to use
        state: Current agent state containing variables to substitute
        configurable: Configuration object with additional variables
        locale: Language locale for template selection (e.g., zh-CN, zh-CN)

    Returns:
        List of messages with the system prompt as the first message
    """
    # Convert state to dict for template rendering
    state_vars = {
        "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        **state,
    }

    # Add configurable variables
    if configurable:
        state_vars.update(dataclasses.asdict(configurable))

    try:
        # Normalize locale format
        normalized_locale = locale.replace("-", "_") if locale and locale.strip() else "zh_CN"
        
        # TODO: 增加一个逻辑，根据提供的 Resouces 的类别与类型，动态选择可以调用的 sub-agents
        
        


        # Try locale-specific template first
        try:
            template = env.get_template(f"{prompt_name}.{normalized_locale}.md")
        except TemplateNotFound:
            # Fallback to English template
            template = env.get_template(f"{prompt_name}.md")
        
        system_prompt = template.render(**state_vars)
        return [{"role": "system", "content": system_prompt}] + state["messages"]
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name} for locale {locale}: {e}")


def apply_summarize_prompt_template(
    prompt_name: str, state: AgentState, configurable: Configuration = None, locale: str = "zh-CN"
) -> list:
    """
    Apply template variables to a prompt template and return formatted messages.

    Args:
        prompt_name: Name of the prompt template to use
        state: Current agent state containing variables to substitute
        configurable: Configuration object with additional variables
        locale: Language locale for template selection (e.g., zh-CN, zh-CN)

    Returns:
        List of messages with the system prompt as the first message
    """
    # Convert state to dict for template rendering
    state_vars = {
        "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        **state,
    }

    valid_sub_agents = ["rag", "tabular", "visual3d", "circuit"]
    found_sub_agents = []
    MAX_HISTORY_ITER = 6
    history_msgs = state.get("messages", [])
    if len(history_msgs) > MAX_HISTORY_ITER:
        history_msgs = history_msgs[-MAX_HISTORY_ITER:]
    for msg in history_msgs:
        if isinstance(msg, AIMessage) and msg.name in valid_sub_agents:
            found_sub_agents.append(msg.name)
    found_sub_agents = sorted(set(found_sub_agents))
    rag_prompt = """
#### **详细分析** 
    - 详细的答案，或按步骤的解决方案、故障可能的原因。
    - 以结构化、易于遵循的方式呈现信息。
    - 突出意外或特别值得注意的细节。

#### **关键引用**
    - 在末尾以链接参考格式列出所有参考(带有 url 的真实文件)。
    - 在每个引用之间包括一个 `\n` 以获得更好的可读性。
    - 格式：`- [来源标题](URL)`
    - 注意所有的 url 都是真实的，不可以捏造
"""
    tabular_prompt = """
#### **统计分析**
    - 根据数据库执行结果，回答提问
    - 使用Markdown表呈现比较数据、统计数据、功能或选项。
    - 始终包括具有列名的清晰标题行。
    - 使用适当的Markdown表语法：
    ```markdown
    | 标题1 | 标题2 | 标题3 |
    |----------|----------|----------|
    | 数据1   | 数据2   | 数据3   |
    | 数据4   | 数据5   | 数据6   |
    ```
"""
    circuit_prompt = """
"""
    visual3d_prompt = """
"""
    sub_agents_prompt = ""
    if "rag" in found_sub_agents:
        sub_agents_prompt += rag_prompt
    elif "tabular" in found_sub_agents:
        sub_agents_prompt += tabular_prompt
    elif "circuit" in found_sub_agents:
        sub_agents_prompt += circuit_prompt
    elif "visual3d" in found_sub_agents:
        sub_agents_prompt += visual3d_prompt
    else:
        pass
    state_vars["sub_agents_prompt"] = sub_agents_prompt
    # Add configurable variables
    if configurable:
        state_vars.update(dataclasses.asdict(configurable))

    try:
        # Normalize locale format
        normalized_locale = locale.replace("-", "_") if locale and locale.strip() else "zh_CN"
        
        # Try locale-specific template first
        try:
            template = env.get_template(f"{prompt_name}.{normalized_locale}.md")
        except TemplateNotFound:
            # Fallback to English template
            template = env.get_template(f"{prompt_name}.md")
        
        system_prompt = template.render(**state_vars)
        current_plan = state.get("current_plan")
        reset_msgs = [
            HumanMessage(
                f"# Requirements\n\n## Task\n\n{current_plan.title}\n\n## Description\n\n{current_plan.thought}"
            )
        ]
        return [{"role": "system", "content": system_prompt}] + reset_msgs
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name} for locale {locale}: {e}")