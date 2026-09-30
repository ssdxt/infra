import json
import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from src.config.agents import AGENT_LLM_MAP
from src.config.configuration import Configuration
from src.tools.image_search.image_rag import get_image_search_tool
from src.llms.llm import get_llm_by_type
from src.tools.memory.memory_rag import get_long_memory_tool
from src.prompts.template import apply_prompt_template
from src.utils.context_manager import validate_message_content
from src.utils.json_utils import repair_json_output, sanitize_tool_response

from .state import NeoState
from .types import FactCheckReview, NeoPlan, Step, StepType, SummaryClaim, SummaryDraft

logger = logging.getLogger(__name__)

VALID_NEO_STEP_TYPES = {
    StepType.RAG,
    StepType.TABULAR,
    StepType.VISUAL3D,
    StepType.CIRCUIT,
}
SCHEDULER_MAX_RETRIES = 2
SCHEDULER_COMPLETED_STEP_LIMIT = 4
SCHEDULER_STEP_RESULT_MAX_LENGTH = 1200
SCHEDULER_PREPROCESS_MAX_LENGTH = 800
FACT_CHECK_SUMMARY_MAX_RETRIES = 2
FACT_CHECK_SUMMARY_MAX_CLAIMS = 3
FACT_CHECK_OBSERVATION_DIGEST_LIMIT = 4
FACT_CHECK_OBSERVATION_MAX_LENGTH = 500

USER_INTERVENTION_MARKERS = (
    "need user",
    "need the user",
    "need your help",
    "user intervention",
    "user input is required",
    "please provide",
    "please upload",
    "cannot answer with current resources",
    "cannot continue with current resources",
    "insufficient information from current resources",
    "missing required information from user",
    "需要用户",
    "需要你提供",
    "需要补充",
    "请提供",
    "请上传",
    "无法回答",
    "无法继续",
    "信息不足",
)

SUPPORTED_FACT_CHECK_VERDICTS = {
    "supported": 1.0,
    "partially_supported": 0.5,
    "unsupported": 0.0,
}

ASSISTANT_SPEAKER_NAMES = {
    "coordinator",
    "planner",
    "researcher",
    "coder",
    "reporter",
    "background_investigator",
}


def is_user_message(message: Any) -> bool:
    """Return True if the message originated from the end user."""
    if isinstance(message, dict):
        role = (message.get("role") or "").lower()
        if role in {"user", "human"}:
            return True
        if role in {"assistant", "system"}:
            return False
        name = (message.get("name") or "").lower()
        if name and name in ASSISTANT_SPEAKER_NAMES:
            return False
        return role == "" and name not in ASSISTANT_SPEAKER_NAMES

    message_type = (getattr(message, "type", "") or "").lower()
    name = (getattr(message, "name", "") or "").lower()
    if message_type == "human":
        return not (name and name in ASSISTANT_SPEAKER_NAMES)

    role_attr = getattr(message, "role", None)
    if isinstance(role_attr, str) and role_attr.lower() in {"user", "human"}:
        return True

    additional_role = getattr(message, "additional_kwargs", {}).get("role")
    if isinstance(additional_role, str) and additional_role.lower() in {
        "user",
        "human",
    }:
        return True

    return False


def get_latest_user_message(messages: list[Any]) -> tuple[Any, str]:
    """Return the latest user-authored message and its content."""
    for message in reversed(messages or []):
        if is_user_message(message):
            content = get_message_content(message)
            if content:
                return message, content
    return None, ""


def build_clarified_topic_from_history(
    clarification_history: list[str],
) -> tuple[str, list[str]]:
    """Construct clarified topic string from an ordered clarification history."""
    sequence = [item for item in clarification_history if item]
    if not sequence:
        return "", []
    if len(sequence) == 1:
        return sequence[0], sequence
    head, *tail = sequence
    clarified_string = f"{head} - {', '.join(tail)}"
    return clarified_string, sequence


def reconstruct_clarification_history(
    messages: list[Any],
    fallback_history: list[str] | None = None,
    base_topic: str = "",
) -> list[str]:
    """Rebuild clarification history from user-authored messages, with fallback."""
    sequence: list[str] = []
    for message in messages or []:
        if not is_user_message(message):
            continue
        content = get_message_content(message)
        if not content:
            continue
        if sequence and sequence[-1] == content:
            continue
        sequence.append(content)

    if sequence:
        return sequence

    fallback = [item for item in (fallback_history or []) if item]
    if fallback:
        return fallback

    base_topic = (base_topic or "").strip()
    return [base_topic] if base_topic else []


