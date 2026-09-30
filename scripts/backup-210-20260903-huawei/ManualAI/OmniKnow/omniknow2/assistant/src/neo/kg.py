import hashlib
import json
import logging
from typing import Any, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

from src.config.agents import AGENT_LLM_MAP
from src.llms.llm import get_llm_by_type
from src.subagents.rag.milvus_client import MilvusDB
from src.subagents.rag.retriever import Resource
from src.utils.json_utils import repair_json_output

logger = logging.getLogger(__name__)


DEFAULT_LLM_DOCUMENT_BATCH_SIZE = 10


KG_REFINEMENT_PROMPT = """
你是知识库图谱迭代完善助手。基础图谱已经由程序预生成，包含中心 resource 节点、document 节点、title 节点和全部 title_mappings。

你每次只会收到一小批 documents 的 titles。请只基于这一批标题，补充概念节点和语义关系，用来完善已有图谱。

输出必须是严格 JSON，不要输出 Markdown、解释或代码块。

JSON 顶层结构：
{
  "nodes": [
    {
      "id": "节点 ID，必须稳定且唯一",
      "label": "节点名称",
      "type": "concept",
      "description": "简短描述，可为空"
    }
  ],
  "edges": [
    {
      "source": "源节点 ID",
      "target": "目标节点 ID",
      "type": "related_to|parent_of",
      "description": "关系说明，可为空"
    }
  ],
  "title_mappings": []
}

要求：
1. 不要生成 resource/document/title 节点，它们已经存在。
2. 不要生成 contains/has_title 边，它们已经存在。
3. 可以新增 concept 节点，也可以复用输入 existing_concepts 中已有 concept 节点。
4. 新增 concept 节点的 id 用 `concept_` 前缀，尽量稳定且语义清晰。
5. 关系的 source/target 必须使用输入里已经存在的 node id，或你本次 nodes 中新增的 concept id。
6. `title_mappings` 必须返回空数组。
7. 中心节点永远是输入 center_node_label 对应的 resource 节点，不要改动它。
8. 不要输出 uri、file_path、collection_name、file_id、agent、is_center 等与概念无关的字段。
"""


class KGTitle(BaseModel):
    collection_name: str = ""
    file_id: str = ""
    file_name: str = ""
    file_path: str = ""
    title: str = ""
    node_id: str = ""


class KGDocument(BaseModel):
    collection_name: str = ""
    file_id: str = ""
    file_name: str = ""
    file_path: str = ""
    update_time: str = ""
    titles: list[KGTitle] = Field(default_factory=list)


