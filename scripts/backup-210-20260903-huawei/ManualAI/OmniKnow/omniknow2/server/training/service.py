import math
import random
from uuid import UUID

from chunks.service import ChunkService
from db.models.rag import KnowledgeBase
from repository.user import UserRepository
from services import DocumentService, KbaseService
from utils.log import logger
from core.dependencies import RequestContext
from training.repository import TrainingRepository
from training.schema import QusetionType, GeneratePaperRequest, CreateCourseRequest, SubmitExamRequest
from training.exception import CourseNotFoundError, QusetionsNotExisted, PaperNotFoundError


class TrainingService:

    @staticmethod
    def _split_question_number(question_number: int) -> tuple[int, int]:
        short_answer_count = question_number // 5
        choice_count = question_number - short_answer_count
        return choice_count, short_answer_count

    @staticmethod
    def _build_objective_reason(is_correct: int | None) -> str:
        if is_correct == 1:
            return "回答正确"
        if is_correct == 0:
            return "回答错误"
        return "题目尚未完成判分"

    @staticmethod
    def _build_subjective_reason(answer, answer_meta: dict) -> str:
        reason = (answer_meta or {}).get("reason")
        if reason:
            return reason
        if answer.judge_status == "pending":
            return "简答题待评分"
        return f"简答题得分 {answer.score} 分"

    @staticmethod
    def _parse_answer_meta(answer) -> dict:
        return answer.answer_json if isinstance(answer.answer_json, dict) else {}

    @staticmethod
    def _build_choice_answer_indexes(answer_value: str, options: list) -> list[int]:
        if not answer_value:
            return []

        key_to_index = {
            (opt.option_key or "").upper(): idx
            for idx, opt in enumerate(options)
        }
        answer_keys = [
            item.strip().upper()
            for item in answer_value.split(",")
            if item.strip()
        ]
        indexes = [key_to_index[key] for key in answer_keys if key in key_to_index]
        return sorted(indexes)

    @staticmethod
    async def _build_exam_evaluation_payload(repo: TrainingRepository, course_id: UUID, exam_session_id: UUID) -> list[dict]:
        exam_session = await repo.get_exam_session(exam_session_id)
        if not exam_session:
            logger.error(f"[TrainingService] 考试评价失败，考试记录不存在: session={exam_session_id}")
            return []

        paper = await repo.get_paper(exam_session.paper_id)
        answers = await repo.get_exam_answers(exam_session_id)
        if not answers:
            logger.error(f"[TrainingService] 考试评价失败，考试答案不存在: session={exam_session_id}")
            return []

        collection_name = ""
        file_id = ""
        file_name = ""
        content = []

        for answer in answers:
            question = await repo.get_question(course_id, answer.question_id)
            if not question:
                continue

            options = await repo.get_options(question.uuid)
            extra = question.extra or {}
            source_title = extra.get("source_title") or (paper.title if paper else "")

            # 从第一道有效题目中提取外层字段
            if not content:
                collection_name = extra.get("collection_name") or ""
                file_id = extra.get("file_id") or ""
                if file_id:
                    resource = await repo.get_resource(UUID(file_id))
                    file_name = resource.name if resource else ""
                else:
                    file_name = ""

            answer_meta = TrainingService._parse_answer_meta(answer)
            if question.type == QusetionType.short_answer:
                student_answer = answer.answer_text or ""
                correct_answer = extra.get("standard_answer", "")
                # reason = TrainingService._build_subjective_reason(answer, answer_meta)
                question_type = "问答"
            else:
                raw_answer = answer_meta.get("answer", "")
                student_answer = TrainingService._build_choice_answer_indexes(raw_answer, options)
                correct_answer = sorted(
                    idx for idx, opt in enumerate(options) if opt.is_correct
                )
                # reason = answer_meta.get("reason") or TrainingService._build_objective_reason(answer.is_correct)
                question_type = "选择"

            content.append({
                "title": source_title,
                "question_type": question_type,
                "question_name": question.stem,
                "options": [opt.option_content for opt in options],
                "chunk_ids": extra.get("chunk_ids", []),
                "student": student_answer,
                "answer": correct_answer,
                "score": answer.score,
                # "reason": reason,
            })

        return [{
            "collection_name": collection_name,
            "file_id": file_id,
            "file_name": file_name,
            "content": content,
        }]

    def __init__(self, ctx: RequestContext):
        self.db = ctx.db
        self.user = ctx.user
        self.repo = TrainingRepository(self.db)
        self.user_repo = UserRepository(self.db)
        self.kbase_service = KbaseService(ctx)
        self.doc_service = DocumentService(ctx)
        self.chunk_service = ChunkService(self.db)

    async def create_course(self, space_id: UUID, course_info: CreateCourseRequest):
        question_number = course_info.question_number
        if question_number == 0:
            chunks = await self.chunk_service.get_chunks_count(course_info.doc_id)
            choice_count = 4 * (8 + int((chunks ** 0.5) / 5))  # 基于文档内容量估算选择题数量
            short_answer_count = 1 * (8 + int((chunks ** 0.5) / 5))  # 基于文档内容量估算简答题数量
            question_number = choice_count + short_answer_count
        else:
            choice_count, short_answer_count = self._split_question_number(question_number)
        course_payload = {
            "title": course_info.name,
            "description": course_info.description,
            "resource_id": course_info.doc_id,
            "kbase_id": course_info.kbase_id,
            "extra": {
                "question_number": question_number,
                "choice_count": choice_count,
                "short_answer_count": short_answer_count,
            },
        }
        # async with self.db.begin():
        course = await self.repo.create_course(space_id, course_payload)
        return {
            "uuid": str(course.uuid),
            "title": course.title,
            "question_number": question_number,
            "choice_count": choice_count,
            "short_answer_count": short_answer_count,
            "message": "课程创建成功，考题生成任务已提交",
        }

    async def get_course_detail(self, space_id: UUID, course_id: UUID):
        course = await self.repo.get_courses_detail(space_id, course_id)
        if not course:
            raise CourseNotFoundError(course_id)

        resource = await self.doc_service.get_resource_detail(space_id, course.kbase_id, course.resource_id)
        if resource["processed_oss_key"] != "1" and resource.get("processed_oss_key"):
            processed_oss_path = resource.get("processed_oss_path")
        else:
            processed_oss_path = resource.get("path")
        question_counts = await self.repo.get_question_counts_by_courses([course.uuid])
        stats = question_counts.get(course.uuid, {})
        return {
            "uuid": str(course.uuid),
            "title": course.title,
            "kbase_id": str(course.kbase_id),
            "description": course.description,
            "logo": course.logo,
            "processed_oss_path": processed_oss_path,
            "created_at": course.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "total_questions": stats.get("total", 0),
            "choice_count": stats.get("choice_count", 0),
            "short_answer_count": stats.get("short_answer_count", 0),
        }

    async def delete_course(self, space_id: UUID, course_id: UUID):
        async with self.db.begin():
            ok = await self.repo.delete_course(course_id)
        return ok

    async def list_courses(self, space_id: UUID):
        courses = await self.repo.get_courses(space_id)
        course_ids = [c.uuid for c in courses]
        question_counts = await self.repo.get_question_counts_by_courses(course_ids)
        return {
            "items": [
                {
                    "uuid": str(c.uuid),
                    "title": c.title,
                    "kbase_id": str(c.kbase_id),
                    "description": c.description,
                    "logo": c.logo,
                    "created_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "total_questions": question_counts.get(c.uuid, {}).get("total", 0),
                    "choice_count": question_counts.get(c.uuid, {}).get("choice_count", 0),
                    "short_answer_count": question_counts.get(c.uuid, {}).get("short_answer_count", 0),
                }
                for c in courses
            ]
        }

    async def get_paper(self, space_id: UUID, course_id: UUID, paper_id: str):
        paper = await self.repo.get_paper(UUID(paper_id))
        if not paper:
            return None
        pqs = await self.repo.get_paper_questions(paper.uuid)
        questions = []
        for pq in pqs:
            q = await self.repo.get_question(course_id, pq.question_id)
            if not q:
                continue
            opts = await self.repo.get_options(q.uuid)
            questions.append({
                "uuid": str(q.uuid),
                "type": q.type,
                "stem": q.stem,
                "analysis": q.analysis,
                "difficulty": q.difficulty,
                "score": pq.score,
                "options": [
                    {
                        "key": opt.option_key,
                        "content": opt.option_content,
                        "is_correct": opt.is_correct,
                    }
                    for opt in opts
                ],
            })
        return {
            "uuid": str(paper.uuid),
            "title": paper.title,
            "description": paper.description,
            "duration_minutes": paper.duration_minutes,
            "total_score": paper.total_score,
            "questions": questions,
        }

    async def get_exam_result(self, space_id: UUID, course_id: UUID, exam_session_id: UUID):
        es = await self.repo.get_exam_session(exam_session_id)
        if not es:
            return None
        answers = await self.repo.get_exam_answers(es.uuid)

        answer_list = []
        for a in answers:
            item = {
                "question_id": str(a.question_id),
                "question_type": a.question_type,
                "answer_text": a.answer_text,
                "answer_json": a.answer_json,
                "is_correct": a.is_correct,
                "score": a.score,
                "judge_status": a.judge_status,
            }
            question = await self.repo.get_question(course_id, a.question_id)
            if question and question.type == QusetionType.short_answer:
                item["standard_answer"] = (question.extra or {}).get("standard_answer", "")
            elif question:
                options = await self.repo.get_options(question.uuid)
                correct_keys = sorted(o.option_key for o in options if o.is_correct)
                item["standard_answer"] = ",".join(correct_keys)
            else:
                item["standard_answer"] = ""
            answer_list.append(item)

        return {
            "uuid": str(es.uuid),
            "paper_id": str(es.paper_id),
            "user_id": str(es.user_id),
            "status": es.status,
            "objective_score": es.objective_score,
            "subjective_score": es.subjective_score,
            "total_score": es.total_score,
            "submit_time": es.submit_time.strftime("%Y-%m-%d %H:%M:%S") if es.submit_time else None,
            "evaluation": es.evaluation,
            "answers": answer_list,
        }

    async def list_exam_records(self, space_id: UUID, page: int, size: int):
        sessions, total = await self.repo.get_exam_sessions(space_id, page, size)

        # 批量查询用户姓名
        user_ids = list({es.user_id for es in sessions})
        user_name_map: dict = {}
        for uid in user_ids:
            u = await self.user_repo.get(uid)
            user_name_map[uid] = u.name if u else ""

        return {
            "total": total,
            "page": page,
            "page_size": size,
            "items": [
                {
                    "uuid": str(es.uuid),
                    "paper_id": str(es.paper_id),
                    "user_id": str(es.user_id),
                    "user_name": user_name_map.get(es.user_id, ""),
                    "course_id": str(es.course_id),
                    "course_title": es.title,
                    "status": es.status,
                    "objective_score": es.objective_score,
                    "subjective_score": es.subjective_score,
                    "total_score": es.total_score,
                    "start_time": es.start_time.strftime("%Y-%m-%d %H:%M:%S") if es.start_time else None,
                    "submit_time": es.submit_time.strftime("%Y-%m-%d %H:%M:%S") if es.submit_time else None,
                }
                for es in sessions
            ],
        }

    async def get_student_profile(self, space_id: UUID):
        """学员画像：可访问课程数、考试次数、各项平均分、按倒序的考试评价。"""
        user_id = self.user.uuid
        courses = await self.repo.get_courses(space_id)
        stats = await self.repo.get_student_profile_stats(space_id, user_id)
        sessions = await self.repo.get_user_exam_evaluations(space_id, user_id)
        return {
            "course_count": len(courses),
            "exam_count": stats["exam_count"],
            "training_count": 34,
            "avg_total_score": round(stats["avg_total_score"], 2),
            "avg_objective_score": round(stats["avg_objective_score"], 2),
            "avg_subjective_score": round(stats["avg_subjective_score"], 2),
            "evaluations": [
                {
                    "exam_session_id": str(es.uuid),
                    "paper_id": str(es.paper_id),
                    "total_score": es.total_score,
                    "objective_score": es.objective_score,
                    "subjective_score": es.subjective_score,
                    "submit_time": es.submit_time.strftime("%Y-%m-%d %H:%M:%S") if es.submit_time else None,
                    "evaluation": es.evaluation,
                }
                for es in sessions
            ],
        }

    async def get_exam_record_detail(self, space_id: UUID, exam_session_id: UUID):
        """获取单条考试记录详情，包含答题明细。"""
        es = await self.repo.get_exam_session(exam_session_id)
        if not es:
            return None
        u = await self.user_repo.get(es.user_id)
        answers = await self.repo.get_exam_answers(exam_session_id)
        course_id = es.course_id if hasattr(es, "course_id") else None
        # Try to get course_id from paper if not attached
        if course_id is None:
            paper = await self.repo.get_paper(es.paper_id)
            course_id = paper.course_id if paper else None

        answer_list = []
        for a in answers:
            item = {
                "question_id": str(a.question_id),
                "question_type": a.question_type,
                "answer_text": a.answer_text,
                "answer_json": a.answer_json,
                "is_correct": a.is_correct,
                "score": a.score,
                "judge_status": a.judge_status,
                "standard_answer": "",
            }
            if course_id:
                question = await self.repo.get_question(course_id, a.question_id)
                if question and question.type == QusetionType.short_answer:
                    item["standard_answer"] = (question.extra or {}).get("standard_answer", "")
                elif question:
                    options = await self.repo.get_options(question.uuid)
                    correct_keys = sorted(o.option_key for o in options if o.is_correct)
                    item["standard_answer"] = ",".join(correct_keys)
            answer_list.append(item)

        return {
            "uuid": str(es.uuid),
            "paper_id": str(es.paper_id),
            "user_id": str(es.user_id),
            "user_name": u.name if u else "",
            "course_id": str(course_id) if course_id else None,
            "status": es.status,
            "objective_score": es.objective_score,
            "subjective_score": es.subjective_score,
            "total_score": es.total_score,
            "start_time": es.start_time.strftime("%Y-%m-%d %H:%M:%S") if es.start_time else None,
            "submit_time": es.submit_time.strftime("%Y-%m-%d %H:%M:%S") if es.submit_time else None,
            "evaluation": es.evaluation,
            "answers": answer_list,
        }

    async def list_questions(self, space_id: UUID, course_id: UUID, page: int, size: int):
        items, total = await self.repo.get_questions(space_id, course_id, page, size)
        if len(items) == 0:
            raise QusetionsNotExisted("课程不存在或考题生成失败，暂无考题可供展示")
        return {
            "total": total,
            "page": page,
            "size": size,
            "items": [
                {
                    "uuid": str(item["question"].uuid),
                    "type": item["question"].type,
                    "stem": item["question"].stem,
                    "analysis": item["question"].analysis,
                    "difficulty": item["question"].difficulty,
                    "default_score": item["question"].default_score,
                    "options": [
                        {
                            "key": opt.option_key,
                            "content": opt.option_content,
                            "is_correct": opt.is_correct,
                        }
                        for opt in item["options"]
                    ],
                }
                for item in items
            ],
        }

    async def generate_and_insert_questions(
            self,
            space_id: UUID,
            kbase_id: UUID,
            course_id: UUID,
            resource_id: UUID,
            question_number: int,
    ):
        """
        后台任务：调用外部 AI 服务批量生成考题并入库。
        每次调用返回 4 道选择题 + 1 道简答题，根据所需数量批量请求后截取。
        """
        from db.session import async_session
        from training.client import TrainingClient

        client = TrainingClient()

        kbase  = await self.kbase_service.get(space_id, kbase_id)
        course = await self.repo.get_course_by_id(course_id)
        if not course:
            raise CourseNotFoundError(course_id)
        chunks = await self.chunk_service.get_chunks_count(resource_id)

        # 每次调用产出 5 道题（4 选择 + 1 简答），按总需求量估算轮次
        if question_number == 0:
            total_calls = 8 + int((chunks ** 0.5) / 5)
        else:
            total_calls = math.ceil(question_number / 5) if question_number > 0 else 0

        logger.info(f"[TrainingService] chunks数量为{chunks}，预计调用外部服务 {total_calls} 轮 (resource={resource_id})")
        choice_questions = []
        short_answer_questions = []

        option_keys = ["A", "B", "C", "D", "E", "F", "G", "H"]

        for i in range(total_calls):
            try:
                logger.info(f"[TrainingService] 正在生成考题: 第 {i + 1}/{total_calls} 轮 (resource={resource_id})")
                result = await client.generate_questions(kbase.collection_name, [str(resource_id)])
            except Exception as e:
                logger.error(f"[TrainingService] 第 {i + 1}/{total_calls} 次考题生成请求失败: {e}")
                continue

            for item in result.get("content", []):
                q_type_raw = item.get("question_type", "")
                if q_type_raw == "选择":
                    # 解析选择题
                    answer_indices = item.get("answer", [])
                    if len(answer_indices) > 1:
                        q_type = QusetionType.multiple_choice
                    else:
                        q_type = QusetionType.single_choice

                    options = []
                    for idx, opt_text in enumerate(item.get("options", [])):
                        key = option_keys[idx] if idx < len(option_keys) else str(idx)
                        options.append({
                            "key": key,
                            "content": opt_text,
                            "is_correct": 1 if idx in answer_indices else 0,
                        })

                    choice_questions.append({
                        "course_id": course_id,
                        "type": q_type,
                        "stem": item.get("question_name", ""),
                        "default_score": 2,
                        "options": options,
                        "extra": {
                            "chunk_ids": item.get("chunk_ids", []),
                            "collection_name": kbase.collection_name,
                            "file_id": result.get("file_id"),
                            "source_title": result.get("title"),
                        },
                    })

                elif q_type_raw == "问答":
                    # 解析简答题
                    short_answer_questions.append({
                        "course_id": course_id,
                        "type": QusetionType.short_answer,
                        "stem": item.get("question_name", ""),
                        "default_score": 10,
                        "options": [],
                        "extra": {
                            "chunk_ids": item.get("chunk_ids", []),
                            "collection_name": kbase.collection_name,
                            "file_id": result.get("file_id"),
                            "source_title": result.get("title"),
                            "standard_answer": item.get("answer", ""),
                        },
                    })

        # 合并并入库
        all_questions = choice_questions + short_answer_questions
        created = []

        async with async_session() as session:
            async with session.begin():
                repo = TrainingRepository(session)
                for q_data in all_questions:
                    q = await repo.create_question(space_id, q_data)
                    created.append(str(q.uuid))

        logger.info(f"[TrainingService] 考题生成入库完成: "
                     f"共入库 {len(created)} 题")

    async def generate_paper(self, space_id: UUID, course_id: UUID, req: GeneratePaperRequest):
        """
        按题型从题库中随机抽取指定数量的题目，同时生成试卷入库，
        返回试卷 ID 与完整题目列表。
        当某类型题目不足时，取该类型全部题目，并在 shortages 中标注差额。
        """
        type_counts = req.type_counts
        question_ids_input = req.question_ids

        shortages = []
        sampled_questions = []  # [(Questions, opts)]

        async with self.db.begin():
            if question_ids_input:
                # 显式指定题目 ID
                for qid in question_ids_input:
                    q = await self.repo.get_question(course_id, UUID(qid))
                    if q:
                        opts = await self.repo.get_options(q.uuid)
                        sampled_questions.append((q, opts))
            else:
                # 按题型随机抽取
                for q_type, requested in type_counts.items():
                    all_qs = await self.repo.get_questions_by_type(space_id, course_id, q_type)
                    available = len(all_qs)

                    if available == 0:
                        shortages.append({
                            "type": q_type,
                            "requested": requested,
                            "actual": 0,
                            "shortage": requested,
                        })
                        continue

                    if available < requested:
                        shortages.append({
                            "type": q_type,
                            "requested": requested,
                            "actual": available,
                            "shortage": requested - available,
                        })
                        sampled = all_qs
                    else:
                        sampled = random.sample(all_qs, requested)

                    for q in sampled:
                        opts = await self.repo.get_options(q.uuid)
                        sampled_questions.append((q, opts))

            # 构建题目列表并生成试卷
            question_list = [
                {"uuid": q.uuid, "score": q.default_score}
                for q, _ in sampled_questions
            ]
            paper = await self.repo.create_paper(space_id, course_id, req, question_list)

            # 生成试卷即开考：在同事务内创建 ExamSession 并写入快照，
            # 后续提交/批改一律以该 ExamSession 为准，避免前端二次传入 paper_id 导致判题错误。
            snapshot_json = {
                "paper_id": str(paper.uuid),
                "course_id": str(course_id),
                "space_id": str(space_id),
                "score_map": {str(q["uuid"]): q.get("score", 1) for q in question_list},
                "question_ids": [str(q["uuid"]) for q in question_list],
                "total_score": paper.total_score,
            }
            exam_session = await self.repo.create_exam_session(
                space_id=space_id,
                paper_id=paper.uuid,
                user_id=self.user.uuid,
                status="ongoing",
                snapshot_json=snapshot_json,
            )

        # 组装返回数据
        questions_out = []
        for (q, opts), idx in zip(sampled_questions, range(len(sampled_questions))):
            questions_out.append({
                "uuid": str(q.uuid),
                "type": q.type,
                "stem": q.stem,
                "analysis": q.analysis,
                "difficulty": q.difficulty,
                "score": q.default_score,
                "options": [
                    {
                        "key": opt.option_key,
                        "content": opt.option_content,
                        "is_correct": opt.is_correct,
                    }
                    for opt in opts
                ],
            })

        return {
            "uuid": str(paper.uuid),
            "exam_session_id": str(exam_session.uuid),
            "title": paper.title,
            "description": paper.description,
            "duration_minutes": paper.duration_minutes,
            "total_score": paper.total_score,
            "shortages": shortages if shortages else None,
            "questions": questions_out,
        }

    async def submit_exam(self, space_id: UUID, course_id: UUID, payload: SubmitExamRequest) -> UUID:
        """提交考试：复用 generate_paper 阶段创建的 ongoing ExamSession；
        若不存在（兼容历史调用方）则现场创建。所有路径都先校验 paper 归属。"""
        paper_id = payload.paper_id
        user_id = self.user.uuid

        async with self.db.begin():
            paper = await self.repo.get_paper_in_scope(space_id, course_id, paper_id)
            if not paper:
                raise PaperNotFoundError(paper_id)

            existing = await self.repo.get_ongoing_exam_session(user_id, paper_id)
            if existing:
                await self.repo.mark_exam_session_submitted(existing.uuid)
                return existing.uuid

            exam_session = await self.repo.create_exam_session(
                space_id=space_id,
                paper_id=paper_id,
                user_id=user_id,
                status="submitted",
            )
        return exam_session.uuid

    @staticmethod
    async def grade_exam(course_id: UUID, exam_session_id: UUID, answers_input: list):
        """后台批改任务：批改客观题，简答题调用外部 AI 服务自动评分。

        以 ExamSession 中的 paper_id 为唯一可信来源，优先使用考试时落库的
        snapshot_json 构造 score_map，避免试卷被改动/删除导致 TOCTOU 错判。
        """
        from db.session import async_session
        from training.client import TrainingClient

        client = TrainingClient()

        async with async_session() as session:
            async with session.begin():
                repo = TrainingRepository(session)

                exam_session = await repo.get_exam_session(exam_session_id)
                if not exam_session:
                    logger.error(f"[TrainingService] 批改失败，考试记录不存在: session={exam_session_id}")
                    return

                snapshot = exam_session.snapshot_json if isinstance(exam_session.snapshot_json, dict) else None
                snapshot_score_map = (snapshot or {}).get("score_map") or {}
                if snapshot_score_map:
                    score_map = {str(qid): int(score) for qid, score in snapshot_score_map.items()}
                else:
                    pqs = await repo.get_paper_questions(exam_session.paper_id)
                    score_map = {str(pq.question_id): pq.score for pq in pqs}

                answers = []
                obj_score = 0
                subj_score = 0

                for item in answers_input:
                    qid = item["question_id"]
                    answer = item.get("answer", "").strip()
                    q = await repo.get_question(course_id, UUID(qid))
                    if not q:
                        continue

                    q_score = score_map.get(qid, q.default_score)
                    judge_status = "auto_graded"
                    is_correct = None
                    earned = 0
                    answer_meta = {"answer": answer}

                    if q.type in (QusetionType.single_choice, QusetionType.true_false):
                        opts = await repo.get_options(q.uuid)
                        correct = next((o.option_key for o in opts if o.is_correct), None)
                        is_correct = 1 if answer.upper() == (correct or "").upper() else 0
                        earned = q_score if is_correct else 0
                        obj_score += earned
                        answer_meta["reason"] = TrainingService._build_objective_reason(is_correct)

                    elif q.type == QusetionType.multiple_choice:
                        opts = await repo.get_options(q.uuid)
                        correct_keys = sorted(o.option_key.upper() for o in opts if o.is_correct)
                        answer_keys = sorted(a.strip().upper() for a in answer.split(",") if a.strip())
                        is_correct = 1 if answer_keys == correct_keys else 0
                        earned = q_score if is_correct else 0
                        obj_score += earned
                        answer_meta["reason"] = TrainingService._build_objective_reason(is_correct)

                    elif q.type == QusetionType.short_answer:
                        standard_answer = (q.extra or {}).get("standard_answer", "")
                        if answer and standard_answer:
                            try:
                                score_result = await client.score_short_answer(answer, standard_answer)
                                earned = score_result.get("score", 0)
                                is_correct = 1 if earned > 0 else 0
                                judge_status = "auto_graded"
                                subj_score += earned
                                answer_meta["reason"] = score_result.get("reason")
                            except Exception as e:
                                logger.error(f"[TrainingService] 简答题评分失败 (question={qid}): {e}")
                                judge_status = "pending"
                                answer_meta["reason"] = "简答题待评分"
                        else:
                            judge_status = "auto_graded"
                            earned = 0
                            is_correct = 0
                            answer_meta["reason"] = "未作答或缺少标准答案"

                    answers.append({
                        "question_id": q.uuid,
                        "question_type": q.type,
                        "answer_text": answer if q.type == QusetionType.short_answer else None,
                        "answer_json": answer_meta,
                        "is_correct": is_correct,
                        "score": earned,
                        "judge_status": judge_status,
                    })

                await repo.create_exam_answers(exam_session_id, answers)
                await repo.update_exam_session_scores(exam_session_id, obj_score, subj_score, obj_score + subj_score)

    @staticmethod
    async def evaluate_exam(course_id: UUID, exam_session_id: UUID):
        """后台任务：根据考试记录组装评价请求，调用外部 AI 服务后写回 ExamSession"""
        from db.session import async_session
        from training.client import TrainingClient

        async with async_session() as session:
            repo = TrainingRepository(session)
            exam_records = await TrainingService._build_exam_evaluation_payload(repo, course_id, exam_session_id)

        if not exam_records:
            logger.error(f"[TrainingService] 考试评价请求未发送，缺少可用考试数据: session={exam_session_id}")
            return

        try:
            client = TrainingClient()
            evaluation = await client.evaluate_exam(exam_records)
        except Exception as e:
            logger.error(f"[TrainingService] 考试评价请求失败 (session={exam_session_id}): {e}")
            return

        async with async_session() as session:
            async with session.begin():
                repo = TrainingRepository(session)
                await repo.update_exam_evaluation(exam_session_id, evaluation)

        logger.info(f"[TrainingService] 考试评价已入库: session={exam_session_id}, "
                     f"内容长度={len(evaluation)} 字符")
