import asyncio
from types import SimpleNamespace

from src.neo.nodes import SCHEDULER_MAX_SUBAGENT_CALLS, scheduler_node, summary_node
from src.neo.types import NeoPlan, Step, StepType


def _completed_step(step_type: StepType, execution_res: str = "done") -> Step:
    return Step(
        title=f"{step_type.value} step",
        description="test step",
        step_type=step_type,
        execution_res=execution_res,
    )


def _planned_step(step_type: StepType) -> Step:
    return Step(
        title=f"next {step_type.value} step",
        description="planned step",
        step_type=step_type,
    )


def test_summary_node_includes_scheduler_thought_in_llm_input(monkeypatch):
    captured = {}

    class DummyLLM:
        def invoke(self, messages):
            captured["messages"] = messages
            return SimpleNamespace(content="final answer")

    monkeypatch.setattr("src.neo.nodes.apply_prompt_template", lambda *args, **kwargs: [])
    monkeypatch.setattr("src.neo.nodes.get_llm_by_type", lambda *_: DummyLLM())
    monkeypatch.setattr("src.neo.nodes.get_llm_token_limit_by_type", lambda *_: 4096)

    command = summary_node(
        {
            "locale": "zh-CN",
            "research_topic": "帮我总结排查结果",
            "scheduler_thought": "应该优先总结已经确认的表格结果，并说明为什么现在结束。",
            "observations": [],
            "completed_steps": [],
        },
        {"configurable": {}},
    )

    assert command.goto == "__end__"
    assert command.update["final_answer"] == "final answer"
    assert any(
        getattr(message, "content", "") == (
            "# Scheduler Thought\n"
            "应该优先总结已经确认的表格结果，并说明为什么现在结束。"
        )
        for message in captured["messages"]
    )


def test_scheduler_node_persists_thought_for_summary(monkeypatch):
    async def fake_run_preprocess(state, config):
        return "preprocess summary"

    monkeypatch.setattr("src.neo.nodes._run_preprocess", fake_run_preprocess)
    monkeypatch.setattr("src.neo.nodes._build_scheduler_prompt_state", lambda *args, **kwargs: {})
    monkeypatch.setattr("src.neo.nodes.apply_prompt_template", lambda *args, **kwargs: [])
    monkeypatch.setattr("src.neo.nodes.get_llm_by_type", lambda *_: object())
    monkeypatch.setattr(
        "src.neo.nodes._invoke_scheduler_with_retries",
        lambda *args, **kwargs: NeoPlan(
            locale="zh-CN",
            thought="已经拿到足够结果，可以结束并进入总结。",
            title="总结当前结果",
            next_step=None,
        ),
    )

    command = asyncio.run(
        scheduler_node(
            {
                "locale": "zh-CN",
                "research_topic": "总结当前结果",
                "resources": [],
                "observations": ["已完成一次检索"],
                "completed_steps": [],
            },
            {"configurable": {}},
        )
    )

    assert command.goto == "summarize"
    assert command.update["scheduler_thought"] == "已经拿到足够结果，可以结束并进入总结。"


def test_scheduler_node_promotes_direct_answer_to_observation(monkeypatch):
    async def fake_run_preprocess(state, config):
        return "preprocess summary"

    monkeypatch.setattr("src.neo.nodes._run_preprocess", fake_run_preprocess)
    monkeypatch.setattr("src.neo.nodes._build_scheduler_prompt_state", lambda *args, **kwargs: {})
    monkeypatch.setattr("src.neo.nodes.apply_prompt_template", lambda *args, **kwargs: [])
    monkeypatch.setattr("src.neo.nodes.get_llm_by_type", lambda *_: object())
    monkeypatch.setattr(
        "src.neo.nodes._invoke_scheduler_with_retries",
        lambda *args, **kwargs: NeoPlan(
            locale="zh-CN",
            thought="用户询问知识库数量，可由提供的资源列表直接回答。",
            title="查询当前知识库的数量",
            direct_answer="当前有 6 个知识库。",
            next_step=None,
        ),
    )

    command = asyncio.run(
        scheduler_node(
            {
                "locale": "zh-CN",
                "research_topic": "当前有多少个知识库？",
                "resources": [],
                "observations": [],
                "completed_steps": [],
            },
            {"configurable": {}},
        )
    )

    assert command.goto == "summarize"
    assert "[SCHEDULER_DIRECT_ANSWER] 当前有 6 个知识库。" in command.update["observations"]
    assert not any("No grounded execution result" in item for item in command.update["observations"])


