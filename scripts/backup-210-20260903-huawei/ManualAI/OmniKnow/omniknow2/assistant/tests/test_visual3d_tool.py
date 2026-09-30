import json
import asyncio
from types import SimpleNamespace

from src.neo.nodes import _extract_visual3d_observation, subagent_node, summary_node
from src.prompts.planner_model import Step, StepType
from src.subagents.rag.retriever import Resource
from src.subagents.visual3d.commander import Visual3DTool


def test_visual3d_tool_uses_local_focus_resource(monkeypatch):
    monkeypatch.setattr(
        Visual3DTool,
        "_invoke_llm_decision",
        lambda self, query, prompt_resources: {
            "action": "postMessage",
            "message": {"type": "focus", "name": "底盘"},
        },
    )
    tool = Visual3DTool(
        resources=[
            Resource(
                uri="truck",
                title="重卡 3d 资源",
                description="",
                agent="visual3d",
            )
        ]
    )

    result = tool._run("查看重卡底盘的 3D 模型")

    assert result["action"] == "postMessage"
    assert result["message"]["type"] == "focus"
    assert result["message"]["id"] == "aff8e8c5-ec17-4752-b7fe-8e6512c2f0c0"
    assert result["target_name"] == "底盘"
    assert result["url"] == "https://www.czy3d.com/sample/ai-3d/#/?id=8714535002975444992"
    assert result["commands"] == [
        {
            "action": "postMessage",
            "message": {
                "type": "reset",
                "id": "EMPTY",
            },
        },
        {
            "action": "postMessage",
            "message": {
                "type": "focus",
                "id": "aff8e8c5-ec17-4752-b7fe-8e6512c2f0c0",
            },
        }
    ]
    assert result["resource"]["uri"] == "truck"
    assert result["available_actions"] == ["focus", "playAnimation"]


def test_visual3d_tool_uses_local_animation_resource(monkeypatch):
    monkeypatch.setattr(
        Visual3DTool,
        "_invoke_llm_decision",
        lambda self, query, prompt_resources: {
            "action": "postMessage",
            "message": {"type": "playAnimation", "name": "整车拆装"},
        },
    )
    tool = Visual3DTool(
        resources=[
            Resource(
                uri="truck",
                title="重卡 3d 资源",
                description="",
                agent="visual3d",
            )
        ]
    )

    result = tool._run("播放重卡拆解动画")

    assert result["action"] == "postMessage"
    assert result["message"]["type"] == "playAnimation"
    assert result["message"]["id"] == "f409689b-395b-425a-95a1-664b137ee0fb"
    assert result["target_name"] == "整车拆装"
    assert result["resource"]["title"] == "重卡 3d 资源"
    assert result["commands"] == [
        {
            "action": "postMessage",
            "message": {
                "type": "reset",
                "id": "EMPTY",
            },
        },
        {
            "action": "postMessage",
            "message": {
                "type": "playAnimation",
                "id": "f409689b-395b-425a-95a1-664b137ee0fb",
            },
        },
    ]


def test_visual3d_tool_always_prepends_reset(monkeypatch):
    responses = iter(
        [
            {
                "action": "postMessage",
                "message": {"type": "focus", "name": "底盘"},
            },
            {
                "action": "postMessage",
                "message": {"type": "playAnimation", "name": "整车拆装"},
            },
        ]
    )
    monkeypatch.setattr(
        Visual3DTool,
        "_invoke_llm_decision",
        lambda self, query, prompt_resources: next(responses),
    )
    tool = Visual3DTool(
        resources=[
            Resource(
                uri="truck",
                title="重卡 3d 资源",
                description="",
                agent="visual3d",
            )
        ]
    )

    first = tool._run("查看重卡底盘的 3D 模型")
    second = tool._run("播放重卡拆解动画")

    assert first["commands"] == [
        {
            "action": "postMessage",
            "message": {
                "type": "reset",
                "id": "EMPTY",
            },
        },
        {
            "action": "postMessage",
            "message": {
                "type": "focus",
                "id": "aff8e8c5-ec17-4752-b7fe-8e6512c2f0c0",
            },
        }
    ]
    assert second["message"]["type"] == "playAnimation"
    assert second["commands"] == [
        {
            "action": "postMessage",
            "message": {
                "type": "reset",
                "id": "EMPTY",
            },
        },
        {
            "action": "postMessage",
            "message": {
                "type": "playAnimation",
                "id": "f409689b-395b-425a-95a1-664b137ee0fb",
            },
        },
    ]
    assert "恢复到初始视角" in second["result"]


