import logging
import os
from typing import Any, Dict, List, Optional, Sequence, Type

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.subagents.rag.milvus_client import MilvusDB
from src.subagents.rag.retriever import Resource, Retriever

logger = logging.getLogger(__name__)


def build_file_ids_filter_expr(file_ids: Sequence[Any] | None = None) -> str:
    normalized_file_ids: list[str] = []
    seen: set[str] = set()

    for item in file_ids or []:
        file_id = str(item or "").strip()
        if not file_id or file_id in seen:
            continue
        normalized_file_ids.append(file_id)
        seen.add(file_id)

    if not normalized_file_ids:
        return ""

    quoted_file_ids = [f'"{file_id}"' for file_id in normalized_file_ids]
    return f"file_id in [{', '.join(quoted_file_ids)}]"


def _get_resource_value(
    resource: Resource | Dict[str, Any], key: str, default: Any = None
) -> Any:
    if isinstance(resource, dict):
        return resource.get(key, default)
    return getattr(resource, key, default)


def _normalize_agent_name(agent: Any) -> str:
    if isinstance(agent, str):
        return agent.strip().lower()
    if isinstance(agent, dict):
        for key in ("agent_type", "name", "type", "key", "id"):
            value = agent.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
    return ""


def _is_rag_resource(
    resource: Resource | Dict[str, Any], include_unbound: bool = True
) -> bool:
    agent_name = _normalize_agent_name(_get_resource_value(resource, "agent"))
    if not agent_name:
        agent_name = _normalize_agent_name(_get_resource_value(resource, "agent_type"))

    if agent_name == "rag":
        return True
    return include_unbound and not agent_name


def get_kb_files(
    resources: Optional[Sequence[Resource | Dict[str, Any]]] = None,
    searcher: Optional[MilvusDB] = None,
    resource_query: Optional[str] = None,
    include_unbound: bool = True,
) -> List[Dict[str, Any]]:
    """List files for rag-compatible resources grouped by collection.

    Returns a list like:
        [
            {
                "resource_uri": "...",
                "resource_title": "...",
                "resource_description": "...",
                "collection_name": "...",
                "files": [
                    {
                        "file_id": "...",
                        "file_name": "...",
                        "file_path": "...",
                        "update_time": "...",
                    }
                ],
            }
        ]

    This is useful when the caller needs to inspect which files exist in the
    current knowledge base, or count files under each rag collection.
    """
    if not resources:
        return []

    normalized_query = (resource_query or "").strip().lower()
    searcher = searcher or MilvusDB()

    kb_files: List[Dict[str, Any]] = []
    visited_collections: set[str] = set()

    for resource in resources:
        if not _is_rag_resource(resource, include_unbound=include_unbound):
            continue

        collection_name = str(_get_resource_value(resource, "uri", "") or "").strip()
        if not collection_name or collection_name in visited_collections:
            continue

        resource_title = str(_get_resource_value(resource, "title", "") or "").strip()
        resource_description = str(
            _get_resource_value(resource, "description", "") or ""
        ).strip()

        if normalized_query:
            searchable_text = " ".join(
                [collection_name, resource_title, resource_description]
            ).lower()
            if normalized_query not in searchable_text:
                continue

        kb_files.append(
            {
                "resource_uri": collection_name,
                "resource_title": resource_title,
                "resource_description": resource_description,
                "collection_name": collection_name,
                "files": searcher.list_collection_files(collection_name),
            }
        )
        visited_collections.add(collection_name)

    return kb_files


class GetKBFilesInput(BaseModel):
    resource_query: Optional[str] = Field(
        default=None,
        description=(
            "Optional substring filter for resource title, description or collection name."
            " Use it when the caller only wants file lists for part of the current"
            " rag resources."
        ),
    )


