from types import SimpleNamespace

from src.quest.chat_tool import QuestKBSearchTool
from src.quest.schemas import QuestChatRequest
from src.quest.service import QUEST_CHAT_NO_RESULT_MESSAGE, QuestService
from src.subagents.rag.milvus_rag import (
    MilvusAPIRetriever,
    build_file_ids_filter_expr,
)


def test_build_file_ids_filter_expr_deduplicates_values():
    expr = build_file_ids_filter_expr(["file-1", " file-2 ", "file-1", "", None])

    assert expr == 'file_id in ["file-1", "file-2"]'


def test_quest_chat_request_defaults_thread_id():
    request = QuestChatRequest(
        collection_name="demo_kb",
        file_ids=["file-1"],
        query="请回答问题",
    )

    assert request.thread_id == "__default__"


def test_milvus_api_retriever_doc_search_by_file_builds_expr():
    retriever = MilvusAPIRetriever.__new__(MilvusAPIRetriever)
    captured: dict[str, object] = {}

    class FakeClient:
        def doc_search(self, **kwargs):
            captured.update(kwargs)
            return ["ok"]

    retriever.client = FakeClient()

    result = retriever.doc_search_by_file(
        query="变压器的作用",
        collection_names="demo_kb",
        file_ids=["file-1", "file-2"],
        top_k=5,
        threshold=0.2,
        rerank_model=True,
        expr='chunk_source == "document"',
    )

    assert result == ["ok"]
    assert captured["collection_names"] == ["demo_kb"]
    assert (
        captured["expr"]
        == '(chunk_source == "document") AND (file_id in ["file-1", "file-2"])'
    )


def test_quest_kb_search_tool_uses_bound_file_ids():
    retriever = MilvusAPIRetriever.__new__(MilvusAPIRetriever)
    captured: dict[str, object] = {}

    def fake_doc_search_by_file(**kwargs):
        captured.update(kwargs)
        return [
            SimpleNamespace(
                chunk_id="chunk-1",
                file_id="file-1",
                file_path="/tmp/book-a.pdf",
                cur_title="第一章",
                title="第一章",
                par_title="",
                score=0.91,
                page_idx=[1, 2],
                content="这是命中的知识片段。",
            )
        ]

    retriever.doc_search_by_file = fake_doc_search_by_file
    tool = QuestKBSearchTool(
        retriever=retriever,
        collection_name="demo_kb",
        file_ids=["file-1"],
        history_text="最近对话历史（仅用于承接上下文，不可替代知识库依据）：\n用户：上一轮问了背景",
    )

    output = tool.search("这里讲了什么")

    assert captured["file_ids"] == ["file-1"]
    assert "上一轮问了背景" in captured["query"]
    assert "当前问题：这里讲了什么" in captured["query"]
    assert tool.last_hits[0].chunk_id == "chunk-1"
    assert "chunk_id=chunk-1" in output
    assert "book-a.pdf" in output


def test_quest_service_chat_builds_response_from_agent_hits(monkeypatch):
    retriever = MilvusAPIRetriever.__new__(MilvusAPIRetriever)
    service = QuestService(retriever=retriever)

    fake_hit = SimpleNamespace(
        chunk_id="chunk-1",
        file_id="file-1",
        file_path="/tmp/book-a.pdf",
        cur_title="第一章",
        title="第一章",
        par_title="",
        score=0.95,
        page_idx=[3],
        content="答案相关片段",
    )

    def fake_run_agent(self, query, tool):
        tool._last_hits = [fake_hit]
        return "这是基于知识库的回答。"

    monkeypatch.setattr(QuestService, "_run_quest_chat_agent", fake_run_agent)

    response = service.chat(
        QuestChatRequest(
            collection_name="demo_kb",
            file_ids=["file-1"],
            query="请总结这一章",
        )
    )

    assert response.answer == "这是基于知识库的回答。"
    assert len(response.references) == 1
    assert response.references[0].chunk_id == "chunk-1"
    assert response.references[0].file_name == "book-a.pdf"


def test_quest_service_chat_returns_no_result_message_when_nothing_found(monkeypatch):
    retriever = MilvusAPIRetriever.__new__(MilvusAPIRetriever)
    service = QuestService(retriever=retriever)

    monkeypatch.setattr(QuestService, "_run_quest_chat_agent", lambda *args, **kwargs: "")
    monkeypatch.setattr(QuestKBSearchTool, "search", lambda self, query: "No result")

    response = service.chat(
        QuestChatRequest(
            collection_name="demo_kb",
            file_ids=["file-1"],
            query="请回答问题",
        )
    )

    assert response.answer == QUEST_CHAT_NO_RESULT_MESSAGE
    assert response.references == []


def test_quest_service_remembers_recent_turns():
    retriever = MilvusAPIRetriever.__new__(MilvusAPIRetriever)
    service = QuestService(retriever=retriever)

    service.remember_chat_turn("thread-1", "第一问", "第一答")
    service.remember_chat_turn("thread-1", "第二问", "第二答")

    history_text = service._build_recent_history_text("thread-1")

    assert "用户：第一问" in history_text
    assert "助手：第一答" in history_text
    assert "用户：第二问" in history_text
    assert "助手：第二答" in history_text
