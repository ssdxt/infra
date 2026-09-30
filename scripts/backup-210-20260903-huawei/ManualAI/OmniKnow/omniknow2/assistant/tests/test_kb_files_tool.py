from src.subagents.rag.retriever import Resource
from src.tools.kb_files import KBFilesTool, get_kb_files


def test_get_kb_files_uses_exact_rag_resource_uri(monkeypatch):
    calls = []

    def fake_fetch(knowledgebase_uri: str, base_url: str, timeout: int = 10):
        calls.append(knowledgebase_uri)
        return [{"file_name": "compare.csv", "file_path": "/tmp/compare.csv"}]

    monkeypatch.setattr("src.tools.kb_files._fetch_kb_resource_files", fake_fetch)

    resources = [
        Resource(
            uri="tesla_manual_oss",
            title="特斯拉维修知识库",
            description="",
            agent="rag",
        ),
        Resource(
            uri="tesla_service_token",
            title="Tesla Service",
            description="特斯拉维修与服务数据库",
            agent="tabular",
        ),
    ]

    result = get_kb_files(resources=resources, resource_uri="tesla_manual_oss")

    assert calls == ["tesla_manual_oss"]
    assert result[0]["resource_uri"] == "tesla_manual_oss"
    assert result[0]["file_count"] == 1


def test_kb_files_tool_falls_back_to_only_rag_uri(monkeypatch):
    def fake_fetch(knowledgebase_uri: str, base_url: str, timeout: int = 10):
        assert knowledgebase_uri == "tesla_manual_oss"
        return [{"file_name": "compare.csv", "file_path": "/tmp/compare.csv"}]

    monkeypatch.setattr("src.tools.kb_files._fetch_kb_resource_files", fake_fetch)

    tool = KBFilesTool(
        resources=[
            Resource(
                uri="tesla_manual_oss",
                title="特斯拉维修知识库",
                description="",
                agent="rag",
            ),
            Resource(
                uri="tesla_service_token",
                title="Tesla Service",
                description="特斯拉维修与服务数据库",
                agent="tabular",
            ),
        ],
        include_unbound=False,
    )

    result = tool._run(resource_uri="compare.csv")

    assert result["status"] == "ok"
    assert result["resource_uri"] == "tesla_manual_oss"
    assert result["resource_uris"] == ["tesla_manual_oss"]
    assert result["kb_files"][0]["files"][0]["file_name"] == "compare.csv"


def test_kb_files_tool_stops_after_three_empty_attempts(monkeypatch):
    calls = []

    def fake_fetch(knowledgebase_uri: str, base_url: str, timeout: int = 10):
        calls.append(knowledgebase_uri)
        return []

    monkeypatch.setattr("src.tools.kb_files._fetch_kb_resource_files", fake_fetch)

    tool = KBFilesTool(
        resources=[
            Resource(
                uri="tesla_manual_oss",
                title="特斯拉维修知识库",
                description="",
                agent="rag",
            )
        ],
        include_unbound=False,
        max_empty_calls=3,
    )

    first = tool._run(resource_uri="tesla_manual_oss")
    second = tool._run(resource_uri="tesla_manual_oss")
    third = tool._run(resource_uri="tesla_manual_oss")
    fourth = tool._run(resource_uri="tesla_manual_oss")

    assert first["status"] == "not_found"
    assert first["final"] is False
    assert first["attempt"] == 1
    assert second["final"] is False
    assert second["attempt"] == 2
    assert third["final"] is True
    assert third["attempt"] == 3
    assert "treat it as not found" in third["message"]
    assert fourth["final"] is True
    assert fourth["attempt"] == 3
    assert len(calls) == 3