def test_scheduler_node_routes_to_fact_check_when_last_completed_step_is_rag(monkeypatch):
    async def fake_run_preprocess(state, config):
        return "preprocess summary"

    monkeypatch.setattr("src.neo.nodes._run_preprocess", fake_run_preprocess)
    monkeypatch.setattr("src.neo.nodes._build_scheduler_prompt_state", lambda *args, **kwargs: {})
    monkeypatch.setattr("src.neo.nodes.apply_prompt_template", lambda *args, **kwargs: [])
    monkeypatch.setattr("src.neo.nodes.get_llm_by_type", lambda *_: object())
    monkeypatch.setattr(
        "src.neo.nodes._invoke_scheduler_with_retries",
        lambda *args, **kwargs: NeoPlan(
            locale="zh-CN",
            thought="已经拿到足够结果，可以结束并进入事实核查。",
            title="总结当前结果",
            next_step=None,
        ),
    )

    command = asyncio.run(
        scheduler_node(
            {
                "locale": "zh-CN",
                "research_topic": "总结当前结果",
                "resources": [],
                "observations": ["已完成一次检索"],
                "completed_steps": [_completed_step(StepType.RAG)],
            },
            {"configurable": {}},
        )
    )

    assert command.goto == "fact_check"


def test_scheduler_node_skips_fact_check_when_rag_is_not_last_completed_step(monkeypatch):
    async def fake_run_preprocess(state, config):
        return "preprocess summary"

    monkeypatch.setattr("src.neo.nodes._run_preprocess", fake_run_preprocess)
    monkeypatch.setattr("src.neo.nodes._build_scheduler_prompt_state", lambda *args, **kwargs: {})
    monkeypatch.setattr("src.neo.nodes.apply_prompt_template", lambda *args, **kwargs: [])
    monkeypatch.setattr("src.neo.nodes.get_llm_by_type", lambda *_: object())
    monkeypatch.setattr(
        "src.neo.nodes._invoke_scheduler_with_retries",
        lambda *args, **kwargs: NeoPlan(
            locale="zh-CN",
            thought="已经拿到足够结果，可以结束并进入总结。",
            title="总结当前结果",
            next_step=None,
        ),
    )

    command = asyncio.run(
        scheduler_node(
            {
                "locale": "zh-CN",
                "research_topic": "总结当前结果",
                "resources": [],
                "observations": ["已完成检索和表格分析"],
                "completed_steps": [
                    _completed_step(StepType.RAG),
                    _completed_step(StepType.TABULAR),
                ],
            },
            {"configurable": {}},
        )
    )

    assert command.goto == "summarize"


def test_scheduler_node_keeps_dispatching_before_reaching_subagent_limit(monkeypatch):
    async def fake_run_preprocess(state, config):
        return "preprocess summary"

    monkeypatch.setattr("src.neo.nodes._run_preprocess", fake_run_preprocess)
    monkeypatch.setattr("src.neo.nodes._build_scheduler_prompt_state", lambda *args, **kwargs: {})
    monkeypatch.setattr("src.neo.nodes.apply_prompt_template", lambda *args, **kwargs: [])
    monkeypatch.setattr("src.neo.nodes.get_llm_by_type", lambda *_: object())
    monkeypatch.setattr(
        "src.neo.nodes._invoke_scheduler_with_retries",
        lambda *args, **kwargs: NeoPlan(
            locale="zh-CN",
            thought="继续执行下一步表格分析。",
            title="继续分析",
            next_step=_planned_step(StepType.TABULAR),
        ),
    )

    command = asyncio.run(
        scheduler_node(
            {
                "locale": "zh-CN",
                "research_topic": "继续分析",
                "resources": [],
                "observations": ["已完成两步"],
                "completed_steps": [
                    _completed_step(StepType.RAG),
                    _completed_step(StepType.TABULAR),
                ],
            },
            {"configurable": {}},
        )
    )

    assert command.goto == "subagent"
    assert command.update["current_step"].step_type == StepType.TABULAR


def test_scheduler_node_stops_dispatching_after_reaching_subagent_limit(monkeypatch):
    async def fake_run_preprocess(state, config):
        return "preprocess summary"

    monkeypatch.setattr("src.neo.nodes._run_preprocess", fake_run_preprocess)
    monkeypatch.setattr("src.neo.nodes._build_scheduler_prompt_state", lambda *args, **kwargs: {})
    monkeypatch.setattr("src.neo.nodes.apply_prompt_template", lambda *args, **kwargs: [])
    monkeypatch.setattr("src.neo.nodes.get_llm_by_type", lambda *_: object())
    monkeypatch.setattr(
        "src.neo.nodes._invoke_scheduler_with_retries",
        lambda *args, **kwargs: NeoPlan(
            locale="zh-CN",
            thought="还可以再派发表格分析。",
            title="继续分析",
            next_step=_planned_step(StepType.TABULAR),
        ),
    )

    command = asyncio.run(
        scheduler_node(
            {
                "locale": "zh-CN",
                "research_topic": "继续分析",
                "resources": [],
                "observations": ["已完成三步"],
                "completed_steps": [
                    _completed_step(StepType.TABULAR),
                    _completed_step(StepType.CIRCUIT),
                    _completed_step(StepType.RAG),
                ],
            },
            {"configurable": {}},
        )
    )

    assert len(command.update["completed_steps"]) == SCHEDULER_MAX_SUBAGENT_CALLS
    assert command.goto == "fact_check"
    assert command.update["current_step"] is None
    assert any("上限" in item for item in command.update["observations"])
