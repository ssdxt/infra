from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import (
    coordinator_node,
    fact_check_node,
    scheduler_node,
    subagent_node,
    summary_node,
)
from .state import NeoState


def _build_neo_graph():
    builder = StateGraph(NeoState)
    builder.add_node("coordinator", coordinator_node)
    builder.add_node("scheduler", scheduler_node)
    builder.add_node("subagent", subagent_node)
    builder.add_node("summarize", summary_node)
    builder.add_node("fact_check", fact_check_node)

    builder.add_edge(START, "coordinator")
    builder.add_edge("fact_check", "summarize")
    builder.add_edge("summarize", END)
    return builder


def build_graph():
    return _build_neo_graph().compile()


def build_graph_with_memory():
    return _build_neo_graph().compile(checkpointer=MemorySaver())