class KBFilesTool(BaseTool):
    name: str = "get_kb_files"
    description: str = (
        "Useful for listing which files exist in the current rag knowledge base,"
        " checking file coverage per collection, and counting files. Use this when"
        " the user asks questions like: which files are in the knowledge base,"
        " how many files are there, or what files exist under a specific resource"
        " or collection."
    )
    args_schema: Type[BaseModel] = GetKBFilesInput

    searcher: MilvusDB = Field(default_factory=MilvusDB)
    resources: List[Resource] = Field(default_factory=list)
    include_unbound: bool = True

    def _run(
        self,
        resource_query: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> List[Dict[str, Any]]:
        logger.info("Get kb files tool query: %s", resource_query)
        return get_kb_files(
            resources=self.resources,
            searcher=self.searcher,
            resource_query=resource_query,
            include_unbound=self.include_unbound,
        )

    async def _arun(
        self,
        resource_query: Optional[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> List[Dict[str, Any]]:
        return self._run(
            resource_query=resource_query,
            run_manager=run_manager.get_sync() if run_manager else None,
        )


def get_kb_files_tool(
    resources: List[Resource], include_unbound: bool = True
) -> KBFilesTool | None:
    """Create a tool for listing files under the current rag resources.

    The returned tool is intended for Neo/style agent execution, where
    `resources` are pre-bound by the runtime. Callers can optionally pass
    `resource_query` at invocation time to narrow the returned collections.
    """
    logger.info("create kb files tool")
    searcher = MilvusDB()

    if not searcher:
        return None

    return KBFilesTool(
        searcher=searcher,
        resources=resources,
        include_unbound=include_unbound,
    )


class MilvusAPIRetriever(Retriever):
    """Retriever implementation backed by a Milvus vector store."""

    def __init__(self) -> None:
        self.client = MilvusDB()

    def list_resources(self, query: Optional[str] = None) -> List[Resource]:
        # TODO: 还未实现
        pass

    def get_kb_files(
        self,
        resources: Optional[List[Resource]] = None,
        resource_query: Optional[str] = None,
        include_unbound: bool = True,
    ) -> List[Dict[str, Any]]:
        return get_kb_files(
            resources=resources,
            searcher=self.client,
            resource_query=resource_query,
            include_unbound=include_unbound,
        )

    def doc_search_by_file(
        self,
        query: str,
        collection_names: str | Sequence[str],
        file_ids: Sequence[Any],
        top_k: int = 10,
        threshold: float = 0.5,
        rerank_model: bool = False,
        **kwargs,
    ) -> List[Any]:
        if isinstance(collection_names, str):
            normalized_collection_names = [collection_names]
        else:
            normalized_collection_names = [
                str(name).strip() for name in collection_names if str(name).strip()
            ]

        if not normalized_collection_names:
            return []

        file_ids_expr = build_file_ids_filter_expr(file_ids)
        if not file_ids_expr:
            return []

        raw_expr = str(kwargs.pop("expr", "") or "").strip()
        merged_expr = raw_expr
        if raw_expr:
            merged_expr = f"({raw_expr}) AND ({file_ids_expr})"
        else:
            merged_expr = file_ids_expr

        if merged_expr:
            kwargs["expr"] = merged_expr

        return self.client.doc_search(
            query=query,
            collection_names=normalized_collection_names,
            top_k=top_k,
            threshold=threshold,
            rerank_model=rerank_model,
            **kwargs,
        )

    def query_relevant_documents(
        self, query: str, resources: Optional[List[Resource]] = None
    ) -> List[Any]:
        pages = []
        if not resources:
            return []

        chunk_results = self.client.doc_search(
            query,
            [resource.uri for resource in resources],
            top_k=5,
            threshold=0.2,
            rerank_model=True,
            # rerank_model=False,
        )
        if not chunk_results:
            return []

        title_params = []
        title_set = []
        for hit in chunk_results:
            title = hit.cur_title
            file_id = hit.file_id
            score = hit.score
            collection_name = hit.collection_name
            if title and file_id and (title not in title_set):
                title_set.append(title)
                title_params.append((score, title, file_id, collection_name))
        title_params = sorted(set(title_params), key=lambda x: x[0], reverse=True)

        for title_param in title_params:
            score = title_param[0]
            title = title_param[1]
            file_id = title_param[2]
            collection_name = title_param[3]
            page_results = self.client.list_chunks_by_title_fileid(
                collection_name, title, file_id
            )

            if not page_results:
                continue

            page_results = sorted(
                page_results, key=lambda x: x["chunk_id"], reverse=False
            )
            content = ""
            page_idx = []
            bbox = []
            for hit in page_results:
                if hit["bbox_type"] in ["image", "table", "video"]:
                    description = hit["content"]
                    chunk = {
                        "content_type": hit["bbox_type"],
                        "title": description,
                        "url": hit["media_path"].replace("http:","https:"),
                        "content": f"`![{description}]({hit['media_path']})`",
                        "source": hit["chunk_source"],
                    }
                    if hit["bbox_type"] == "table":
                        chunk["others"] = str(hit["others"])
                    pages.append(chunk)
                else:
                    content += hit["content"]
                    page_idx.append(hit["page_idx"])
                    bbox.append(hit["bbox"])

            if content:
                # filename = os.path.basename(hit["file_path"])
                pages.append(
                    {
                        "content_type": "text",
                        # "title": f"{filename}_{hit['title']}",
                        "title": f"{hit['title']}",
                        "url": hit["file_path"].replace("http:","https:"),
                        "content": content,
                        "score": score,
                        "source": hit["chunk_source"],
                        "metadata": {
                            "bbox": bbox,
                            "page_idx": page_idx,
                        },
                    }
                )
        return pages
