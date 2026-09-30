import json
import logging
import re
from pathlib import Path
from typing import Any, Optional, Sequence

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool
from pydantic import Field

from src.llms.llm import get_llm_by_type

logger = logging.getLogger(__name__)

RESOURCE_ROOT = Path(__file__).resolve().parent / "resources"

EXAMPLE_OUTPUT = {
    "action": "postMessage",
    "message": {"type": "focus", "name": "模块名称"},
}
example1 = {
    "action": "postMessage",
    "message": {"type": "playAnimation", "name": "整车拆装"},
}
example2 = {
    "action": "postMessage",
    "message": {"type": "focus", "name": "驱动总成"},
}
example3 = {
    "action": "postMessage",
    "message": {"type": "focus", "name": "底盘"},
}


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (value or "").strip().lower())


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load visual3d resource %s: %s", path, exc)
        return []

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _load_text(path: Path) -> str:
    if not path.is_file():
        return ""

    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception as exc:
        logger.warning("Failed to load visual3d text resource %s: %s", path, exc)
        return ""


def _match_item_by_exact_name(
    name: str,
    items: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    normalized_name = _normalize_text(name)
    if not normalized_name:
        return None

    for item in items:
        if _normalize_text(str(item.get("name", "")).strip()) == normalized_name:
            return item
    return None


def _resource_catalog_payload(resources: Sequence[dict[str, Any]]) -> str:
    catalog = []
    for resource in resources:
        catalog.append(
            {
                "uri": resource.get("uri", ""),
                "title": resource.get("title", ""),
                "description": resource.get("description", ""),
                "playAnimationNames": [
                    str(item.get("name", "")).strip()
                    for item in resource.get("play_animation_items", [])
                    if str(item.get("name", "")).strip()
                ],
                "focusNames": [
                    str(item.get("name", "")).strip()
                    for item in resource.get("focus_items", [])
                    if str(item.get("name", "")).strip()
                ],
            }
        )
    return json.dumps(catalog, ensure_ascii=False, indent=2)


class Visual3DTool(BaseTool):
    name: str = "visual3d"
    description: str = (
        "Use LLM parsing plus local visual3d resources to generate a standardized 3D postMessage payload."
    )

    llm: Any | None = Field(default=None, exclude=True)
    resources: list[Any] = Field(default_factory=list, exclude=True)

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> dict[str, Any]:
        logger.info("Visual3D tool query: %s", query)

        prompt_resources = self._load_prompt_resources()
        if not prompt_resources:
            resource_uris = [
                getattr(resource, "uri", "")
                for resource in self.resources
                if getattr(resource, "uri", "")
            ]
            return {
                "error": (
                    "No local visual3d resource was found for the current bound resources. "
                    f"Expected folders under {RESOURCE_ROOT}. Bound uris: {resource_uris}"
                )
            }

        try:
            decision = self._invoke_llm_decision(query, prompt_resources)
        except Exception as exc:
            logger.error("Error in Visual3D LLM decision: %s", exc)
            return {"error": "Failed to process query. Please try again."}

        return self._resolve_llm_decision(decision, prompt_resources)

    def _load_prompt_resources(self) -> list[dict[str, Any]]:
        loaded: list[dict[str, Any]] = []
        seen_uris: set[str] = set()

        candidate_uris = [str(getattr(resource, "uri", "") or "").strip() for resource in self.resources]
        if not any(candidate_uris):
            if RESOURCE_ROOT.is_dir():
                candidate_uris = sorted(
                    resource_dir.name
                    for resource_dir in RESOURCE_ROOT.iterdir()
                    if resource_dir.is_dir()
                )

        for resource in self.resources:
            uri = str(getattr(resource, "uri", "") or "").strip()
            if not uri or uri in seen_uris:
                continue
            bundle = self._load_resource_bundle(
                uri=uri,
                title=getattr(resource, "title", "") or uri,
                description=getattr(resource, "description", "") or "",
            )
            if bundle is not None:
                loaded.append(bundle)
                seen_uris.add(uri)

        for uri in candidate_uris:
            if not uri or uri in seen_uris:
                continue
            bundle = self._load_resource_bundle(uri=uri, title=uri, description="")
            if bundle is not None:
                loaded.append(bundle)
                seen_uris.add(uri)

        return loaded

    def _load_resource_bundle(
        self,
        uri: str,
        title: str,
        description: str,
    ) -> dict[str, Any] | None:
        resource_dir = RESOURCE_ROOT / uri
        if not resource_dir.is_dir():
            return None

        focus_items = _load_json_array(resource_dir / "focus.json")
        play_animation_items = _load_json_array(resource_dir / "playAnimation.json")
        reset_items = _load_json_array(resource_dir / "reset.json")
        if not focus_items and not play_animation_items and not reset_items:
            return None

        return {
            "uri": uri,
            "title": title or uri,
            "description": description or "",
            "url": _load_text(resource_dir / "url.txt"),
            "focus_items": focus_items,
            "play_animation_items": play_animation_items,
            "reset_items": reset_items,
        }

    def _invoke_llm_decision(
        self,
        query: str,
        prompt_resources: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        if self.llm is None:
            raise ValueError("visual3d llm is not configured")

        prompt = PromptTemplate.from_template(
            """You are an expert in parsing user queries for 3D visual models.
            Based on the user query: {query}

            Available visual3d resources:
            {resource_catalog}

            Analyze the query and choose exactly one command.

            Rules:
            - The message type must be exactly one of 'focus' or 'playAnimation'.
            - For `focus`, the `name` must be chosen from the matching resource's `focusNames`.
            - For `playAnimation`, the `name` must be chosen from the matching resource's `playAnimationNames`.
            - Output only `type` and `name` in `message`.
            - Never output `id`; the runtime will resolve the id from local resource dictionaries.
            - Never output synonyms such as 'highlight', 'disassemble', or 'reset'.
            - If the user asks for animation, choose `playAnimation`; otherwise choose `focus`.

            示例1: 播放重卡整车拆装动画
            output: {example1}

            示例2: 定位重卡驱动总成
            output: {example2}

            示例3: 定位重卡底盘
            output: {example3}

            Output strictly in this JSON format (no extra text):
            ```json
            {example_format}
            ```
            user: {query}
            output: """
        )

        parser = JsonOutputParser()
        chain = prompt | self.llm | parser
        return chain.invoke(
            {
                "query": query,
                "resource_catalog": _resource_catalog_payload(prompt_resources),
                "example_format": json.dumps(EXAMPLE_OUTPUT, indent=2, ensure_ascii=False),
                "example1": json.dumps(example1, indent=2, ensure_ascii=False),
                "example2": json.dumps(example2, indent=2, ensure_ascii=False),
                "example3": json.dumps(example3, indent=2, ensure_ascii=False),
            }
        )

    def _resolve_llm_decision(
        self,
        decision: dict[str, Any],
        prompt_resources: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        message = decision.get("message", {})
        action_type = str(message.get("type", "")).strip()
        target_name = str(message.get("name", "")).strip()

        if action_type not in {"focus", "playAnimation"}:
            return {"error": f"Visual3D LLM returned unsupported type: {action_type}"}
        if not target_name:
            return {"error": "Visual3D LLM did not return a valid target name."}

        matches: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for resource in prompt_resources:
            candidate_items = (
                resource.get("play_animation_items", [])
                if action_type == "playAnimation"
                else resource.get("focus_items", [])
            )
            target = _match_item_by_exact_name(target_name, candidate_items)
            if target is not None:
                matches.append((resource, target))

        if not matches:
            return {
                "error": (
                    f"Visual3D LLM returned name `{target_name}` but no matching {action_type} target was found."
                )
            }

        if len(matches) > 1:
            matched_resource_uris = [resource.get("uri", "") for resource, _ in matches]
            return {
                "error": (
                    f"Visual3D LLM returned ambiguous name `{target_name}` for {action_type}. "
                    f"Matched resources: {matched_resource_uris}"
                )
            }

        selected_resource, target = matches[0]
        return self._build_action_payload(
            resource=selected_resource,
            action_type=action_type,
            target=target,
        )

    def _build_action_payload(
        self,
        resource: dict[str, Any],
        action_type: str,
        target: dict[str, Any],
    ) -> dict[str, Any]:
        target_name = str(target.get("name", "") or resource.get("title", "")).strip()
        target_id = str(target.get("uuid", "")).strip()
        resource_title = resource.get("title") or resource.get("uri", "")
        available_actions = []
        if resource.get("focus_items"):
            available_actions.append("focus")
        if resource.get("play_animation_items"):
            available_actions.append("playAnimation")

        primary_command = {
            "action": "postMessage",
            "message": {
                "type": action_type,
                "id": target_id,
                "name": target_name
            },
        }
        commands = []
        if resource.get("reset_items"):
            reset_item = resource["reset_items"][0]
            commands.append(
                {
                    "action": "postMessage",
                    "message": {
                        "type": "reset",
                        "id": str(reset_item.get("uuid", "")).strip(),
                        "name": "重置"
                    },
                }
            )
        commands.append(primary_command)

        if len(commands) > 1:
            result = f"已先将 `{resource_title}` 恢复到初始视角，再执行 `{action_type}` 指令。"
        elif action_type == "playAnimation":
            result = f"已成功调用 `{resource_title}` 的动画 `{target_name}`。"
        else:
            result = f"已成功展示 `{resource_title}` 的 3D 模型，并定位到 `{target_name}`。"

        return {
            **primary_command,
            "commands": commands,
            "target_name": target_name,
            "url": resource.get("url", ""),
            "resource": {
                "uri": resource.get("uri", ""),
                "title": resource_title,
                "description": resource.get("description", ""),
            },
            "available_actions": available_actions,
            "result": result,
        }

    async def _arun(
        self,
        query: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> dict[str, Any]:
        return self._run(query, run_manager.get_sync() if run_manager else None)


def get_visual3d_tool(
    resources: Optional[list[Any]] = None,
) -> Visual3DTool | None:
    logger.info("Creating Visual3D tool")
    llm = get_llm_by_type("basic")
    return Visual3DTool(
        llm=llm,
        resources=resources or [],
    )


if __name__ == "__main__":
    tool = get_visual3d_tool()
    if tool:
        resp = tool.invoke("展示重卡底盘")
        print(json.dumps(resp, indent=2, ensure_ascii=False))
