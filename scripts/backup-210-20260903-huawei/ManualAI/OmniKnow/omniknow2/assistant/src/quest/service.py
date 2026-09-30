import json
import logging
import random
import threading
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage

from src.config.agents import AGENT_LLM_MAP
from src.llms.llm import get_llm_by_type
from src.quest.chat_tool import QuestKBSearchTool
from src.quest.schemas import (
    QuestChatReference,
    QuestChatRequest,
    QuestChatResponse,
    QuestEvaluationRecord,
    QuestEvaluationQuestion,
    QuestEvaluationScoreSummary,
    QuestEvaluationChapterSummary,
    QuestGenerateRequest,
    QuestGenerateResponse,
    RawQuestGeneration,
    RawQuestQuestion,
    RawQuestScore,
    QuestScoreRequest,
    QuestScoreResponse,
    build_question_payload,
)
from src.subagents.rag.milvus_rag import MilvusAPIRetriever

logger = logging.getLogger(__name__)

MAX_SOURCE_CHARS = 12000
MCQ_COUNT = 4
QA_COUNT = 1
QUEST_CHAT_MEMORY_MAX_MESSAGES = 6
QUEST_CHAT_MEMORY_MAX_CHARS = 1200

QUESTION_GENERATION_PROMPT = """
你是一个严格的中文出题助手。

任务要求：
1. 仅基于提供的标题和正文内容出题，不要编造资料里没有的信息。
2. 生成 5 道题：4 道单选题，1 道问答题。
3. 返回字段必须是：
   - questions: list
   - 每个元素包含 question_type, question_name, options, chunk_ids, answer
4. question_type 只能是“选择”或“问答”。
5. 选择题：
   - question_name 不超过 50 个中文字符，问题要清楚完整
   - options 必须是 4 个选项文本，每个不超过 20 个中文字符
   - chunk_ids 必须是 list，且至少包含 1 个 chunk_id
   - answer 必须是单个正确选项的下标列表，例如 [0]
6. 问答题：
   - question_name 不超过 100 个中文字符
   - options 必须为 []
   - chunk_ids 必须是 list，且至少包含 1 个 chunk_id
   - answer 必须是 200 个中文字符以内的标准答案
7. chunk_ids 只能从提供给你的正文里的 chunk_id 标记中选择，不能编造。
8. 题目要尽量覆盖标题正文里的不同知识点，避免重复。
9. 不要输出任何解释、前后缀或 markdown，只输出符合 schema 的 JSON。
"""

ANSWER_SCORING_PROMPT = """
你是一个严格的中文问答题评分助手。

任务要求：
1. 根据标准答案和考生答案，对考生答案打分。
2. score 取值范围只能是 0 到 10 的整数，不能有小数。
3. reason 必须给出简短判分理由，且不超过 50 个中文字符。
4. 评分时优先看事实正确性、关键信息覆盖度、是否偏题。
5. 完全正确可给 9 到 10 分，部分正确给 4 到 8 分，明显错误或空泛给 0 到 3 分。
6. 只输出符合 schema 的 JSON，不要输出解释、markdown 或其他文本。
"""

QUEST_CHAT_AGENT_PROMPT = """
你是一个严格的中文知识库问答助手。

任务要求：
1. 你必须优先调用 `quest_kb_search` 工具检索知识，再回答问题。
2. 只能基于工具返回的内容回答，禁止使用外部常识补充或猜测。
3. 如果工具没有返回足够信息，明确说明“在指定文件范围内未检索到足够依据”。
4. 回答尽量简洁、直接；如果存在明确依据，可分点总结。
5. 不要编造出处，不要虚构页码或文件名。
"""

QUEST_CHAT_FALLBACK_PROMPT = """
你是一个严格的中文知识库问答助手。

任务要求：
1. 仅根据提供的检索片段回答用户问题，禁止编造。
2. 如果检索片段不足以支撑回答，明确说明“在指定文件范围内未检索到足够依据”。
3. 回答简洁清楚，优先提炼结论，再补充必要细节。
"""

QUEST_CHAT_NO_RESULT_MESSAGE = "在指定文件范围内未检索到足够依据，暂时无法回答这个问题。"

EVALUATION_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "quest" / "evaluation_prompt.md"
)


