import logging
from pathlib import Path
from typing import Any, Optional, Type

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr

from src.subagents.rag.milvus_rag import MilvusAPIRetriever

logger = logging.getLogger(__name__)

DEFAULT_TOP_K = 8
DEFAULT_THRESHOLD = 0.2
MAX_TOOL_CONTEXT_CHARS = 7000
MAX_HIT_CHARS = 900


class QuestKBSearchToolInput(BaseModel):
    query: str = Field(..., description="用户在指定知识库文件范围内的问题")


class QuestKBSearchTool(BaseTool):
    name: str = "quest_kb_search"
    description: str = (
        "Search knowledge from the preselected collection and file_ids only. "
        "Always use this tool before answering knowledge-base questions."
    )
    args_schema: Type[BaseModel] = QuestKBSearchToolInput

    retriever: MilvusAPIRetriever = Field(default_factory=MilvusAPIRetriever)
    collection_name: str = Field(..., description="目标知识库 collection")
    file_ids: list[str] = Field(default_factory=list, description="允许检索的文件 ID")
    history_text: str = Field(default="", description="最近几轮对话历史，仅用于承接上下文")
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=20)
    threshold: float = Field(default=DEFAULT_THRESHOLD, ge=0.0, le=1.0)

    _last_hits: list[Any] = PrivateAttr(default_factory=list)

    @property
    def last_hits(self) -> list[Any]:
        return list(self._last_hits)

    def search(self, query: str) -> str:
        logger.info(
            "Quest KB tool query: collection=%s file_ids=%s query=%s",
            self.collection_name,
            self.file_ids,
            query,
        )
        search_query = self._build_search_query(query)
        results = self.retriever.doc_search_by_file(
            query=search_query,
            collection_names=[self.collection_name],
            file_ids=self.file_ids,
            top_k=self.top_k,
            threshold=self.threshold,
            rerank_model=True,
        )

        allowed_file_ids = set(self.file_ids)
        self._last_hits = [
            hit
            for hit in (results or [])
            if str(getattr(hit, "file_id", "") or "").strip() in allowed_file_ids
        ]

        if not self._last_hits:
            return (
                "No relevant knowledge was found in the selected files. "
                "Do not fabricate an answer."
            )

        return self.format_hits(self._last_hits)

    def format_hits(self, hits: Optional[list[Any]] = None) -> str:
        selected_hits = hits if hits is not None else self._last_hits
        if not selected_hits:
            return (
                "No relevant knowledge was found in the selected files. "
                "Do not fabricate an answer."
            )

        sections = [
            (
                "The following knowledge snippets are retrieved only from the "
                f"selected files in collection `{self.collection_name}`."
            )
        ]
        current_length = len(sections[0])

        for index, hit in enumerate(selected_hits, start=1):
            title = self._resolve_title(hit)
            file_id = str(getattr(hit, "file_id", "") or "").strip()
            file_name = self._resolve_file_name(hit)
            chunk_id = str(getattr(hit, "chunk_id", "") or "").strip()
            score = float(getattr(hit, "score", 0.0) or 0.0)
            page_idx = self._format_page_idx(getattr(hit, "page_idx", []))
            content = self._trim_text(str(getattr(hit, "content", "") or "").strip())

            if not content:
                continue

            section = (
                f"[{index}] file_id={file_id}; file_name={file_name}; "
                f"title={title}; chunk_id={chunk_id}; score={score:.4f}; "
                f"page_idx={page_idx}\n{content}"
            )
            section_length = len(section) + 2
            if sections and current_length + section_length > MAX_TOOL_CONTEXT_CHARS:
                break

            sections.append(section)
            current_length += section_length

        return "\n\n".join(sections).strip()

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return self.search(query)

    async def _arun(
        self,
        query: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        return self.search(query)

    def _resolve_title(self, hit: Any) -> str:
        for attr_name in ("cur_title", "title", "par_title"):
            value = str(getattr(hit, attr_name, "") or "").strip()
            if value:
                return value
        return "未命名标题"

    def _resolve_file_name(self, hit: Any) -> str:
        file_path = str(getattr(hit, "file_path", "") or "").strip()
        if file_path:
            return Path(file_path).name or file_path
        file_id = str(getattr(hit, "file_id", "") or "").strip()
        return file_id or "unknown"

    def _format_page_idx(self, value: Any) -> str:
        normalized_pages: list[int] = []

        def visit(item: Any) -> None:
            if isinstance(item, list):
                for child in item:
                    visit(child)
                return

            if isinstance(item, (int, float)):
                page = int(item)
                if page not in normalized_pages:
                    normalized_pages.append(page)
                return

            item_text = str(item or "").strip()
            if item_text.isdigit():
                page = int(item_text)
                if page not in normalized_pages:
                    normalized_pages.append(page)

        visit(value)

        if not normalized_pages:
            return "[]"
        return "[" + ", ".join(str(page) for page in normalized_pages[:10]) + "]"

    def _trim_text(self, value: str) -> str:
        if len(value) <= MAX_HIT_CHARS:
            return value
        return value[:MAX_HIT_CHARS].rstrip()

    def _build_search_query(self, query: str) -> str:
        history_text = str(self.history_text or "").strip()
        normalized_query = str(query or "").strip()
        if not history_text:
            return normalized_query
        return f"{history_text}\n当前问题：{normalized_query}"