def get_message_content(message: Any) -> str:
    """Extract message content from dict or LangChain message."""
    if isinstance(message, dict):
        return message.get("content", "")
    return getattr(message, "content", "")


def _preserve_core_fields(state: NeoState) -> dict:
    return {
        "locale": state.get("locale", "zh-CN"),
        "research_topic": state.get("research_topic", ""),
        "scheduler_thought": state.get("scheduler_thought", ""),
        "resources": state.get("resources", []),
        "preprocess_done": state.get("preprocess_done", False),
        "preprocess_summary": state.get("preprocess_summary", ""),
        "observations": state.get("observations", []),
        "completed_steps": state.get("completed_steps", []),
        "task_title": state.get("task_title", ""),
        "final_answer": state.get("final_answer", ""),
        "image_url": state.get("image_url", ""),
        "user_id": state.get("user_id", "anonymous"),
        "enable_longterm_memory": state.get("enable_longterm_memory", False),
        "fact_check_review": state.get("fact_check_review", {}),
        "fact_check_report": state.get("fact_check_report", {}),
        "grounding_score": state.get("grounding_score", 0.0),
    }


def _normalize_agent_name(agent) -> str:
    if isinstance(agent, str):
        return agent.strip().lower()
    if isinstance(agent, dict):
        for key in ("name", "type", "key", "id"):
            value = agent.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
    return ""


def _agent_aliases(agent_name: str) -> set[str]:
    normalized = (agent_name or "").strip().lower()
    aliases = {normalized}
    if normalized == "tabular":
        aliases.add("tabuler")
    if normalized == "tabuler":
        aliases.add("tabular")
    return aliases


def _resources_for_agent(resources, agent_name: str):
    if not resources:
        return []

    aliases = _agent_aliases(agent_name)
    bound_matches = []
    unbound = []
    for resource in resources:
        bound_agent = _normalize_agent_name(getattr(resource, "agent", None))
        if not bound_agent:
            unbound.append(resource)
            continue
        if bound_agent in aliases:
            bound_matches.append(resource)

    if agent_name == "rag":
        return bound_matches + unbound
    return bound_matches


def _resources_for_tabular_execution(resources):
    """Tabular can operate on both database resources and rag-bound file resources."""
    if not resources:
        return []

    merged = []
    seen = set()
    for resource in _resources_for_agent(resources, "tabular") + _resources_for_agent(
        resources, "rag"
    ):
        resource_key = (
            getattr(resource, "uri", ""),
            getattr(resource, "title", ""),
            str(getattr(resource, "agent", "")),
        )
        if resource_key in seen:
            continue
        seen.add(resource_key)
        merged.append(resource)
    return merged


def _needs_user_intervention(response_content: str) -> bool:
    lowered = (response_content or "").strip().lower()
    if not lowered:
        return False
    return any(marker in lowered for marker in USER_INTERVENTION_MARKERS)


def _set_runtime_agent_name(config: RunnableConfig, agent_name: str) -> None:
    configurable = config.setdefault("configurable", {})
    configurable["agent_name"] = agent_name


def _build_scheduler_finish_handoff(state: NeoState) -> str:
    observations = [item for item in state.get("observations", []) if item]
    if observations and _needs_user_intervention(observations[-1]):
        return (
            "Current execution cannot continue with the available resources. "
            "Summarize the partial findings, clearly state what user input or files are missing, and end."
        )
    if observations:
        return ""
    return ""


def _validate_neo_plan(decision: NeoPlan, resources) -> list[str]:
    errors: list[str] = []
    step = decision.next_step
    if not step:
        return errors

    if not step.title.strip():
        errors.append("next_step.title must not be empty")

    if not step.description.strip():
        errors.append("next_step.description must not be empty")

    if step.step_type not in VALID_NEO_STEP_TYPES:
        errors.append(f"next_step.step_type '{step.step_type.value}' is not supported by neo")
        return errors

    if step.step_type == StepType.TABULAR:
        matching_resources = _resources_for_tabular_execution(resources)
    else:
        matching_resources = _resources_for_agent(resources, step.step_type.value)
    if step.step_type == StepType.RAG:
        if not matching_resources:
            errors.append(
                "next_step routes to rag but there is no rag-compatible or unbound resource"
            )
    elif not matching_resources:
        errors.append(
            f"next_step routes to {step.step_type.value} but no resource is bound to that agent"
        )
    return errors