class KGNode(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    label: str
    type: str = "concept"
    description: str = ""
    collection_name: str = ""
    file_id: str = ""
    title: str = ""
    is_center: bool = False


class KGEdge(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str
    target: str
    type: str = "related_to"
    description: str = ""


class KGTitleMapping(BaseModel):
    collection_name: str = ""
    file_id: str = ""
    title: str
    node_id: str


class KnowledgeGraph(BaseModel):
    nodes: list[KGNode] = Field(default_factory=list)
    edges: list[KGEdge] = Field(default_factory=list)
    title_mappings: list[KGTitleMapping] = Field(default_factory=list)
    documents: list[KGDocument] = Field(default_factory=list)
    center_node_id: str = ""
    center_node_label: str = ""


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "\n".join(str(part or "") for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _stable_slug(value: Any) -> str:
    raw = str(value or "").strip()
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return digest


def _normalize_title(value: Any) -> str:
    return str(value or "").strip()


def _get_resource_value(resource: Resource | dict[str, Any], key: str) -> Any:
    if isinstance(resource, dict):
        return resource.get(key)
    return getattr(resource, key, None)


def _resource_collection_name(resource: Resource | dict[str, Any]) -> str:
    return str(_get_resource_value(resource, "uri") or "").strip()


def _resource_title(resource: Resource | dict[str, Any]) -> str:
    return str(_get_resource_value(resource, "title") or "").strip()


def _resource_description(resource: Resource | dict[str, Any]) -> str:
    return str(_get_resource_value(resource, "description") or "").strip()


def _resource_prompt_payload(resource: Resource | dict[str, Any]) -> dict[str, Any]:
    return {
        "title": _resource_title(resource),
        "description": _resource_description(resource),
    }


def _dedupe_titles(
    raw_titles: Sequence[dict[str, Any]],
    document: dict[str, Any],
) -> list[KGTitle]:
    titles: list[KGTitle] = []
    seen: set[str] = set()
    collection_name = str(document.get("collection_name") or "")
    file_id = str(document.get("file_id") or "")
    file_name = str(document.get("file_name") or "")
    file_path = str(document.get("file_path") or "")

    for item in raw_titles:
        title = _normalize_title(item.get("cur_title") or item.get("title"))
        if not title or title in seen:
            continue
        seen.add(title)
        titles.append(
            KGTitle(
                collection_name=collection_name,
                file_id=file_id,
                file_name=file_name,
                file_path=file_path,
                title=title,
                node_id=_stable_id("title", collection_name, file_id, title),
            )
        )

    titles.sort(key=lambda item: item.title)
    return titles


def list_kb_documents_and_titles(
    resource: Resource | dict[str, Any],
    searcher: MilvusDB | None = None,
) -> list[KGDocument]:
    """List all documents and unique current titles for one rag resource.

    The title source is the Milvus `cur_title` field, grouped by collection and
    file. The returned title objects already contain stable graph node IDs so
    the LLM can preserve deterministic mappings.
    """
    collection_name = _resource_collection_name(resource)
    if not collection_name:
        return []

    searcher = searcher or MilvusDB()
    files = searcher.list_collection_files(collection_name)

    documents: list[KGDocument] = []
    for file_item in files or []:
        file_id = str(file_item.get("file_id") or "").strip()
        if not file_id:
            continue

        document_payload = {
            "collection_name": collection_name,
            "file_id": file_id,
            "file_name": str(file_item.get("file_name") or ""),
            "file_path": str(file_item.get("file_path") or ""),
            "update_time": str(file_item.get("update_time") or ""),
        }
        raw_titles = searcher.list_curtitle_by_fileid(collection_name, [file_id])
        documents.append(
            KGDocument(
                **document_payload,
                titles=_dedupe_titles(raw_titles, document_payload),
            )
        )

    documents.sort(
        key=lambda item: (item.collection_name, item.file_name, item.file_id)
    )
    return documents


def _document_batch_prompt_payload(
    graph: KnowledgeGraph,
    resource: Resource | dict[str, Any],
    documents: Sequence[KGDocument],
    batch_index: int,
    batch_count: int,
) -> dict[str, Any]:
    existing_concepts = [
        {
            "id": node.id,
            "label": node.label,
            "description": node.description,
        }
        for node in graph.nodes
        if node.type == "concept"
    ]
    existing_concepts.sort(key=lambda item: (item["label"], item["id"]))

    return {
        "resource": _resource_prompt_payload(resource),
        "center_node_id": graph.center_node_id,
        "center_node_label": graph.center_node_label,
        "batch": {
            "index": batch_index,
            "count": batch_count,
            "document_count": len(documents),
        },
        "existing_concepts": existing_concepts[:200],
        "documents": [
            {
                "document_node_id": _stable_id(
                    "document", document.collection_name, document.file_id
                ),
                "titles": [
                    {
                        "title_node_id": title.node_id,
                        "title": title.title,
                    }
                    for title in document.titles
                ],
            }
            for document in documents
        ],
    }


def _iter_document_batches(
    documents: Sequence[KGDocument],
    batch_size: int = DEFAULT_LLM_DOCUMENT_BATCH_SIZE,
) -> list[list[KGDocument]]:
    normalized_batch_size = max(
        int(batch_size or DEFAULT_LLM_DOCUMENT_BATCH_SIZE),
        1,
    )
    return [
        list(documents[index : index + normalized_batch_size])
        for index in range(0, len(documents), normalized_batch_size)
    ]


def _load_graph_from_llm_response(content: Any) -> KnowledgeGraph:
    raw = str(content or "").strip()
    if not raw:
        return KnowledgeGraph()

    try:
        repaired = repair_json_output(raw)
        payload = json.loads(repaired)
        if not isinstance(payload, dict):
            return KnowledgeGraph()
        return KnowledgeGraph.model_validate(payload)
    except Exception as exc:
        logger.warning("Failed to parse knowledge graph JSON from LLM: %s", exc)
        return KnowledgeGraph()


def _normalize_llm_concept_updates(update: KnowledgeGraph) -> KnowledgeGraph:
    id_map: dict[str, str] = {}
    normalized_nodes: list[KGNode] = []
    seen_node_ids: set[str] = set()

    for node in update.nodes:
        if node.type and node.type != "concept":
            continue

        label = str(node.label or "").strip()
        if not label:
            continue

        normalized_id = str(node.id or "").strip()
        if not normalized_id.startswith("concept_"):
            normalized_id = f"concept_{_stable_slug(label)}"

        id_map[node.id] = normalized_id
        if normalized_id in seen_node_ids:
            continue

        seen_node_ids.add(normalized_id)
        normalized_nodes.append(
            KGNode(
                id=normalized_id,
                label=label,
                type="concept",
                description=node.description,
                is_center=False,
            )
        )

    normalized_edges: list[KGEdge] = []
    seen_edge_keys: set[tuple[str, str, str]] = set()
    for edge in update.edges:
        edge_type = (
            edge.type if edge.type in {"related_to", "parent_of"} else "related_to"
        )
        source = id_map.get(edge.source, edge.source)
        target = id_map.get(edge.target, edge.target)
        if not source or not target or source == target:
            continue

        edge_key = (source, target, edge_type)
        if edge_key in seen_edge_keys:
            continue

        seen_edge_keys.add(edge_key)
        normalized_edges.append(
            KGEdge(
                source=source,
                target=target,
                type=edge_type,
                description=edge.description,
            )
        )

    return KnowledgeGraph(nodes=normalized_nodes, edges=normalized_edges)


def _merge_graph_update(
    base_graph: KnowledgeGraph,
    update: KnowledgeGraph,
) -> KnowledgeGraph:
    update = _normalize_llm_concept_updates(update)
    node_by_id = {node.id: node for node in base_graph.nodes if node.id}

    for node in update.nodes:
        existing = node_by_id.get(node.id)
        if existing:
            if existing.type == "concept":
                existing.label = existing.label or node.label
                existing.description = existing.description or node.description
            continue
        node_by_id[node.id] = node

    valid_node_ids = set(node_by_id)
    edge_keys = {(edge.source, edge.target, edge.type) for edge in base_graph.edges}
    for edge in update.edges:
        if edge.source not in valid_node_ids or edge.target not in valid_node_ids:
            continue
        _append_edge_once(base_graph.edges, edge, edge_keys)

    base_graph.nodes = list(node_by_id.values())
    return base_graph


def _append_edge_once(
    edges: list[KGEdge],
    edge: KGEdge,
    seen: set[tuple[str, str, str]],
) -> None:
    key = (edge.source, edge.target, edge.type)
    if key in seen:
        return
    seen.add(key)
    edges.append(edge)


def _complete_graph_coverage(
    graph: KnowledgeGraph,
    resource: Resource | dict[str, Any],
    documents: Sequence[KGDocument],
) -> KnowledgeGraph:
    """Deterministically add missing resource/document/title coverage."""
    node_by_id = {node.id: node for node in graph.nodes if node.id}
    edge_keys = {(edge.source, edge.target, edge.type) for edge in graph.edges}
    collection_name = _resource_collection_name(resource)
    center_node_id = _stable_id("resource", collection_name)
    center_node_label = _resource_title(resource) or collection_name

    for node in node_by_id.values():
        node.is_center = False

    if center_node_id not in node_by_id:
        node_by_id[center_node_id] = KGNode(
            id=center_node_id,
            label=center_node_label,
            type="resource",
            description=_resource_description(resource),
            collection_name=collection_name,
            is_center=True,
        )
    else:
        node_by_id[center_node_id].type = "resource"
        node_by_id[center_node_id].label = center_node_label
        node_by_id[center_node_id].description = (
            node_by_id[center_node_id].description
            or _resource_description(resource)
        )
        node_by_id[center_node_id].collection_name = collection_name
        node_by_id[center_node_id].is_center = True

    graph.center_node_id = center_node_id
    graph.center_node_label = center_node_label

    expected_mapping_keys: set[tuple[str, str, str]] = set()
    for document in documents:
        for title in document.titles:
            expected_mapping_keys.add(
                (title.collection_name, title.file_id, title.title)
            )

    graph.title_mappings = [
        mapping
        for mapping in graph.title_mappings
        if (mapping.collection_name, mapping.file_id, mapping.title)
        not in expected_mapping_keys
    ]
    mapping_keys = {
        (mapping.collection_name, mapping.file_id, mapping.title)
        for mapping in graph.title_mappings
    }

    for document in documents:
        resource_id = center_node_id
        document_id = _stable_id(
            "document",
            document.collection_name,
            document.file_id,
        )

        if document_id not in node_by_id:
            node_by_id[document_id] = KGNode(
                id=document_id,
                label=document.file_name or document.file_id,
                type="document",
                collection_name=document.collection_name,
                file_id=document.file_id,
                description=document.file_path,
            )

        _append_edge_once(
            graph.edges,
            KGEdge(source=resource_id, target=document_id, type="contains"),
            edge_keys,
        )

        for title in document.titles:
            if title.node_id not in node_by_id:
                node_by_id[title.node_id] = KGNode(
                    id=title.node_id,
                    label=title.title,
                    type="title",
                    collection_name=title.collection_name,
                    file_id=title.file_id,
                    title=title.title,
                )
            else:
                node_by_id[title.node_id].type = "title"
                node_by_id[title.node_id].label = (
                    node_by_id[title.node_id].label or title.title
                )
                node_by_id[title.node_id].collection_name = title.collection_name
                node_by_id[title.node_id].file_id = title.file_id
                node_by_id[title.node_id].title = title.title

            _append_edge_once(
                graph.edges,
                KGEdge(source=document_id, target=title.node_id, type="has_title"),
                edge_keys,
            )

            mapping_key = (title.collection_name, title.file_id, title.title)
            if mapping_key in mapping_keys:
                continue

            graph.title_mappings.append(
                KGTitleMapping(
                    collection_name=title.collection_name,
                    file_id=title.file_id,
                    title=title.title,
                    node_id=title.node_id,
                )
            )
            mapping_keys.add(mapping_key)

    graph.nodes = sorted(
        node_by_id.values(),
        key=lambda item: (item.type, item.label, item.id),
    )
    graph.edges = sorted(
        graph.edges,
        key=lambda item: (item.source, item.target, item.type),
    )
    graph.title_mappings = sorted(
        graph.title_mappings,
        key=lambda item: (item.collection_name, item.file_id, item.title),
    )
    graph.documents = list(documents)
    return graph


def generate_knowledge_graph(
    resource: Resource | dict[str, Any],
    searcher: MilvusDB | None = None,
    llm: BaseChatModel | None = None,
    use_llm: bool = True,
    llm_document_batch_size: int = DEFAULT_LLM_DOCUMENT_BATCH_SIZE,
) -> dict[str, Any]:
    """Generate a knowledge graph JSON from one rag resource.

    The graph is pre-generated deterministically first. The LLM then iterates
    through document batches to add concept nodes and semantic relations.
    """
    documents = list_kb_documents_and_titles(
        resource=resource,
        searcher=searcher,
    )

    graph = _complete_graph_coverage(KnowledgeGraph(), resource, documents)
    if use_llm and documents:
        llm = llm or get_llm_by_type(AGENT_LLM_MAP["summarize"])
        document_batches = _iter_document_batches(documents, llm_document_batch_size)
        batch_count = len(document_batches)

        for batch_index, document_batch in enumerate(document_batches, start=1):
            prompt_payload = _document_batch_prompt_payload(
                graph=graph,
                resource=resource,
                documents=document_batch,
                batch_index=batch_index,
                batch_count=batch_count,
            )
            try:
                response = llm.invoke(
                    [
                        SystemMessage(content=KG_REFINEMENT_PROMPT),
                        HumanMessage(
                            content=json.dumps(
                                prompt_payload,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                        ),
                    ]
                )
                update = _load_graph_from_llm_response(
                    getattr(response, "content", response)
                )
            except Exception as exc:
                logger.warning(
                    "Knowledge graph refinement batch %s/%s failed: %s",
                    batch_index,
                    batch_count,
                    exc,
                )
                continue

            graph = _merge_graph_update(graph, update)
            graph = _complete_graph_coverage(graph, resource, documents)

    graph = _complete_graph_coverage(graph, resource, documents)
    return graph.model_dump(mode="json", exclude_none=True)


__all__ = [
    "KGDocument",
    "KGEdge",
    "KGNode",
    "KGTitle",
    "KGTitleMapping",
    "KnowledgeGraph",
    "generate_knowledge_graph",
    "list_kb_documents_and_titles",
]
