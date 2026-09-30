from typing import Literal

# Define available LLM types
LLMType = Literal[
    "basic",
    "glm",
    "qwen3_next_80b",
    "qwen3_5_9b",
    "qwen3_5_4b",
    "deepseek_chat",
    "reasoning",
    "deepseek_reasoner",
    "vision",
    "code",
]

# Define agent-LLM mapping
AGENT_LLM_MAP: dict[str, LLMType] = {
    "coordinator": "basic",
    "planner": "basic",
    "researcher": "basic",
    "analyst": "basic",
    "coder": "basic",
    "reporter": "basic",
    "scheduler": "basic",
    "rag": "basic",
    "writer": "basic",
    "tabular": "basic",
    "visual3d": "basic",
    "circuit": "basic",
    "summarize": "basic",
    "fact_check": "basic",
    "image_search": "basic",
    "preprocess":"basic",
    "lite":"basic"
}
