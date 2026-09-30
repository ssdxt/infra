from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.prompts.planner_model import StepType

from .nodes import (
    coordinator_node,
    router_node,
    scheduler_node,
    manager_node,
    writer_node,
    summary_node
)
from .types import State


def continue_to_running_omniknow_team(state: State):
    current_plan = state.get("current_plan")
    if not current_plan or not current_plan.steps:
        return "scheduler"

    if all(step.execution_res for step in current_plan.steps):
        return "scheduler"

    # Find first incomplete step
    incomplete_step = None
    for step in current_plan.steps:
        if not step.execution_res:
            incomplete_step = step
            break

    if not incomplete_step:
        return "scheduler"
    
    # get incomplete step type
    if incomplete_step.step_type == StepType.WRITER:
        return "writer"
    return "scheduler"


def _build_report_graph():
    """Build and return the base state graph with all nodes and edges."""
    builder = StateGraph(State)
    builder.add_node("coordinator", coordinator_node)
    builder.add_node("scheduler", scheduler_node)
    builder.add_node("manager", manager_node)
    builder.add_node("writer", writer_node)
    builder.add_node("router", router_node)
    builder.add_node("summarize", summary_node)

    builder.add_edge(START, "coordinator")
    builder.add_conditional_edges(
        "manager",
        continue_to_running_omniknow_team,
        ["scheduler", "writer"],
    )
    builder.add_edge("summarize", END) 
    return builder


def build_graph_with_memory():
    """Build and return the agent workflow graph with memory."""
    # use persistent memory to save conversation history
    memory = MemorySaver()

    # build state graph
    builder = _build_report_graph()
    return builder.compile(checkpointer=memory)


def build_graph():
    """Build and return the agent workflow graph without memory."""
    # build state graph
    builder = _build_report_graph()
    return builder.compile()