def test_visual3d_tool_resolves_llm_name_to_id(monkeypatch):
    monkeypatch.setattr(
        Visual3DTool,
        "_invoke_llm_decision",
        lambda self, query, prompt_resources: {
            "action": "postMessage",
            "message": {"type": "focus", "name": "驱动总成"},
        },
    )
    tool = Visual3DTool(
        resources=[
            Resource(
                uri="truck",
                title="重卡 3d 资源",
                description="",
                agent="visual3d",
            )
        ]
    )

    result = tool._run("请定位重卡驱动总成")

    assert result["message"]["type"] == "focus"
    assert result["message"]["id"] == "1f67638e-fc75-4ce1-84bd-71b35ff89cc1"
    assert result["target_name"] == "驱动总成"


def test_summary_node_passthroughs_pure_visual3d_payload():
    payload = {
        "action": "postMessage",
        "message": {
            "type": "focus",
            "id": "aff8e8c5-ec17-4752-b7fe-8e6512c2f0c0",
        },
        "commands": [
            {
                "action": "postMessage",
                "message": {
                    "type": "reset",
                    "id": "EMPTY",
                },
            },
            {
                "action": "postMessage",
                "message": {
                    "type": "focus",
                    "id": "aff8e8c5-ec17-4752-b7fe-8e6512c2f0c0",
                },
            }
        ],
        "target_name": "底盘",
        "url": "https://www.czy3d.com/sample/ai-3d/#/?id=8714535002975444992",
        "resource": {
            "uri": "truck",
            "title": "重卡 3d 资源",
            "description": "",
        },
        "available_actions": ["focus", "playAnimation"],
        "result": "已先将 `重卡 3d 资源` 恢复到初始视角，再执行 `focus` 指令。",
    }
    payload_text = json.dumps(payload, ensure_ascii=False)
    step = Step(
        title="展示重卡底盘",
        description="定位底盘",
        step_type=StepType.VISUAL3D,
        execution_res=payload_text,
    )

    command = summary_node(
        {
            "locale": "zh-CN",
            "research_topic": "查看重卡底盘的 3D 模型",
            "observations": [payload_text],
            "completed_steps": [step],
        },
        {"configurable": {}},
    )

    assert command.goto == "__end__"
    assert command.update["final_answer"] == payload_text


def test_extract_visual3d_observation_reads_structured_tool_payload():
    payload = {
        "action": "postMessage",
        "message": {
            "type": "focus",
            "id": "aff8e8c5-ec17-4752-b7fe-8e6512c2f0c0",
        },
        "commands": [
            {
                "action": "postMessage",
                "message": {
                    "type": "reset",
                    "id": "EMPTY",
                },
            },
            {
                "action": "postMessage",
                "message": {
                    "type": "focus",
                    "id": "aff8e8c5-ec17-4752-b7fe-8e6512c2f0c0",
                },
            },
        ],
        "url": "https://www.czy3d.com/sample/ai-3d/#/?id=8714535002975444992",
    }
    payload_text = json.dumps(payload, ensure_ascii=False)

    result = _extract_visual3d_observation(
        [
            SimpleNamespace(content="普通文本"),
            SimpleNamespace(content=payload_text),
        ]
    )

    assert result == payload_text


def test_visual3d_subagent_uses_bound_tool_flow(monkeypatch):
    step = Step(
        title="展示重卡底盘",
        description="定位底盘",
        step_type=StepType.VISUAL3D,
    )
    state = {
        "locale": "zh-CN",
        "research_topic": "查看重卡底盘的 3D 模型",
        "current_step": step,
        "resources": [],
        "observations": [],
        "completed_steps": [],
    }
    config = {"configurable": {}}
    loaded_tools = [object()]
    captured = {}

    async def fake_tool_loader(loader_state):
        captured["loader_state"] = loader_state
        return loaded_tools

    async def fake_execute_step(
        exec_state,
        exec_config,
        agent_name,
        prompt_name,
        default_tools,
    ):
        captured["exec_state"] = exec_state
        captured["exec_config"] = exec_config
        captured["agent_name"] = agent_name
        captured["prompt_name"] = prompt_name
        captured["default_tools"] = default_tools
        return {"goto": "scheduler"}

    monkeypatch.setitem(
        subagent_node.__globals__["subagents"]["visual3d"],
        "tool_loader",
        fake_tool_loader,
    )
    monkeypatch.setattr(
        "src.neo.nodes._execute_step",
        fake_execute_step,
    )

    result = asyncio.run(subagent_node(state, config))

    assert result == {"goto": "scheduler"}
    assert captured["loader_state"] is state
    assert captured["exec_state"] is state
    assert captured["exec_config"] is config
    assert captured["agent_name"] == "visual3d"
    assert captured["prompt_name"] == "neo/visual3d"
    assert captured["default_tools"] == loaded_tools
    assert config["configurable"]["agent_name"] == "visual3d"
