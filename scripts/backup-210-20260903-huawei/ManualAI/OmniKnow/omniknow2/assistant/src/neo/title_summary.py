from src.config.agents import AGENT_LLM_MAP
from src.llms.llm import get_llm_by_type

TITLE_SUMMARY_PROMPT = """
你是一个历史对话标题总结助手。
请根据给定对话生成一个 10 字左右的中文标题。

要求：
1. 只输出标题本身
2. 不要输出解释、前后缀、引号或标点
3. 标题要尽量概括对话核心主题
"""


def generate_title_summary(messages: list[dict], locale: str = "zh-CN") -> str:
    llm = get_llm_by_type(AGENT_LLM_MAP["summarize"])
    response = llm.invoke(
        [
            {"role": "system", "content": TITLE_SUMMARY_PROMPT},
            *messages,
        ]
    )
    return str(response.content).strip().splitlines()[0].strip().strip("\"'“”")