class QuestService:
    def __init__(self, retriever: MilvusAPIRetriever | None = None) -> None:
        self._retriever = retriever
        self._chat_memory: dict[str, deque[dict[str, str]]] = defaultdict(
            lambda: deque(maxlen=QUEST_CHAT_MEMORY_MAX_MESSAGES)
        )
        self._chat_memory_lock = threading.RLock()

    @property
    def retriever(self) -> MilvusAPIRetriever:
        if self._retriever is None:
            self._retriever = MilvusAPIRetriever()
        return self._retriever

    def generate_questions(
        self, request: QuestGenerateRequest
    ) -> QuestGenerateResponse:
        candidates = self._list_title_candidates(
            request.collection_name,
            request.file_ids,
        )
        if not candidates:
            raise ValueError("No available titles found for the given file_ids")

        random.shuffle(candidates)

        selected_title: str | None = None
        selected_file_id: str | None = None
        content: str | None = None
        valid_chunk_ids: list[str] | None = None

        for candidate in candidates:
            title = candidate["title"]
            file_id = candidate["file_id"]

            chunks = self.retriever.client.list_chunks_by_title_fileid(
                request.collection_name,
                title,
                file_id,
            )
            text_chunks = self._extract_text_chunks(chunks)
            if not text_chunks:
                continue

            content, valid_chunk_ids = self._build_content(text_chunks)
            if not content:
                continue

            selected_title = title
            selected_file_id = file_id
            break

        if not selected_title or not selected_file_id or not content or not valid_chunk_ids:
            raise ValueError("No text chunks found under the selected titles")

        questions = self._generate_question_set(
            selected_title,
            content,
            valid_chunk_ids,
        )
        return QuestGenerateResponse(
            collection_name=request.collection_name,
            file_id=selected_file_id,
            title=selected_title,
            content=questions,
        )

    def chat(self, request: QuestChatRequest) -> QuestChatResponse:
        tool = self._build_chat_tool(request)
        answer: str = ""
        context = ""

        try:
            answer = self._run_quest_chat_agent(
                request.thread_id,
                request.query,
                tool,
            )
        except Exception as exc:
            logger.warning("Quest chat agent fallback triggered: %s", exc)

        references = self._build_chat_references(tool.last_hits)
        regenerated_from_search = False
        if not references:
            references, context = self._search_chat_context(request, tool)
            regenerated_from_search = bool(references)
        else:
            context = tool.format_hits()

        if not references:
            response = QuestChatResponse(
                answer=QUEST_CHAT_NO_RESULT_MESSAGE,
                references=[],
            )
            self.remember_chat_turn(
                request.thread_id,
                request.query,
                response.answer,
            )
            return response

        if not answer or regenerated_from_search:
            try:
                answer = self._answer_with_context(
                    request.thread_id,
                    request.query,
                    context,
                )
            except Exception as exc:
                logger.warning("Quest chat answer fallback failed: %s", exc)
                answer = "已检索到相关知识片段，但生成回答失败，请稍后重试。"

        response = QuestChatResponse(
            answer=answer,
            references=references,
        )
        self.remember_chat_turn(
            request.thread_id,
            request.query,
            response.answer,
        )
        return response

    def get_chat_context(
        self,
        request: QuestChatRequest,
    ) -> tuple[list[QuestChatReference], str]:
        return self._search_chat_context(request)

    async def astream_answer_with_context(
        self,
        thread_id: str,
        query: str,
        context: str,
    ) -> AsyncIterator[str]:
        llm = get_llm_by_type(AGENT_LLM_MAP["rag"])
        prompt = self._build_chat_answer_prompt(
            thread_id,
            query,
            context,
        )
        async for chunk in llm.astream(
            [
                SystemMessage(content=QUEST_CHAT_FALLBACK_PROMPT),
                HumanMessage(content=prompt),
            ]
        ):
            content = self._normalize_chat_text(getattr(chunk, "content", ""))
            if content:
                yield content

    def remember_chat_turn(
        self,
        thread_id: str,
        user_query: str,
        assistant_answer: str,
    ) -> None:
        normalized_thread_id = self._normalize_memory_thread_id(thread_id)
        if not normalized_thread_id:
            return

        normalized_user_query = str(user_query or "").strip()
        normalized_assistant_answer = str(assistant_answer or "").strip()

        with self._chat_memory_lock:
            memory_bucket = self._chat_memory[normalized_thread_id]
            if normalized_user_query:
                memory_bucket.append({"role": "user", "content": normalized_user_query})
            if normalized_assistant_answer:
                memory_bucket.append(
                    {"role": "assistant", "content": normalized_assistant_answer}
                )

    def score_answer(self, request: QuestScoreRequest) -> QuestScoreResponse:
        llm = get_llm_by_type(AGENT_LLM_MAP["writer"]).with_structured_output(
            RawQuestScore,
            method="json_mode",
        )
        prompt = (
            f"标准答案：\n{request.standard_answer}\n\n"
            f"考生答案：\n{request.exam_answer}\n"
        )

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                generated = llm.invoke(
                    [
                        SystemMessage(content=ANSWER_SCORING_PROMPT),
                        HumanMessage(content=prompt),
                    ]
                )
                return QuestScoreResponse(
                    score=self._normalize_score(generated.score),
                    reason=self._normalize_reason(generated.reason),
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Quest scoring attempt %s failed: %s",
                    attempt + 1,
                    exc,
                )

        raise ValueError(f"Failed to score answer: {last_error}")

    def evaluate_exam(
        self,
        records: list[QuestEvaluationRecord],
    ) -> str:
        if not records:
            raise ValueError("records cannot be empty")

        score_summary = self._summarize_exam_records(records)
        llm = get_llm_by_type(AGENT_LLM_MAP["writer"])
        prompt = self._build_exam_evaluation_prompt(score_summary, records)

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = llm.invoke([SystemMessage(content=prompt)])
                return self._normalize_evaluation_text(response.content)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Quest evaluation attempt %s failed: %s",
                    attempt + 1,
                    exc,
                )

        raise ValueError(f"Failed to evaluate exam: {last_error}")

    def _run_quest_chat_agent(
        self,
        thread_id: str,
        query: str,
        tool: QuestKBSearchTool,
    ) -> str:
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(
            name="quest_chat",
            model=get_llm_by_type(AGENT_LLM_MAP["rag"]),
            tools=[tool],
        )
        result = agent.invoke(
            input={
                "messages": [
                    SystemMessage(content=QUEST_CHAT_AGENT_PROMPT),
                    HumanMessage(content=self._build_chat_user_prompt(thread_id, query)),
                ]
            },
            config={"recursion_limit": 8},
        )
        messages = result.get("messages", []) if isinstance(result, dict) else []
        if not messages:
            return ""
        return self._normalize_chat_text(messages[-1].content)

    def _build_chat_tool(self, request: QuestChatRequest) -> QuestKBSearchTool:
        return QuestKBSearchTool(
            retriever=self.retriever,
            collection_name=request.collection_name,
            file_ids=request.file_ids,
            history_text=self._build_recent_history_text(request.thread_id),
        )

    def _search_chat_context(
        self,
        request: QuestChatRequest,
        tool: QuestKBSearchTool | None = None,
    ) -> tuple[list[QuestChatReference], str]:
        active_tool = tool or self._build_chat_tool(request)
        active_tool.search(request.query)
        references = self._build_chat_references(active_tool.last_hits)
        if not references:
            return [], ""
        return references, active_tool.format_hits()

    def _answer_with_context(
        self,
        thread_id: str,
        query: str,
        context: str,
    ) -> str:
        llm = get_llm_by_type(AGENT_LLM_MAP["rag"])
        prompt = self._build_chat_answer_prompt(
            thread_id,
            query,
            context,
        )

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = llm.invoke(
                    [
                        SystemMessage(content=QUEST_CHAT_FALLBACK_PROMPT),
                        HumanMessage(content=prompt),
                    ]
                )
                answer = self._normalize_chat_text(response.content)
                if answer:
                    return answer
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Quest chat fallback attempt %s failed: %s",
                    attempt + 1,
                    exc,
                )

        raise ValueError(f"Failed to answer quest chat: {last_error}")

    def _build_chat_answer_prompt(
        self,
        thread_id: str,
        query: str,
        context: str,
    ) -> str:
        history_text = self._build_recent_history_text(thread_id)
        prompt_sections: list[str] = []
        if history_text:
            prompt_sections.append(history_text)
        prompt_sections.append(f"用户问题：\n{query}")
        prompt_sections.append(f"检索片段：\n{context}")
        return "\n\n".join(prompt_sections).strip() + "\n"

    def _build_chat_user_prompt(self, thread_id: str, query: str) -> str:
        history_text = self._build_recent_history_text(thread_id)
        if not history_text:
            return query
        return f"{history_text}\n\n当前问题：\n{query}"

    def _build_recent_history_text(self, thread_id: str) -> str:
        history_messages = self._get_recent_history(thread_id)
        if not history_messages:
            return ""

        header = "最近对话历史（仅用于承接上下文，不可替代知识库依据）："
        selected_sections: list[str] = []
        current_length = len(header)
        for message in reversed(history_messages):
            role = "用户" if message["role"] == "user" else "助手"
            content = str(message["content"] or "").strip()
            if not content:
                continue

            section = f"{role}：{content}"
            section_length = len(section) + 1
            if current_length + section_length > QUEST_CHAT_MEMORY_MAX_CHARS:
                break

            selected_sections.append(section)
            current_length += section_length

        if not selected_sections:
            return ""
        selected_sections.reverse()
        return "\n".join([header, *selected_sections])

    def _get_recent_history(self, thread_id: str) -> list[dict[str, str]]:
        normalized_thread_id = self._normalize_memory_thread_id(thread_id)
        if not normalized_thread_id:
            return []

        with self._chat_memory_lock:
            return list(self._chat_memory.get(normalized_thread_id, []))

    def _normalize_memory_thread_id(self, thread_id: str | None) -> str:
        normalized = str(thread_id or "").strip()
        if not normalized or normalized == "__default__":
            return ""
        return normalized

    def _build_chat_references(self, hits: list[Any]) -> list[QuestChatReference]:
        references: list[QuestChatReference] = []
        seen: set[str] = set()

        for hit in hits or []:
            chunk_id = str(getattr(hit, "chunk_id", "") or "").strip()
            if not chunk_id or chunk_id in seen:
                continue

            seen.add(chunk_id)
            references.append(
                QuestChatReference(
                    chunk_id=chunk_id,
                    file_id=str(getattr(hit, "file_id", "") or "").strip(),
                    file_name=self._resolve_hit_file_name(hit),
                    title=self._resolve_hit_title(hit),
                    score=round(float(getattr(hit, "score", 0.0) or 0.0), 4),
                    page_idx=self._normalize_page_indices(
                        getattr(hit, "page_idx", []),
                    ),
                )
            )

        return references

    def _resolve_hit_title(self, hit: Any) -> str:
        for attr_name in ("cur_title", "title", "par_title"):
            value = str(getattr(hit, attr_name, "") or "").strip()
            if value:
                return value
        return ""

    def _resolve_hit_file_name(self, hit: Any) -> str:
        file_path = str(getattr(hit, "file_path", "") or "").strip()
        if file_path:
            return Path(file_path).name or file_path

        file_id = str(getattr(hit, "file_id", "") or "").strip()
        if file_id:
            return file_id
        return "unknown"

    def _normalize_page_indices(self, value: Any) -> list[int]:
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
        return normalized_pages[:10]

    def _normalize_chat_text(self, value: Any) -> str:
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, dict):
                    text = str(
                        item.get("text")
                        or item.get("content")
                        or item.get("output")
                        or ""
                    ).strip()
                else:
                    text = str(item or "").strip()

                if text:
                    parts.append(text)

            return "\n".join(parts).strip()

        return str(value or "").strip()

    def _build_exam_evaluation_prompt(
        self,
        score_summary: QuestEvaluationScoreSummary,
        records: list[QuestEvaluationRecord],
    ) -> str:
        optimized_records = self._build_exam_record_analysis_payload(records)
        template = EVALUATION_PROMPT_PATH.read_text(encoding="utf-8")
        return (
            template.replace(
                "{{score_summary}}",
                json.dumps(score_summary.model_dump(), ensure_ascii=False, indent=2),
            ).replace(
                "{{exam_records}}",
                json.dumps(
                    optimized_records,
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        )

    def _build_exam_record_analysis_payload(
        self,
        records: list[QuestEvaluationRecord],
    ) -> list[dict[str, Any]]:
        grouped_records = self._group_exam_records(records)
        optimized_records: list[dict[str, Any]] = []

        for file_bucket in grouped_records.values():
            chapters: list[dict[str, Any]] = []
            for chapter_bucket in file_bucket["chapters"].values():
                chapters.append(
                    {
                        "title": chapter_bucket["title"],
                        "chapter_summary": self._build_score_metrics(chapter_bucket),
                        "question_performance": chapter_bucket["question_performance"],
                    }
                )

            chapters.sort(
                key=lambda item: (
                    item["chapter_summary"]["score_rate"],
                    item["title"],
                )
            )
            optimized_records.append(
                {
                    "collection_name": file_bucket["collection_name"],
                    "file_id": file_bucket["file_id"],
                    "file_name": file_bucket["file_name"],
                    "file_summary": self._build_score_metrics(file_bucket),
                    "chapters": chapters,
                }
            )

        optimized_records.sort(
            key=lambda item: (
                item["file_summary"]["score_rate"],
                item["file_name"],
            )
        )

        return optimized_records

    def _build_question_performance_payload(
        self,
        question: QuestEvaluationQuestion,
        question_type: str,
    ) -> dict[str, Any]:
        max_score = self._get_max_score(question_type)
        payload: dict[str, Any] = {
            "question_type": question_type,
            "question_name": question.question_name,
            "chunk_ids": question.chunk_ids,
            "score": question.score,
            "max_score": max_score,
            "score_rate": round(float(question.score) / float(max_score), 3),
            "performance": self._describe_question_performance(
                question_type,
                question.score,
            ),
        }

        if question_type == "选择":
            payload["correct_answer"] = self._format_choice_answer(
                question.answer,
                question.options,
            )
            payload["student_answer"] = self._format_choice_answer(
                question.student,
                question.options,
                allow_empty=True,
            )
        else:
            payload["reference_answer"] = self._trim_text(question.answer, 200)
            payload["student_answer"] = self._trim_text(question.student, 200)
            if question.reason:
                payload["improvement_hint"] = self._trim_text(question.reason, 80)

        return payload

    def _describe_question_performance(self, question_type: str, score: int) -> str:
        if question_type == "选择":
            return "答对" if score == self._get_max_score("选择") else "答错"

        if score >= 9:
            return "掌握较好"
        if score >= 6:
            return "部分掌握"
        if score >= 3:
            return "掌握较弱"
        return "明显薄弱"

    def _format_choice_answer(
        self,
        answer: list[int] | str | int | None,
        options: list[str],
        *,
        allow_empty: bool = False,
    ) -> str:
        if allow_empty and self._is_empty_choice_answer(answer):
            return "未作答"

        normalized_answer = self._normalize_choice_answer(answer)
        option_index = normalized_answer[0]
        if 0 <= option_index < len(options):
            return options[option_index]
        return str(option_index)

    def _is_empty_choice_answer(self, value: Any) -> bool:
        if value is None:
            return True

        if isinstance(value, list):
            return len(value) == 0

        if isinstance(value, str):
            return not value.strip()

        return False

    def _group_exam_records(
        self,
        records: list[QuestEvaluationRecord],
    ) -> dict[str, dict[str, Any]]:
        grouped_records: dict[str, dict[str, Any]] = {}

        for record in records:
            file_bucket = grouped_records.setdefault(
                record.file_id,
                self._create_score_bucket(
                    collection_name=record.collection_name,
                    file_id=record.file_id,
                    file_name=record.file_name,
                ),
            )

            for question in record.content:
                chapter_title = self._resolve_question_title(record, question)
                question_type = self._normalize_question_type(question.question_type)
                self._validate_question_score(question_type, question.score)

                max_score = self._get_max_score(question_type)
                self._apply_score_to_bucket(
                    file_bucket,
                    question_type,
                    question.score,
                    max_score,
                )

                chapter_bucket = file_bucket["chapters"].setdefault(
                    chapter_title,
                    self._create_score_bucket(title=chapter_title),
                )
                self._apply_score_to_bucket(
                    chapter_bucket,
                    question_type,
                    question.score,
                    max_score,
                )
                chapter_bucket["question_performance"].append(
                    self._build_question_performance_payload(question, question_type)
                )

        return grouped_records

    def _resolve_question_title(
        self,
        record: QuestEvaluationRecord,
        question: QuestEvaluationQuestion,
    ) -> str:
        title = str(question.title or "").strip()
        if title:
            return title

        legacy_title = str(record.title or "").strip()
        if legacy_title:
            return legacy_title

        raise ValueError("Question title cannot be empty")

    def _create_score_bucket(self, **extra: Any) -> dict[str, Any]:
        return {
            **extra,
            "question_count": 0,
            "score_obtained": 0.0,
            "score_possible": 0.0,
            "choice_total": 0,
            "choice_correct": 0,
            "qa_total": 0,
            "qa_score_sum": 0.0,
            "chapters": {},
            "question_performance": [],
        }

    def _apply_score_to_bucket(
        self,
        bucket: dict[str, Any],
        question_type: str,
        score: int,
        max_score: int,
    ) -> None:
        bucket["question_count"] += 1
        bucket["score_obtained"] += float(score)
        bucket["score_possible"] += float(max_score)

        if question_type == "选择":
            bucket["choice_total"] += 1
            if score == max_score:
                bucket["choice_correct"] += 1
        else:
            bucket["qa_total"] += 1
            bucket["qa_score_sum"] += float(score)

    def _build_score_metrics(self, bucket: dict[str, Any]) -> dict[str, Any]:
        score_possible = float(bucket["score_possible"])
        choice_total = int(bucket["choice_total"])
        qa_total = int(bucket["qa_total"])

        return {
            "question_count": int(bucket["question_count"]),
            "score_obtained": round(float(bucket["score_obtained"]), 2),
            "score_possible": round(score_possible, 2),
            "score_rate": round(float(bucket["score_obtained"]) / score_possible, 3)
            if score_possible > 0
            else 0.0,
            "choice_total": choice_total,
            "choice_correct": int(bucket["choice_correct"]),
            "choice_accuracy": round(float(bucket["choice_correct"]) / choice_total, 3)
            if choice_total > 0
            else 0.0,
            "qa_total": qa_total,
            "qa_average_score": round(float(bucket["qa_score_sum"]) / qa_total, 3)
            if qa_total > 0
            else 0.0,
        }

    def _get_max_score(self, question_type: str) -> int:
        return 2 if question_type == "选择" else 10

    def _list_title_candidates(
        self,
        collection_name: str,
        file_ids: list[str],
    ) -> list[dict[str, str]]:
        results = self.retriever.client.list_curtitle_by_fileid(
            collection_name,
            file_ids,
        )
        candidates: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        for item in results or []:
            title = str(item.get("cur_title", "") or "").strip()
            file_id = str(item.get("file_id", "") or "").strip()
            if not title or not file_id:
                continue
            key = (title, file_id)
            if key in seen:
                continue
            seen.add(key)
            candidates.append({"title": title, "file_id": file_id})

        return candidates

    def _extract_text_chunks(self, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        text_chunks: list[dict[str, Any]] = []
        for chunk in chunks or []:
            bbox_type = str(chunk.get("bbox_type", "") or "").strip().lower()
            if bbox_type not in {"", "text"}:
                continue
            content = str(chunk.get("content", "") or "").strip()
            if not content:
                continue
            text_chunks.append(chunk)

        return sorted(text_chunks, key=self._chunk_sort_key)

    def _chunk_sort_key(self, chunk: dict[str, Any]) -> tuple[int, int, str]:
        page_idx = chunk.get("page_idx", [])
        if isinstance(page_idx, list) and page_idx:
            numeric_pages = [
                int(item) for item in page_idx if isinstance(item, (int, float))
            ]
            first_page = min(numeric_pages) if numeric_pages else 0
        elif isinstance(page_idx, (int, float)):
            first_page = int(page_idx)
        else:
            first_page = 0

        chunk_index = chunk.get("chunk_index", 0)
        if not isinstance(chunk_index, int):
            try:
                chunk_index = int(chunk_index)
            except (TypeError, ValueError):
                chunk_index = 0

        chunk_id = str(chunk.get("chunk_id", "") or "")
        return (first_page, chunk_index, chunk_id)

    def _build_content(self, text_chunks: list[dict[str, Any]]) -> tuple[str, list[str]]:
        sections: list[str] = []
        valid_chunk_ids: list[str] = []
        current_length = 0

        for chunk in text_chunks:
            chunk_id = str(chunk.get("chunk_id", "") or "").strip()
            content = str(chunk.get("content", "") or "").strip()
            if not chunk_id or not content:
                continue

            section = f"[chunk_id={chunk_id}]\n{content}"
            section_length = len(section) + (2 if sections else 0)

            if sections and current_length + section_length > MAX_SOURCE_CHARS:
                break

            if not sections and section_length > MAX_SOURCE_CHARS:
                available = MAX_SOURCE_CHARS - len(f"[chunk_id={chunk_id}]\n")
                truncated_content = content[: max(available, 0)].rstrip()
                section = f"[chunk_id={chunk_id}]\n{truncated_content}"
                section_length = len(section)

            sections.append(section)
            valid_chunk_ids.append(chunk_id)
            current_length += section_length

        return "\n\n".join(sections).strip(), valid_chunk_ids

    def _generate_question_set(
        self,
        title: str,
        content: str,
        valid_chunk_ids: list[str],
    ) -> list:
        llm = get_llm_by_type(AGENT_LLM_MAP["writer"]).with_structured_output(
            RawQuestGeneration,
            method="json_mode",
        )

        prompt = (
            f"标题：{title}\n\n"
            f"可用 chunk_ids：{valid_chunk_ids}\n\n"
            f"正文内容：\n{content}\n"
        )

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                generated = llm.invoke(
                    [
                        SystemMessage(content=QUESTION_GENERATION_PROMPT),
                        HumanMessage(content=prompt),
                    ]
                )
                return self._normalize_questions(
                    generated.questions,
                    set(valid_chunk_ids),
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Quest generation attempt %s failed for title '%s': %s",
                    attempt + 1,
                    title,
                    exc,
                )

        raise ValueError(f"Failed to generate questions: {last_error}")

    def _normalize_questions(
        self,
        questions: list[RawQuestQuestion],
        valid_chunk_ids: set[str],
    ) -> list:
        choice_questions = []
        qa_questions = []

        for item in questions:
            normalized_type = self._normalize_question_type(item.question_type)
            if normalized_type == "选择":
                choice_questions.append(
                    self._normalize_choice_question(item, valid_chunk_ids)
                )
            elif normalized_type == "问答":
                qa_questions.append(self._normalize_qa_question(item, valid_chunk_ids))

        if len(choice_questions) < MCQ_COUNT or len(qa_questions) < QA_COUNT:
            raise ValueError("Model output does not contain 4 choice questions and 1 QA question")

        return choice_questions[:MCQ_COUNT] + qa_questions[:QA_COUNT]

    def _normalize_question_type(self, value: str) -> str:
        normalized = str(value or "").strip()
        if normalized in {"选择", "选择题", "单选", "单选题"}:
            return "选择"
        if normalized in {"问答", "问答题", "简答", "简答题"}:
            return "问答"
        raise ValueError(f"Unsupported question_type: {value}")

    def _normalize_choice_question(
        self,
        item: RawQuestQuestion,
        valid_chunk_ids: set[str],
    ):
        question_name = self._trim_text(item.question_name, 50)
        if not question_name:
            raise ValueError("Choice question_name cannot be empty")

        options = [self._trim_text(option, 20) for option in item.options or []]
        options = [option for option in options if option]
        if len(options) != 4:
            raise ValueError("Choice question must contain exactly 4 options")

        chunk_ids = self._normalize_chunk_ids(item.chunk_ids, valid_chunk_ids)
        answer = self._normalize_choice_answer(item.answer)
        return build_question_payload(
            question_type="选择",
            question_name=question_name,
            options=options,
            chunk_ids=chunk_ids,
            answer=answer,
        )

    def _normalize_qa_question(
        self,
        item: RawQuestQuestion,
        valid_chunk_ids: set[str],
    ):
        question_name = self._trim_text(item.question_name, 100)
        if not question_name:
            raise ValueError("QA question_name cannot be empty")

        if item.options not in (None, []):
            raise ValueError("QA question options must be []")

        chunk_ids = self._normalize_chunk_ids(item.chunk_ids, valid_chunk_ids)
        answer = self._trim_text(str(item.answer or ""), 200)
        if not answer:
            raise ValueError("QA answer cannot be empty")

        return build_question_payload(
            question_type="问答",
            question_name=question_name,
            options=[],
            chunk_ids=chunk_ids,
            answer=answer,
        )

    def _normalize_chunk_ids(
        self,
        value: list[str] | str,
        valid_chunk_ids: set[str],
    ) -> list[str]:
        if isinstance(value, str):
            raw_chunk_ids = [value]
        else:
            raw_chunk_ids = value or []

        chunk_ids: list[str] = []
        seen: set[str] = set()
        for item in raw_chunk_ids:
            chunk_id = str(item or "").strip()
            if not chunk_id or chunk_id in seen:
                continue
            if chunk_id not in valid_chunk_ids:
                continue
            chunk_ids.append(chunk_id)
            seen.add(chunk_id)

        if not chunk_ids:
            raise ValueError("Each question must contain at least one valid chunk_id")

        return chunk_ids

    def _summarize_exam_records(
        self,
        records: list[QuestEvaluationRecord],
    ) -> QuestEvaluationScoreSummary:
        grouped_records = self._group_exam_records(records)
        total_questions = 0
        total_score_obtained = 0.0
        total_score_possible = 0.0
        choice_total = 0
        choice_correct = 0
        qa_total = 0
        qa_score_sum = 0.0
        chapter_performance: list[QuestEvaluationChapterSummary] = []

        for file_bucket in grouped_records.values():
            total_questions += int(file_bucket["question_count"])
            total_score_obtained += float(file_bucket["score_obtained"])
            total_score_possible += float(file_bucket["score_possible"])
            choice_total += int(file_bucket["choice_total"])
            choice_correct += int(file_bucket["choice_correct"])
            qa_total += int(file_bucket["qa_total"])
            qa_score_sum += float(file_bucket["qa_score_sum"])

            for chapter_bucket in file_bucket["chapters"].values():
                chapter_metrics = self._build_score_metrics(chapter_bucket)
                chapter_performance.append(
                    QuestEvaluationChapterSummary(
                        file_name=file_bucket["file_name"],
                        title=chapter_bucket["title"],
                        total_questions=chapter_metrics["question_count"],
                        score_obtained=chapter_metrics["score_obtained"],
                        score_possible=chapter_metrics["score_possible"],
                        score_rate=chapter_metrics["score_rate"],
                    )
                )

        chapter_performance.sort(key=lambda item: (item.score_rate, item.title))
        score_rate = (
            round(total_score_obtained / total_score_possible, 3)
            if total_score_possible > 0
            else 0.0
        )
        choice_accuracy = (
            round(choice_correct / choice_total, 3)
            if choice_total > 0
            else 0.0
        )
        qa_average_score = (
            round(qa_score_sum / qa_total, 3)
            if qa_total > 0
            else 0.0
        )

        return QuestEvaluationScoreSummary(
            total_questions=total_questions,
            total_score_obtained=round(total_score_obtained, 2),
            total_score_possible=round(total_score_possible, 2),
            score_rate=score_rate,
            choice_total=choice_total,
            choice_correct=choice_correct,
            choice_accuracy=choice_accuracy,
            qa_total=qa_total,
            qa_average_score=qa_average_score,
            chapter_performance=chapter_performance,
        )

    def _validate_question_score(self, question_type: str, score: int) -> None:
        if question_type == "选择" and score not in {0, 2}:
            raise ValueError("Choice question score must be 0 or 2")
        if question_type == "问答" and not 0 <= score <= 10:
            raise ValueError("QA question score must be between 0 and 10")

    def _normalize_choice_answer(self, value: Any) -> list[int]:
        if isinstance(value, int):
            if 0 <= value <= 3:
                return [value]
            raise ValueError(f"Choice answer index out of range: {value}")

        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, int) and 0 <= first <= 3:
                return [first]
            if isinstance(first, str):
                parsed = self._parse_choice_answer_str(first)
                return [parsed]

        if isinstance(value, str):
            return [self._parse_choice_answer_str(value)]

        raise ValueError(f"Invalid choice answer: {value}")

    def _parse_choice_answer_str(self, value: str) -> int:
        normalized = str(value or "").strip().upper()
        if normalized.isdigit():
            idx = int(normalized)
            if 0 <= idx <= 3:
                return idx

        mapping = {"A": 0, "B": 1, "C": 2, "D": 3}
        if normalized in mapping:
            return mapping[normalized]

        raise ValueError(f"Invalid choice answer string: {value}")

    def _trim_text(self, value: Any, max_length: int) -> str:
        text = str(value or "").strip()
        if len(text) <= max_length:
            return text
        return text[:max_length].rstrip()

    def _normalize_score(self, value: Any) -> int:
        try:
            raw_score = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid score value: {value}") from exc

        if raw_score < 0:
            raw_score = 0.0
        elif raw_score > 10:
            raw_score = 10.0

        return int(raw_score + 0.5)

    def _normalize_reason(self, value: Any) -> str:
        reason = str(value or "").strip()
        if not reason:
            raise ValueError("Invalid score reason")
        if len(reason) <= 50:
            return reason
        return reason[:50].rstrip()

    def _normalize_evaluation_text(self, value: Any) -> str:
        if isinstance(value, list):
            text = "".join(str(item) for item in value).strip()
        else:
            text = str(value or "").strip()

        if not text:
            raise ValueError("Invalid evaluation text")

        normalized_lines: list[str] = []
        blank_count = 0
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                blank_count += 1
                if blank_count <= 1:
                    normalized_lines.append("")
                continue

            blank_count = 0
            normalized_lines.append(line)

        return "\n".join(normalized_lines).strip()
