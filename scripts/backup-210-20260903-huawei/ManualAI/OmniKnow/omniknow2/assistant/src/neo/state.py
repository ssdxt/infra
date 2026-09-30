from dataclasses import field

from langgraph.graph import MessagesState

from src.subagents.rag import Resource

from .types import Step


class NeoState(MessagesState):
    """Compact state for the neo graph."""

    locale: str = "en-US"
    research_topic: str = ""
    scheduler_thought: str = ""
    task_title: str = ""
    resources: list[Resource] = []
    observations: list[str] = field(default_factory=list)
    completed_steps: list[Step] = field(default_factory=list)
    current_step: Step | None = None
    final_answer: str = ""
    preprocess_done: bool = False
    preprocess_summary: str = ""
    image_url: str = ""
    user_id: str = "anonymous"
    enable_longterm_memory: bool = False
    fact_check_review: dict = field(default_factory=dict)
    fact_check_report: dict = field(default_factory=dict)
    grounding_score: float = 0.0
