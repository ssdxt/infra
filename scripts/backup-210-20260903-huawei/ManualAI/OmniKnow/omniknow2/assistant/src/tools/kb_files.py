import logging
import os
from typing import Any, Dict, List, Optional, Sequence, Type
from urllib.parse import quote

import requests
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, PrivateAttr

from src.subagents.rag.retriever import Resource

logger = logging.getLogger(__name__)

DEFAULT_KB_API_BASE_URL = os.getenv(
    "KB_RESOURCES_API_BASE_URL", "http://ai_server:8375"
).rstrip("/")


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


def _extract_file_items(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in ("data", "resources", "files", "items", "list", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = _extract_file_items(value)
                if nested:
                    return nested

    return []


def _collect_rag_resources(
    resources: Optional[Sequence[Resource | Dict[str, Any]]] = None,
    include_unbound: bool = True,
) -> List[Resource | Dict[str, Any]]:
    rag_resources: List[Resource | Dict[str, Any]] = []
    visited_uris: set[str] = set()

    for resource in resources or []:
        if not _is_rag_resource(resource, include_unbound=include_unbound):
            continue

        resource_uri = str(_get_resource_value(resource, "uri", "") or "").strip()
        if not resource_uri or resource_uri in visited_uris:
            continue

        rag_resources.append(resource)
        visited_uris.add(resource_uri)

    return rag_resources


def _resolve_kb_resources(
    resources: Optional[Sequence[Resource | Dict[str, Any]]] = None,
    resource_uri: Optional[str] = None,
    include_unbound: bool = True,
) -> tuple[
    List[Resource | Dict[str, Any]],
    List[str],
    List[str],
    Optional[str],
]:
    rag_resources = _collect_rag_resources(resources, include_unbound=include_unbound)
    allowed_resource_uris = [
        str(_get_resource_value(resource, "uri", "") or "").strip()
        for resource in rag_resources
    ]
    normalized_resource_uri = str(resource_uri or "").strip()

    if not normalized_resource_uri:
        if len(rag_resources) == 1:
            fallback_uri = allowed_resource_uris[0]
            return (
                rag_resources,
                allowed_resource_uris,
                [fallback_uri],
                (
                    "No resource_uri was provided. "
                    f"Using the only available rag resource uri '{fallback_uri}'."
                ),
            )
        return (
            [],
            allowed_resource_uris,
            [],
            (
                "resource_uri is required. "
                "It must be an exact uri from the current resources with agent=rag."
            ),
        )

    matched_resources = [
        resource
        for resource in rag_resources
        if str(_get_resource_value(resource, "uri", "") or "").strip()
        == normalized_resource_uri
    ]
    if matched_resources:
        return (
            matched_resources,
            allowed_resource_uris,
            [normalized_resource_uri],
            None,
        )

    if len(rag_resources) == 1:
        fallback_uri = allowed_resource_uris[0]
        logger.warning(
            "Get kb files received invalid resource_uri '%s'; falling back to sole rag resource '%s'",
            normalized_resource_uri,
            fallback_uri,
        )
        return (
            rag_resources,
            allowed_resource_uris,
            [fallback_uri],
            (
                "The provided value was not a rag resource uri. "
                f"Using the only available rag resource uri '{fallback_uri}' instead."
            ),
        )

    return (
        [],
        allowed_resource_uris,
        [],
        (
            "Invalid resource_uri. "
            "The value must be an exact uri from the current resources with agent=rag."
        ),
    )


def _normalize_file_items(payload: Any) -> List[Dict[str, str]]:
    files: List[Dict[str, str]] = []
    for item in _extract_file_items(payload):
        file_path = str(
            item.get("file_path")
            or item.get("filePath")
            or item.get("path")
            or item.get("url")
            or ""
        ).strip()
        file_name = str(
            item.get("file_name")
            or item.get("fileName")
            or item.get("name")
            or item.get("title")
            or ""
        ).strip()

        if not file_name and file_path:
            file_name = os.path.basename(file_path.rstrip("/"))

        if not file_name and not file_path:
            continue

        files.append({"file_name": file_name, "file_path": file_path})

    return files


def _fetch_kb_resource_files(
    knowledgebase_uri: str,
    base_url: str = DEFAULT_KB_API_BASE_URL,
    timeout: int = 10,
) -> List[Dict[str, str]]:
    encoded_uri = quote(knowledgebase_uri, safe="")
    url = f"{base_url}/api/v1/kbs/{encoded_uri}/resources"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, dict) and "code" in payload:
        api_code = payload.get("code")
        if api_code != 200:
            raise ValueError(
                f"KB resources API returned code {api_code}:"
                f" {payload.get('message', 'unknown error')}"
            )

        return _normalize_file_items(payload.get("data", []))

    return _normalize_file_items(payload)


def get_kb_files(
    resources: Optional[Sequence[Resource | Dict[str, Any]]] = None,
    resource_uri: Optional[str] = None,
    include_unbound: bool = True,
    base_url: str = DEFAULT_KB_API_BASE_URL,
) -> List[Dict[str, Any]]:
    """List files for rag-compatible knowledge bases via the KB resources API."""
    if not resources:
        return []

    resolved_resources, _, _, _ = _resolve_kb_resources(
        resources=resources,
        resource_uri=resource_uri,
        include_unbound=include_unbound,
    )
    if not resolved_resources:
        return []

    kb_files: List[Dict[str, Any]] = []
    visited_kbs: set[str] = set()

    for resource in resolved_resources:
        knowledgebase_uri = str(_get_resource_value(resource, "uri", "") or "").strip()
        if not knowledgebase_uri or knowledgebase_uri in visited_kbs:
            continue

        resource_title = str(_get_resource_value(resource, "title", "") or "").strip()
        resource_description = str(
            _get_resource_value(resource, "description", "") or ""
        ).strip()

        record: Dict[str, Any] = {
            "resource_uri": knowledgebase_uri,
            "resource_title": resource_title,
            "resource_description": resource_description,
            "collection_name": knowledgebase_uri,
            "files": [],
            "file_count": 0,
        }

        try:
            record["files"] = _fetch_kb_resource_files(
                knowledgebase_uri=knowledgebase_uri,
                base_url=base_url,
            )
            record["file_count"] = len(record["files"])
        except requests.RequestException as exc:
            logger.warning(
                "Failed to fetch kb files for knowledge base '%s': %s",
                knowledgebase_uri,
                exc,
            )
            record["error"] = str(exc)
        except ValueError as exc:
            logger.warning(
                "Failed to parse kb files response for knowledge base '%s': %s",
                knowledgebase_uri,
                exc,
            )
            record["error"] = str(exc)

        kb_files.append(record)
        visited_kbs.add(knowledgebase_uri)

    return kb_files


class GetKBFilesInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    resource_uri: Optional[str] = Field(
        default=None,
        description=(
            "Exact uri of one current knowledge-base resource bound to agent=rag."
            " This value must come from the current Resources list. Never pass a"
            " file name like compare.csv."
        ),
        validation_alias=AliasChoices("resource_uri", "resource_query"),
    )


class KBFilesTool(BaseTool):
    name: str = "get_kb_files"
    description: str = (
        "Useful for listing which files exist in the current rag knowledge base,"
        " checking file coverage per knowledge base, and counting files. Use this"
        " when the user asks which files are in the knowledge base, how many files"
        " there are, or what files exist under a specific resource."
    )
    args_schema: Type[BaseModel] = GetKBFilesInput

    resources: List[Resource] = Field(default_factory=list)
    include_unbound: bool = True
    base_url: str = DEFAULT_KB_API_BASE_URL
    max_empty_calls: int = 3
    _empty_call_counts: Dict[str, int] = PrivateAttr(default_factory=dict)

    def _increment_empty_calls(self, attempt_key: str) -> int:
        attempts = self._empty_call_counts.get(attempt_key, 0) + 1
        self._empty_call_counts[attempt_key] = attempts
        return attempts

    def _reset_empty_calls(self, attempt_key: str) -> None:
        if attempt_key in self._empty_call_counts:
            del self._empty_call_counts[attempt_key]

    def _build_final_not_found_response(
        self,
        attempt_key: str,
        resource_uri: Optional[str],
        queried_resource_uris: List[str],
        allowed_resource_uris: List[str],
        message: str,
    ) -> Dict[str, Any]:
        attempts = self._empty_call_counts.get(attempt_key, self.max_empty_calls)
        return {
            "status": "not_found",
            "resource_uri": resource_uri,
            "resource_uris": queried_resource_uris,
            "allowed_resource_uris": allowed_resource_uris,
            "attempt": attempts,
            "max_attempts": self.max_empty_calls,
            "final": True,
            "message": (
                f"{message} Stop calling get_kb_files for this target and treat it as not found."
            ),
            "kb_files": [],
        }

    @staticmethod
    def _has_meaningful_result(kb_files: List[Dict[str, Any]]) -> bool:
        return any(record.get("files") for record in kb_files)

    def _run(
        self,
        resource_uri: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> Dict[str, Any]:
        resolved_resources, allowed_resource_uris, queried_resource_uris, resolution_note = (
            _resolve_kb_resources(
                resources=self.resources,
                resource_uri=resource_uri,
                include_unbound=self.include_unbound,
            )
        )
        attempt_key = "|".join(queried_resource_uris) or str(resource_uri or "__all__")
        logger.info(
            "Get kb files tool resource_uri: requested=%s resolved=%s",
            resource_uri,
            queried_resource_uris or allowed_resource_uris,
        )
        existing_attempts = self._empty_call_counts.get(attempt_key, 0)
        if existing_attempts >= self.max_empty_calls:
            return self._build_final_not_found_response(
                attempt_key=attempt_key,
                resource_uri=queried_resource_uris[0] if len(queried_resource_uris) == 1 else resource_uri,
                queried_resource_uris=queried_resource_uris,
                allowed_resource_uris=allowed_resource_uris,
                message=(
                    resolution_note
                    or "The maximum number of empty get_kb_files attempts has already been reached."
                ),
            )

        if not resolved_resources:
            attempts = self._increment_empty_calls(attempt_key)
            final = attempts >= self.max_empty_calls
            return {
                "status": "not_found" if final else "invalid_resource_uri",
                "resource_uri": resource_uri,
                "resource_uris": queried_resource_uris,
                "allowed_resource_uris": allowed_resource_uris,
                "attempt": attempts,
                "max_attempts": self.max_empty_calls,
                "final": final,
                "message": (
                    (
                        resolution_note
                        or "No rag resource uri could be resolved from the current resources."
                    )
                    + (
                        " Stop calling get_kb_files for this target and treat it as not found."
                        if final
                        else ""
                    )
                ),
                "kb_files": [],
            }

        kb_files = get_kb_files(
            resources=resolved_resources,
            resource_uri=queried_resource_uris[0] if len(queried_resource_uris) == 1 else None,
            include_unbound=self.include_unbound,
            base_url=self.base_url,
        )
        if self._has_meaningful_result(kb_files):
            self._reset_empty_calls(attempt_key)
            return {
                "status": "ok",
                "resource_uri": queried_resource_uris[0] if len(queried_resource_uris) == 1 else None,
                "resource_uris": queried_resource_uris,
                "allowed_resource_uris": allowed_resource_uris,
                "attempt": 0,
                "max_attempts": self.max_empty_calls,
                "final": False,
                "message": resolution_note or "Fetched kb files successfully.",
                "kb_files": kb_files,
            }

        attempts = self._increment_empty_calls(attempt_key)
        final = attempts >= self.max_empty_calls
        return {
            "status": "not_found",
            "resource_uri": queried_resource_uris[0] if len(queried_resource_uris) == 1 else None,
            "resource_uris": queried_resource_uris,
            "allowed_resource_uris": allowed_resource_uris,
            "attempt": attempts,
            "max_attempts": self.max_empty_calls,
            "final": final,
            "message": (
                (
                    resolution_note
                    or "No file metadata was returned from the current rag resource."
                )
                + (
                    " Stop calling get_kb_files for this target and treat it as not found."
                    if final
                    else ""
                )
            ),
            "kb_files": kb_files,
        }

    async def _arun(
        self,
        resource_uri: Optional[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> Dict[str, Any]:
        return self._run(
            resource_uri=resource_uri,
            run_manager=run_manager.get_sync() if run_manager else None,
        )


def get_kb_files_tool(
    resources: List[Resource], include_unbound: bool = True
) -> KBFilesTool | None:
    if not resources:
        return None

    logger.info("create kb files api tool")
    return KBFilesTool(
        resources=resources,
        include_unbound=include_unbound,
    )
