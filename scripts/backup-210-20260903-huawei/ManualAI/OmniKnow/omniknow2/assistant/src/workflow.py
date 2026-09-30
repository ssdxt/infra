import logging

from src.config.configuration import get_recursion_limit
from src.neo import build_graph

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Default level is INFO
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def enable_debug_logging():
    """Enable debug level logging for more detailed execution information."""
    logging.getLogger("src").setLevel(logging.DEBUG)


logger = logging.getLogger(__name__)

# Create the graph
graph = build_graph()


async def run_agent_workflow_async(
    user_input: str,
    debug: bool = False,
    max_plan_iterations: int = 1,
    max_step_num: int = 3,
    enable_background_investigation: bool = True,
    enable_clarification: bool | None = None,
    max_clarification_rounds: int | None = None,
    initial_state: dict | None = None,
):
    """Run the neo workflow asynchronously with the given user input.

    Args:
        user_input: The user's query or request
        debug: If True, enables debug level logging
        max_plan_iterations: Deprecated for neo workflow, kept for compatibility
        max_step_num: Deprecated for neo workflow, kept for compatibility
        enable_background_investigation: Deprecated for neo workflow, kept for compatibility
        enable_clarification: Deprecated for neo workflow, kept for compatibility
        max_clarification_rounds: Deprecated for neo workflow, kept for compatibility
        initial_state: Optional initial state override

    Returns:
        The final state after the workflow completes
    """
    if not user_input:
        raise ValueError("Input could not be empty")

    if debug:
        enable_debug_logging()

    logger.info(f"Starting async workflow with user input: {user_input}")

    if initial_state is None:
        initial_state = {
            "messages": [{"role": "user", "content": user_input}],
            "research_topic": user_input,
            "locale": "en-US",
            "scheduler_thought": "",
            "resources": [],
            "observations": [],
            "completed_steps": [],
            "current_step": None,
            "final_answer": "",
            "task_title": "",
            "preprocess_done": False,
            "preprocess_summary": "",
            "image_url": "",
            "user_id": "anonymous",
            "enable_longterm_memory": False,
        }

    config = {
        "configurable": {
            "thread_id": "default",
            "mcp_settings": {
                "servers": {
                    "mcp-github-trending": {
                        "transport": "stdio",
                        "command": "uvx",
                        "args": ["mcp-github-trending"],
                        "enabled_tools": ["get_github_trending_repositories"],
                        "add_to_agents": ["rag"],
                    }
                }
            },
        },
        "recursion_limit": get_recursion_limit(default=100),
    }
    last_message_cnt = 0
    final_state = None
    async for s in graph.astream(
        input=initial_state, config=config, stream_mode="values"
    ):
        try:
            final_state = s
            if isinstance(s, dict) and "messages" in s:
                if len(s["messages"]) <= last_message_cnt:
                    continue
                last_message_cnt = len(s["messages"])
                message = s["messages"][-1]
                if isinstance(message, tuple):
                    print(message)
                else:
                    message.pretty_print()
            else:
                print(f"Output: {s}")
        except Exception as e:
            logger.error(f"Error processing stream output: {e}")
            print(f"Error processing output: {str(e)}")

    logger.info("Async workflow completed successfully")
    return final_state


if __name__ == "__main__":
    print(graph.get_graph(xray=True).draw_mermaid())