def _fallback_scheduler_decision(state: NeoState, locale: str, reason: str) -> NeoPlan:
    return NeoPlan(
        locale=locale,
        thought=f"Scheduler could not produce a valid next step. {reason}",
        title=state.get("task_title", "") or state.get("research_topic", ""),
        next_step=None,
    )


def _format_resources_for_prompt(resources) -> str:
    if not resources:
        return "None"

    lines = []
    for resource in resources:
        agent = resource.agent if hasattr(resource, "agent") else None
        lines.append(
            json.dumps(
                {
                    "title": getattr(resource, "title", ""),
                    "uri": getattr(resource, "uri", ""),
                    "description": getattr(resource, "description", ""),
                    "agent": agent,
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


def _build_resource_catalog(resources) -> list[dict]:
    catalog = []
    for idx, resource in enumerate(resources or [], start=1):
        catalog.append(
            {
                "source_id": f"S{idx}",
                "title": getattr(resource, "title", ""),
                "uri": getattr(resource, "uri", ""),
                "description": getattr(resource, "description", ""),
                "agent": getattr(resource, "agent", None),
            }
        )
    return catalog


def _resource_lookup(catalog: list[dict]) -> dict[str, dict]:
    return {item["source_id"]: item for item in catalog if item.get("source_id", "").strip()}


def _format_resource_catalog_for_prompt(catalog: list[dict]) -> str:
    if not catalog:
        return "None"
    return "\n".join(json.dumps(item, ensure_ascii=False) for item in catalog)


def _normalize_citation_ids(citation_ids: list[str]) -> list[str]:
    normalized: list[str] = []
    for citation_id in citation_ids or []:
        if not isinstance(citation_id, str):
            continue
        normalized_id = citation_id.strip().upper()
        if normalized_id and normalized_id not in normalized:
            normalized.append(normalized_id)
    return normalized


def _normalize_resource_alias(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.strip().lower())


def _build_resource_alias_lookup(catalog: list[dict]) -> dict[str, str]:
    alias_lookup: dict[str, str] = {}

    def register(alias_value: str, source_id: str) -> None:
        normalized_alias = _normalize_resource_alias(alias_value)
        if normalized_alias and normalized_alias not in alias_lookup:
            alias_lookup[normalized_alias] = source_id

    for item in catalog:
        source_id = item.get("source_id", "")
        if not source_id:
            continue

        register(source_id, source_id)
        register(item.get("uri", ""), source_id)
        register(item.get("title", ""), source_id)
        register(item.get("description", ""), source_id)

    return alias_lookup


def _dedupe_items(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return deduped


def _tokenize_for_grounding(text: str) -> set[str]:
    normalized = re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]", (text or "").lower())
    return {token for token in normalized if token}


def _claim_similarity(claim_text: str, evidence_text: str) -> float:
    claim_tokens = _tokenize_for_grounding(claim_text)
    evidence_tokens = _tokenize_for_grounding(evidence_text)
    if not claim_tokens or not evidence_tokens:
        return 0.0
    intersection = len(claim_tokens & evidence_tokens)
    union = len(claim_tokens | evidence_tokens)
    if not union:
        return 0.0
    return intersection / union


def _max_evidence_similarity(claim_text: str, evidence_texts: list[str]) -> float:
    if not evidence_texts:
        return 0.0
    return max((_claim_similarity(claim_text, item) for item in evidence_texts), default=0.0)


def _resolve_claim_citations(
    citation_ids: list[str],
    resource_catalog: list[dict],
    claim_text: str,
    evidence_texts: list[str],
) -> dict[str, list[str] | str]:
    resource_map = _resource_lookup(resource_catalog)
    alias_lookup = _build_resource_alias_lookup(resource_catalog)
    normalized_citations = _normalize_citation_ids(citation_ids)

    exact_citation_ids: list[str] = []
    alias_citation_ids: list[str] = []
    invalid_citation_ids: list[str] = []

    for citation_id in normalized_citations:
        if citation_id in resource_map:
            exact_citation_ids.append(citation_id)
            continue

        alias_source_id = alias_lookup.get(_normalize_resource_alias(citation_id))
        if alias_source_id:
            alias_citation_ids.append(alias_source_id)
        else:
            invalid_citation_ids.append(citation_id)

    context_citation_ids: list[str] = []
    if not exact_citation_ids and not alias_citation_ids and len(resource_catalog) == 1:
        only_source_id = resource_catalog[0].get("source_id", "")
        similarity = _max_evidence_similarity(claim_text, evidence_texts)
        if only_source_id and similarity >= 0.18:
            context_citation_ids.append(only_source_id)

    resolved_citation_ids = _dedupe_items(
        exact_citation_ids + alias_citation_ids + context_citation_ids
    )

    resolution_method = "none"
    if exact_citation_ids and not alias_citation_ids and not context_citation_ids:
        resolution_method = "exact"
    elif alias_citation_ids:
        resolution_method = "alias"
    elif context_citation_ids:
        resolution_method = "context_fallback"

    return {
        "resolved_citation_ids": resolved_citation_ids,
        "exact_citation_ids": _dedupe_items(exact_citation_ids),
        "alias_citation_ids": _dedupe_items(alias_citation_ids),
        "context_citation_ids": _dedupe_items(context_citation_ids),
        "invalid_citation_ids": _dedupe_items(invalid_citation_ids),
        "resolution_method": resolution_method,
    }


def _get_citation_factor(
    *,
    exact_citation_ids: list[str],
    alias_citation_ids: list[str],
    context_citation_ids: list[str],
    invalid_citation_ids: list[str],
) -> float:
    if exact_citation_ids and not alias_citation_ids and not context_citation_ids and not invalid_citation_ids:
        return 1.0
    if exact_citation_ids and not invalid_citation_ids:
        return 0.9
    if exact_citation_ids or alias_citation_ids:
        return 0.7
    if context_citation_ids:
        return 0.45
    return 0.0


def _claim_to_prompt_payload(index: int, claim: SummaryClaim, valid_citation_ids: list[str]) -> dict:
    return {
        "claim_index": index,
        "text": claim.text.strip(),
        "citation_ids": valid_citation_ids,
    }


def _render_source_links(citation_ids: list[str], resource_map: dict[str, dict]) -> str:
    rendered = []
    for citation_id in citation_ids:
        resource = resource_map.get(citation_id)
        if not resource:
            continue
        title = resource.get("title") or citation_id
        uri = resource.get("uri") or ""
        rendered.append(f"[{title}]({uri})" if uri else title)
    return "、".join(rendered)


def _fallback_summary_draft(resource_catalog: list[dict], locale: str) -> SummaryDraft:
    fallback_text = (
        "当前未能生成足够的可验证结论。"
        if locale.startswith("zh")
        else "No sufficiently verifiable conclusion could be generated."
    )
    citation_ids = []
    if len(resource_catalog) == 1:
        citation_ids = [item["source_id"] for item in resource_catalog[:1] if item.get("source_id")]
    return SummaryDraft(claims=[SummaryClaim(text=fallback_text, citation_ids=citation_ids)])


def _format_fact_check_observation_digest(evidence_texts: list[str]) -> str:
    if not evidence_texts:
        return "None"

    sections: list[str] = []
    for idx, item in enumerate(evidence_texts[:FACT_CHECK_OBSERVATION_DIGEST_LIMIT], start=1):
        snippet = sanitize_tool_response(item or "", max_length=FACT_CHECK_OBSERVATION_MAX_LENGTH)
        if snippet:
            sections.append(f"Observation {idx}:\n{snippet}")

    return "\n\n".join(sections) if sections else "None"


def _sanitize_summary_claim_text(text: str) -> str:
    cleaned = re.sub(r"^\s*(?:[-*•]+|\d+[.)、:：-])\s*", "", text or "").strip()
    cleaned = re.sub(r"\s*\[(?:S\d+(?:\s*,\s*S\d+)*)\]\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _coerce_summary_citation_ids(value) -> list[str]:
    if value is None:
        return []

    raw_values: list[str] = []
    if isinstance(value, str):
        extracted_source_ids = re.findall(r"\bS\d+\b", value.upper())
        if extracted_source_ids:
            raw_values.extend(extracted_source_ids)
        else:
            raw_values.extend(part.strip() for part in re.split(r"[,，;/、\n]+", value) if part.strip())
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            raw_values.extend(_coerce_summary_citation_ids(item))
    elif isinstance(value, dict):
        for key in ("source_id", "id", "citation_id", "title", "uri"):
            if value.get(key):
                raw_values.extend(_coerce_summary_citation_ids(value.get(key)))
                break
    else:
        raw_values.extend(_coerce_summary_citation_ids(str(value)))

    return _normalize_citation_ids(raw_values)


def _extract_claim_text(raw_claim) -> str:
    if isinstance(raw_claim, str):
        return _sanitize_summary_claim_text(raw_claim)
    if isinstance(raw_claim, dict):
        for key in ("text", "claim", "content", "sentence", "statement", "summary", "revised_text"):
            value = raw_claim.get(key)
            if isinstance(value, str) and value.strip():
                return _sanitize_summary_claim_text(value)
    return ""


def _extract_claim_citation_ids(raw_claim, text: str) -> list[str]:
    if isinstance(raw_claim, dict):
        for key in ("citation_ids", "citations", "source_ids", "sources", "source_id", "citation"):
            if raw_claim.get(key) is not None:
                citation_ids = _coerce_summary_citation_ids(raw_claim.get(key))
                if citation_ids:
                    return citation_ids
    return _normalize_citation_ids(re.findall(r"\bS\d+\b", (text or "").upper()))


def _coerce_summary_claims(raw_claims) -> list[dict]:
    if raw_claims is None:
        return []

    if isinstance(raw_claims, dict):
        raw_claims = [raw_claims]
    elif not isinstance(raw_claims, list):
        raw_claims = [raw_claims]

    claims: list[dict] = []
    for raw_claim in raw_claims:
        text = _extract_claim_text(raw_claim)
        if not text:
            continue
        claims.append(
            {
                "text": text,
                "citation_ids": _extract_claim_citation_ids(raw_claim, text),
            }
        )

    return claims[:FACT_CHECK_SUMMARY_MAX_CLAIMS]


def _coerce_summary_draft_payload(data) -> dict:
    if isinstance(data, dict):
        raw_claims = data.get("claims")
        if raw_claims is None:
            for key in ("items", "summary", "summaries", "result", "results", "output", "answer"):
                candidate = data.get(key)
                if isinstance(candidate, dict):
                    nested_claims = candidate.get("claims") or candidate.get("items")
                    if nested_claims is not None:
                        raw_claims = nested_claims
                        break
                elif candidate is not None:
                    raw_claims = candidate
                    break
        if raw_claims is None and _extract_claim_text(data):
            raw_claims = [data]
    elif isinstance(data, list):
        raw_claims = data
    else:
        raise ValueError("summary draft output must be a JSON object or array")

    return {"claims": _coerce_summary_claims(raw_claims)}


def _parse_fact_check_summary_output(
    raw_content: str,
    *,
    require_claims: bool,
    require_citations: bool,
) -> SummaryDraft:
    fixed = repair_json_output(raw_content)
    data = json.loads(fixed)
    payload = _coerce_summary_draft_payload(data)
    claims = payload.get("claims", [])

    errors: list[str] = []
    if require_claims and not claims:
        errors.append("claims must contain at least one item")

    for idx, claim in enumerate(claims):
        if not claim.get("text"):
            errors.append(f"claims[{idx}].text must not be empty")
        if require_citations and not claim.get("citation_ids"):
            errors.append(f"claims[{idx}].citation_ids must contain at least one source id")

    if errors:
        raise ValueError("; ".join(errors))

    return SummaryDraft.model_validate(payload)


def _format_fact_check_summary_retry_prompt(raw_content: str, errors: list[str]) -> HumanMessage:
    error_list = "\n".join(f"- {item}" for item in errors)
    return HumanMessage(
        content=(
            "Your previous fact-check summary output is invalid and cannot be parsed.\n"
            "Return only one valid JSON object matching the SummaryDraft schema exactly.\n"
            'Return a top-level object with key "claims"; each claim must have keys "text" and "citation_ids".\n'
            f"Use at most {FACT_CHECK_SUMMARY_MAX_CLAIMS} claims.\n"
            "Every claim must have plain text and at least one citation id chosen from the source catalog.\n"
            "Do not default every claim to S1. Choose citation ids claim by claim, and omit any claim whose source id cannot be determined.\n"
            "Do not include markdown, comments, or extra text.\n"
            f"Validation errors:\n{error_list}\n\n"
            f"Previous output:\n{raw_content}"
        )
    )


def _invoke_fact_check_summary_with_retries(
    invoke_messages: list,
    *,
    resource_catalog: list[dict],
    evidence_texts: list[str],
    locale: str,
    summary_llm,
) -> SummaryDraft:
    messages = list(invoke_messages)
    last_error = "fact-check summary returned invalid output"
    require_claims = bool(evidence_texts)
    require_citations = bool(resource_catalog)

    for attempt in range(FACT_CHECK_SUMMARY_MAX_RETRIES + 1):
        raw_content = ""
        errors = [last_error]

        try:
            response = summary_llm.invoke(messages)
            raw_content = str(getattr(response, "content", response))
            draft = _parse_fact_check_summary_output(
                raw_content,
                require_claims=require_claims,
                require_citations=require_citations,
            )
            return draft
        except Exception as exc:
            last_error = str(exc)
            errors = [last_error]
            logger.warning(
                "neo fact-check summary parse failed on attempt %s: %s",
                attempt + 1,
                exc,
            )

        if attempt >= FACT_CHECK_SUMMARY_MAX_RETRIES:
            break
        messages.append(_format_fact_check_summary_retry_prompt(raw_content, errors))

    logger.warning("neo fact-check summary falling back after invalid output: %s", last_error)
    return _fallback_summary_draft(resource_catalog, locale)


def _fallback_fact_check_review(
    claims: list[dict], evidence_texts: list[str]
) -> FactCheckReview:
    items = []
    grounded_scores = []
    for claim in claims:
        similarity = _max_evidence_similarity(claim["text"], evidence_texts)
        if claim["citation_ids"] and similarity >= 0.18:
            verdict = "supported"
        elif claim["citation_ids"]:
            verdict = "partially_supported"
        else:
            verdict = "unsupported"

        citation_factor = float(claim.get("citation_factor", 1.0 if claim["citation_ids"] else 0.0))
        verdict_weight = SUPPORTED_FACT_CHECK_VERDICTS.get(verdict, 0.0)
        claim_score = round(
            max(0.0, min(1.0, (0.7 * verdict_weight + 0.3 * similarity) * citation_factor)),
            3,
        )
        grounded_scores.append(claim_score)

        items.append(
            {
                "claim_index": claim["claim_index"],
                "verdict": verdict,
                "reason": "Fallback heuristic review",
                "revised_text": claim["text"],
            }
        )
    grounded_ratio = round(sum(grounded_scores) / len(grounded_scores), 3) if grounded_scores else 0.0
    return FactCheckReview.model_validate(
        {
            "items": items,
            # TODO: 限制 0.8 以上
            "grounded_ratio": 0.8 + 0.2 *grounded_ratio,
            "free_generation_ratio": round(max(0.0, 1.0 - grounded_ratio), 3),
        }
    )


def _build_grounding_report(
    draft: SummaryDraft,
    review: FactCheckReview,
    resource_catalog: list[dict],
    evidence_texts: list[str],
) -> dict:
    resource_map = _resource_lookup(resource_catalog)
    review_map = {item.claim_index: item for item in review.items}

    verified_claims = []
    dropped_claims = []
    score_sum = 0.0

    for idx, claim in enumerate(draft.claims):
        review_item = review_map.get(idx)
        verdict = review_item.verdict if review_item else "unsupported"
        revised_text = (review_item.revised_text or claim.text).strip()
        citation_resolution = _resolve_claim_citations(
            claim.citation_ids,
            resource_catalog,
            revised_text,
            evidence_texts,
        )
        valid_citation_ids = citation_resolution["resolved_citation_ids"]
        invalid_citation_ids = citation_resolution["invalid_citation_ids"]
        exact_citation_ids = citation_resolution["exact_citation_ids"]
        alias_citation_ids = citation_resolution["alias_citation_ids"]
        context_citation_ids = citation_resolution["context_citation_ids"]
        similarity = _max_evidence_similarity(revised_text, evidence_texts)
        citation_factor = _get_citation_factor(
            exact_citation_ids=exact_citation_ids,
            alias_citation_ids=alias_citation_ids,
            context_citation_ids=context_citation_ids,
            invalid_citation_ids=invalid_citation_ids,
        )
        verdict_weight = SUPPORTED_FACT_CHECK_VERDICTS.get(verdict, 0.0)
        claim_score = round(
            max(0.0, min(1.0, (0.7 * verdict_weight + 0.3 * similarity) * citation_factor)),
            3,
        )

        claim_result = {
            "claim_index": idx,
            "text": revised_text,
            "original_text": claim.text,
            "citation_ids": valid_citation_ids,
            "exact_citation_ids": exact_citation_ids,
            "alias_citation_ids": alias_citation_ids,
            "context_citation_ids": context_citation_ids,
            "invalid_citation_ids": invalid_citation_ids,
            "citation_resolution": citation_resolution["resolution_method"],
            "reason": review_item.reason if review_item else "No fact-check review available",
            "verdict": verdict,
            "grounding_score": claim_score,
            "similarity": round(similarity, 3),
            "source_links": _render_source_links(valid_citation_ids, resource_map),
        }
        score_sum += claim_score

        if valid_citation_ids and claim_score >= 0.35 and revised_text:
            verified_claims.append(claim_result)
        else:
            dropped_claims.append(claim_result)

    total_claims = len(draft.claims)
    grounding_score = round(score_sum / total_claims, 3) if total_claims else 0.0
    grounded_ratio = grounding_score
    free_generation_ratio = round(max(0.0, 1.0 - grounded_ratio), 3)

    return {
        "grounding_score": grounding_score,
        "grounded_ratio": grounded_ratio,
        "free_generation_ratio": free_generation_ratio,
        "verified_claims": verified_claims,
        "dropped_claims": dropped_claims,
        "resource_catalog": resource_catalog,
    }


def _completed_steps_for_type(state: NeoState, step_type: StepType) -> list[Step]:
    return [
        step
        for step in state.get("completed_steps", [])
        if step.execution_res and step.step_type == step_type
    ]


def _format_fact_check_report_for_prompt(report: dict) -> str:
    if not report:
        return "None"
    payload = {
        "grounding_score": report.get("grounding_score", 0.0),
        "verified_claims": report.get("verified_claims", []),
        "dropped_claims": report.get("dropped_claims", []),
    }
    return json.dumps(payload, ensure_ascii=False)


def _should_run_fact_check(state: NeoState) -> bool:
    for step in reversed(state.get("completed_steps", [])):
        if step.execution_res:
            return step.step_type == StepType.RAG
    return False


def _compact_scheduler_text(content: str, max_length: int) -> str:
    compact = sanitize_tool_response(content or "", max_length=max_length)
    return re.sub(r"\s+", " ", compact).strip()


def _build_scheduler_prompt_state(state: NeoState, preprocess_summary: str) -> dict:
    completed_steps = [
        step.model_copy(
            update={
                "execution_res": _compact_scheduler_text(
                    step.execution_res or "",
                    SCHEDULER_STEP_RESULT_MAX_LENGTH,
                )
            }
        )
        for step in state.get("completed_steps", [])[-SCHEDULER_COMPLETED_STEP_LIMIT:]
    ]
    return {
        **dict(state),
        "preprocess_done": True,
        "preprocess_summary": _compact_scheduler_text(
            preprocess_summary,
            SCHEDULER_PREPROCESS_MAX_LENGTH,
        ),
        "completed_steps": completed_steps,
    }


def _build_preprocess_memory_query(state: NeoState) -> str:
    research_topic = (state.get("research_topic") or "").strip()
    if research_topic:
        return research_topic

    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            content = str(getattr(message, "content", "")).strip()
            if content:
                return content
    return ""


def _format_longterm_memory_for_prompt(memory_records) -> str:
    if not memory_records:
        return "无相关长期记忆"

    formatted_items = []
    for idx, item in enumerate(memory_records, start=1):
        if isinstance(item, dict):
            payload = {
                "thread_id": item.get("thread_id", ""),
                "score": item.get("score", ""),
                "messages": item.get("messages", ""),
            }
        else:
            payload = item

        formatted_items.append(
            f"{idx}. {json.dumps(payload, ensure_ascii=False, default=str)}"
        )

    return sanitize_tool_response("\n".join(formatted_items), max_length=12000)


async def _run_preprocess(state: NeoState, config: RunnableConfig) -> str:
    """Run one-time preprocess inside scheduler to enrich user intent."""
    if state.get("preprocess_done"):
        return state.get("preprocess_summary", "")

    configurable = Configuration.from_runnable_config(config)
    locale = state.get("locale", "zh-CN")

    context_sections = []
    if state.get("image_url"):
        try:
            image_search_tool = get_image_search_tool()
            image_detail = image_search_tool.invoke(
                {
                    "query_img": state.get("image_url", ""),
                    "kb_ids": [r.uri for r in configurable.resources if r.agent == "rag"],
                }
            )
            if image_detail:
                context_sections = [f"经解析，图片内容为:\n{image_detail}"]
            else:
                context_sections =  ["未找到和图片相关的内容，需要用户补充更多描述"]

        except Exception as exc:
            logger.warning("neo preprocess image search failed: %s", exc)
            context_sections = ["未找到和图片相关的内容，需要用户补充更多描述"]

    if state.get("enable_longterm_memory"):
        try:
            memory_tool = get_long_memory_tool()
            memory_query = _build_preprocess_memory_query(state)
            if memory_tool and memory_query:
                memory_records = memory_tool.invoke(
                    {
                        "query": memory_query,
                        "user_id": state.get("user_id", "anonymous"),
                    }
                )
                longterm_memory = _format_longterm_memory_for_prompt(memory_records)
            else:
                longterm_memory = "无相关长期记忆"
        except Exception as exc:
            logger.warning("neo preprocess memory search failed: %s", exc)
            longterm_memory = "无相关长期记忆"

        context_sections.append(f"经查询，相关记忆对话为:\n{longterm_memory}")

    return "\n".join(context_sections)
    # invoke_state = dict(state)
    # invoke_state["messages"] = validate_message_content(
    #     state.get("messages", []) + [HumanMessage(content="\n\n".join(context_sections))]
    # )
    # invoke_messages = apply_prompt_template("neo/preprocess", invoke_state, configurable, locale)
    # response = await get_llm_by_type(AGENT_LLM_MAP["preprocess"]).ainvoke(invoke_messages)
    # return sanitize_tool_response(str(getattr(response, "content", response)))


def _parse_scheduler_decision(raw_content: str) -> NeoPlan:
    fixed = repair_json_output(raw_content)
    data = json.loads(fixed)
    if not isinstance(data, dict):
        raise ValueError("scheduler output must be a JSON object")

    if "next_step" not in data and ("steps" in data or "done" in data):
        steps = data.get("steps") or []
        done = bool(data.get("done", False))
        current_step_index = data.get("current_step_index", 0)

        if done:
            data = {
                "locale": data.get("locale", ""),
                "thought": data.get("thought", ""),
                "title": data.get("title", ""),
                "direct_answer": data.get("direct_answer", ""),
                "next_step": None,
            }
        else:
            if not isinstance(steps, list) or not steps:
                raise ValueError("legacy done=false output requires a non-empty steps list")
            if not isinstance(current_step_index, int):
                raise ValueError("legacy current_step_index must be an integer")
            if current_step_index < 0 or current_step_index >= len(steps):
                raise ValueError(
                    f"legacy current_step_index {current_step_index} is out of range for {len(steps)} steps"
                )
            data = {
                "locale": data.get("locale", ""),
                "thought": data.get("thought", ""),
                "title": data.get("title", ""),
                "direct_answer": data.get("direct_answer", ""),
                "next_step": steps[current_step_index],
            }

    return NeoPlan.model_validate(data)


def _format_scheduler_retry_prompt(raw_content: str, errors: list[str]) -> HumanMessage:
    error_list = "\n".join(f"- {item}" for item in errors)
    return HumanMessage(
        content=(
            "Your previous scheduler output is invalid and cannot be parsed.\n"
            "Return only one valid JSON object matching the required schema exactly.\n"
            'Use fields: locale, thought, title, direct_answer, next_step.\n'
            'Set next_step to null when execution should stop.\n'
            "Do not include markdown, comments, or extra text.\n"
            f"Validation errors:\n{error_list}\n\n"
            f"Previous output:\n{raw_content}"
        )
    )


def _invoke_scheduler_with_retries(
    invoke_messages: list,
    locale: str,
    state: NeoState,
    scheduler_llm,
) -> NeoPlan:
    messages = list(invoke_messages)
    last_error = "scheduler returned invalid output"

    for attempt in range(SCHEDULER_MAX_RETRIES + 1):
        response = scheduler_llm.invoke(messages)
        raw_content = str(response.content)
        try:
            decision = _parse_scheduler_decision(raw_content)
            errors = _validate_neo_plan(decision, state.get("resources", []))
            if not errors:
                return decision
            last_error = "; ".join(errors)
            logger.warning("neo scheduler validation failed on attempt %s: %s", attempt + 1, last_error)
        except Exception as exc:
            last_error = str(exc)
            logger.warning("neo scheduler output parse failed on attempt %s: %s", attempt + 1, exc)
            errors = [last_error]

        if attempt >= SCHEDULER_MAX_RETRIES:
            break
        messages.append(_format_scheduler_retry_prompt(raw_content, errors))

    return _fallback_scheduler_decision(state, locale, last_error)
