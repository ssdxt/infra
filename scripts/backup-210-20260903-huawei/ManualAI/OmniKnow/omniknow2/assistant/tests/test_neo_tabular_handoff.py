import asyncio
from types import SimpleNamespace

from src.neo.nodes import (
    _build_scheduler_runtime_instruction,
    _build_subagent_runtime_instruction,
    _load_rag_tools,
    _load_tabular_tools,
)
from src.subagents.rag.retriever import Resource


def test_scheduler_runtime_instruction_routes_kb_table_files_to_tabular():
    instruction = _build_scheduler_runtime_instruction("zh-CN")

    assert "get_kb_files" in instruction
    assert "`tabular`" in instruction
    assert "`rag`" in instruction
    assert ".csv" in instruction
    assert "知识库有哪些文件" in instruction


def test_rag_runtime_instruction_allows_kb_file_listing():
    instruction = _build_subagent_runtime_instruction("rag", "zh-CN")

    assert "get_kb_files" in instruction
    assert "`tabular`" in instruction
    assert "知识库有哪些文件" in instruction
    assert "文档语义检索" in instruction


def test_load_rag_tools_mounts_get_kb_files(monkeypatch):
    kb_files_called = {"called": False}

    monkeypatch.setattr(
        "src.neo.nodes.get_retriever_tool",
        lambda resources: SimpleNamespace(name="local_search_tool"),
    )

    def fake_get_kb_files_tool(*args, **kwargs):
        kb_files_called["called"] = True
        return SimpleNamespace(name="get_kb_files")

    monkeypatch.setattr("src.neo.nodes.get_kb_files_tool", fake_get_kb_files_tool)

    tools = asyncio.run(
        _load_rag_tools(
            {
                "resources": [
                    Resource(
                        uri="rag://dataset/1",
                        title="知识库",
                        description="",
                        agent="rag",
                    )
                ]
            }
        )
    )

    assert [tool.name for tool in tools] == ["get_kb_files", "local_search_tool"]
    assert kb_files_called["called"] is True


def test_load_tabular_tools_mounts_get_kb_files_from_rag_resources(monkeypatch):
    captured = {}

    def fake_get_kb_files_tool(resources, include_unbound=False):
        captured["resources"] = resources
        captured["include_unbound"] = include_unbound
        return SimpleNamespace(name="get_kb_files")

    monkeypatch.setattr("src.neo.nodes.get_kb_files_tool", fake_get_kb_files_tool)
    monkeypatch.setattr("src.neo.nodes.get_sql_toolkit", lambda resources: [])

    tools = asyncio.run(
        _load_tabular_tools(
            {
                "resources": [
                    Resource(
                        uri="rag://dataset/1",
                        title="知识库",
                        description="",
                        agent="rag",
                    )
                ]
            }
        )
    )

    assert any(getattr(tool, "name", "") == "get_kb_files" for tool in tools)
    assert captured["include_unbound"] is False
    assert [resource.uri for resource in captured["resources"]] == ["rag://dataset/1"]
