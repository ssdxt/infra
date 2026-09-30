from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from db.models.rag import Resource
from training.models import Course, Questions, QuestionOptions, Paper, PaperQuestions, ExamSession, ExamAnswer
from training.schema import QusetionType, GeneratePaperRequest


class TrainingRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_questions(self, space_id: UUID, course_id: UUID, page: int, size: int):
        offset = (page - 1) * size
        result = await self.session.execute(
            select(Questions)
            .join(Course, Course.uuid == Questions.course_id)
            .where(Questions.space_id == space_id,
                   Questions.course_id == course_id,
                   Questions.status == 1,
                   Course.uuid == course_id,
                   Course.status == 1)
            .offset(offset)
            .limit(size)
        )
        questions = result.scalars().all()

        count_result = await self.session.execute(
            select(func.count(Questions.uuid))
            .join(Course, Course.uuid == Questions.course_id)
            .where(
                Questions.space_id == space_id,
                Questions.course_id == course_id,
                Questions.status == 1,
                Course.uuid == course_id,
                Course.status == 1)
        )
        total = count_result.scalar()

        # load options for each question
        items = []
        for q in questions:
            opts = await self.get_options(q.uuid)
            items.append({"question": q, "options": opts})

        return items, total

    async def get_options(self, question_id: UUID):
        result = await self.session.execute(
            select(QuestionOptions)
            .where(QuestionOptions.question_id == question_id)
            .order_by(QuestionOptions.sort)
        )
        return result.scalars().all()

    async def create_question(self, space_id: UUID, data: dict) -> Questions:
        q = Questions(
            space_id=space_id,
            course_id=data["course_id"],
            type=data["type"],
            stem=data["stem"],
            analysis=data.get("analysis"),
            difficulty=data.get("difficulty", 1),
            default_score=data.get("default_score", 1),
            extra=data.get("extra"),
        )
        self.session.add(q)
        await self.session.flush()

        for i, opt in enumerate(data.get("options", [])):
            option = QuestionOptions(
                question_id=q.uuid,
                option_key=opt["key"],
                option_content=opt["content"],
                is_correct=opt.get("is_correct", 0),
                sort=i,
            )
            self.session.add(option)

        await self.session.flush()
        return q

    async def get_questions_by_type(self, space_id: UUID, course_id: UUID, question_type: str):
        """获取指定空间下某一题目类型的所有有效题目"""
        result = await self.session.execute(
            select(Questions)
            .where(
                Questions.space_id == space_id,
                Questions.course_id == course_id,
                Questions.type == question_type,
                Questions.status == 1,
            )
        )
        return result.scalars().all()

    async def get_all_question_ids(self, space_id: UUID):
        result = await self.session.execute(
            select(Questions.uuid, Questions.default_score)
            .where(Questions.space_id == space_id, Questions.status == 1)
        )
        return result.all()

    async def create_paper(self, space_id: UUID, course_id: UUID, req: GeneratePaperRequest, question_ids: list) -> Paper:
        total_score = sum(q.get("score", 1) for q in question_ids) if question_ids else 0
        paper = Paper(
            space_id=space_id,
            course_id=course_id,
            title=req.title,
            description=req.description,
            duration_minutes=req.duration_minutes,
            question_ids=[str(q["uuid"]) for q in question_ids],
            total_score=total_score,
        )
        self.session.add(paper)
        await self.session.flush()

        for i, q in enumerate(question_ids):
            pq = PaperQuestions(
                paper_id=paper.uuid,
                question_id=q["uuid"],
                score=q.get("score", 1),
                sort=i,
            )
            self.session.add(pq)

        await self.session.flush()
        return paper

    async def get_paper(self, paper_id: UUID):
        result = await self.session.execute(
            select(Paper).where(Paper.uuid == paper_id)
        )
        return result.scalar_one_or_none()

    async def get_paper_questions(self, paper_id: UUID):
        result = await self.session.execute(
            select(PaperQuestions)
            .where(PaperQuestions.paper_id == paper_id)
            .order_by(PaperQuestions.sort)
        )
        return result.scalars().all()

    async def get_question(self, course_id: UUID, question_id: UUID):
        result = await self.session.execute(
            select(Questions).where(
                Questions.course_id == course_id,
                Questions.uuid == question_id)
        )
        return result.scalar_one_or_none()

    async def create_exam_session(
        self,
        space_id: UUID,
        paper_id: UUID,
        user_id: UUID,
        status: str = "submitted",
        snapshot_json: dict | None = None,
        submit_time: datetime | None = None,
    ) -> ExamSession:
        now = datetime.now()
        session = ExamSession(
            space_id=space_id,
            paper_id=paper_id,
            user_id=user_id,
            status=status,
            start_time=now,
            submit_time=submit_time if submit_time is not None else (now if status == "submitted" else None),
            snapshot_json=snapshot_json,
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def get_paper_in_scope(self, space_id: UUID, course_id: UUID, paper_id: UUID) -> Paper | None:
        result = await self.session.execute(
            select(Paper).where(
                Paper.uuid == paper_id,
                Paper.space_id == space_id,
                Paper.course_id == course_id,
                Paper.status == 1,
            )
        )
        return result.scalar_one_or_none()

    async def get_ongoing_exam_session(self, user_id: UUID, paper_id: UUID) -> ExamSession | None:
        """查找当前用户在指定试卷上未提交的考试记录（最近一条）。"""
        result = await self.session.execute(
            select(ExamSession)
            .where(
                ExamSession.user_id == user_id,
                ExamSession.paper_id == paper_id,
                ExamSession.status == "ongoing",
            )
            .order_by(ExamSession.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def mark_exam_session_submitted(self, exam_session_id: UUID) -> ExamSession | None:
        result = await self.session.execute(
            select(ExamSession).where(ExamSession.uuid == exam_session_id)
        )
        es = result.scalar_one_or_none()
        if es:
            es.status = "submitted"
            es.submit_time = datetime.now()
            await self.session.flush()
        return es

    async def create_exam_answers(self, exam_session_id: UUID, answers: list):
        for ans in answers:
            ea = ExamAnswer(
                exam_session_id=exam_session_id,
                question_id=ans["question_id"],
                question_type=ans["question_type"],
                answer_text=ans.get("answer_text"),
                answer_json=ans.get("answer_json"),
                is_correct=ans.get("is_correct"),
                score=ans.get("score", 0),
                judge_status=ans.get("judge_status", "pending"),
            )
            self.session.add(ea)
        await self.session.flush()

    # --- Course ---

    async def create_course(self, space_id: UUID, data: dict) -> Course:
        course = Course(
            space_id=space_id,
            kbase_id=data["kbase_id"],
            resource_id=data["resource_id"],
            title=data["title"],
            description=data.get("description"),
            logo=data.get("logo"),
            extra=data.get("extra"),
        )
        self.session.add(course)
        await self.session.flush()
        await self.session.commit()
        return course

    async def get_courses_detail(self, space_id: UUID, course_id: UUID):
        result = await self.session.execute(
            select(Course)
            .where(Course.space_id == space_id, Course.uuid == course_id, Course.status == 1)
        )
        return result.scalar_one_or_none()

    async def get_course_by_id(self, course_id: UUID):
        result = await self.session.execute(
            select(Course)
            .where(Course.uuid == course_id, Course.status == 1)
        )
        return result.scalar_one_or_none()

    async def get_courses(self, space_id: UUID):
        result = await self.session.execute(
            select(Course)
            .where(Course.space_id == space_id, Course.status == 1)
            .order_by(Course.created_at.desc())
        )
        return result.scalars().all()

    async def get_question_counts_by_courses(self, course_ids: list[UUID]) -> dict:
        """批量查询课程题目数量统计，返回 {course_id: {total, choice_count, short_answer_count}}"""
        if not course_ids:
            return {}
        result = await self.session.execute(
            select(
                Questions.course_id,
                Questions.type,
                func.count(Questions.uuid)
            )
            .where(
                Questions.course_id.in_(course_ids),
                Questions.status == 1,
            )
            .group_by(Questions.course_id, Questions.type)
        )
        rows = result.all()

        counts = {}
        for course_id, q_type, cnt in rows:
            if course_id not in counts:
                counts[course_id] = {"total": 0, "choice_count": 0, "short_answer_count": 0}
            counts[course_id]["total"] += cnt
            if q_type in ("single_choice", "multiple_choice", "true_false"):
                counts[course_id]["choice_count"] += cnt
            elif q_type == "short_answer":
                counts[course_id]["short_answer_count"] += cnt
        return counts

    async def delete_course(self, course_id: UUID) -> bool:
        result = await self.session.execute(
            select(Course).where(Course.uuid == course_id)
        )
        course = result.scalar_one_or_none()
        if not course:
            return False

        # 获取该课程下所有 paper_ids
        paper_result = await self.session.execute(
            select(Paper.uuid).where(Paper.course_id == course_id)
        )
        paper_ids = [row[0] for row in paper_result.all()]

        if paper_ids:
            # 获取这些 paper 下所有 exam_session_ids
            session_result = await self.session.execute(
                select(ExamSession.uuid).where(ExamSession.paper_id.in_(paper_ids))
            )
            session_ids = [row[0] for row in session_result.all()]

            if session_ids:
                # 删除 ExamAnswer
                await self.session.execute(
                    delete(ExamAnswer).where(ExamAnswer.exam_session_id.in_(session_ids))
                )
                # 删除 ExamSession
                await self.session.execute(
                    delete(ExamSession).where(ExamSession.uuid.in_(session_ids))
                )

            # 删除 PaperQuestions
            await self.session.execute(
                delete(PaperQuestions).where(PaperQuestions.paper_id.in_(paper_ids))
            )
            # 删除 Paper
            await self.session.execute(
                delete(Paper).where(Paper.course_id == course_id)
            )

        # 获取该课程下所有 question_ids
        question_result = await self.session.execute(
            select(Questions.uuid).where(Questions.course_id == course_id)
        )
        question_ids = [row[0] for row in question_result.all()]

        if question_ids:
            # 删除 QuestionOptions
            await self.session.execute(
                delete(QuestionOptions).where(QuestionOptions.question_id.in_(question_ids))
            )
            # 删除 Questions
            await self.session.execute(
                delete(Questions).where(Questions.course_id == course_id)
            )

        # 删除 Course
        await self.session.execute(
            delete(Course).where(Course.uuid == course_id)
        )
        await self.session.flush()
        return True

    # --- ExamSession / ExamAnswer ---

    async def get_exam_session(self, exam_session_id: UUID) -> ExamSession | None:
        result = await self.session.execute(
            select(ExamSession).where(ExamSession.uuid == exam_session_id)
        )
        return result.scalar_one_or_none()

    async def get_exam_answers(self, exam_session_id: UUID):
        result = await self.session.execute(
            select(ExamAnswer).where(ExamAnswer.exam_session_id == exam_session_id)
        )
        return result.scalars().all()

    async def get_exam_sessions(self, space_id: UUID, page: int, size: int):
        # Join through Paper and Course to get course_id and course title
        offset = (page - 1) * size
        result = await self.session.execute(
            select(ExamSession, Paper.course_id, Course.title)
            .join(Paper, Paper.uuid == ExamSession.paper_id)
            .join(Course, Course.uuid == Paper.course_id)
            .where(ExamSession.space_id == space_id)
            .order_by(ExamSession.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        rows = result.all()
        # Attach course_id and title as dynamic attributes for service layer convenience
        sessions = []
        for es, course_id, course_title in rows:
            es.course_id = course_id
            es.title = course_title
            sessions.append(es)

        count_result = await self.session.execute(
            select(func.count(ExamSession.uuid))
            .join(Paper, Paper.uuid == ExamSession.paper_id)
            .where(ExamSession.space_id == space_id)
        )
        total = count_result.scalar()
        return sessions, total

    async def get_student_profile_stats(self, space_id: UUID, user_id: UUID) -> dict:
        """统计当前用户在指定空间下的考试次数与平均分（仅统计已评分的考试）。"""
        result = await self.session.execute(
            select(
                func.count(ExamSession.uuid),
                func.avg(ExamSession.total_score),
                func.avg(ExamSession.objective_score),
                func.avg(ExamSession.subjective_score),
            ).where(
                ExamSession.space_id == space_id,
                ExamSession.user_id == user_id,
                ExamSession.status == "graded",
            )
        )
        count, avg_total, avg_obj, avg_subj = result.one()
        return {
            "exam_count": count or 0,
            "avg_total_score": float(avg_total) if avg_total is not None else 0.0,
            "avg_objective_score": float(avg_obj) if avg_obj is not None else 0.0,
            "avg_subjective_score": float(avg_subj) if avg_subj is not None else 0.0,
        }

    async def get_user_exam_evaluations(self, space_id: UUID, user_id: UUID):
        """按倒序返回当前用户在指定空间下、已生成评价的考试记录。"""
        result = await self.session.execute(
            select(ExamSession)
            .where(
                ExamSession.space_id == space_id,
                ExamSession.user_id == user_id,
                ExamSession.evaluation.isnot(None),
            )
            .order_by(ExamSession.created_at.desc())
        )
        return result.scalars().all()

    async def update_exam_session_scores(self, exam_session_id: UUID, obj_score: int, subj_score: int, total: int):
        result = await self.session.execute(
            select(ExamSession).where(ExamSession.uuid == exam_session_id)
        )
        es = result.scalar_one_or_none()
        if es:
            es.objective_score = obj_score
            es.subjective_score = subj_score
            es.total_score = total
            es.status = "graded"
            await self.session.flush()

    async def get_resource(self, resource_id: UUID) -> Resource | None:
        result = await self.session.execute(
            select(Resource).where(Resource.uuid == resource_id)
        )
        return result.scalar_one_or_none()

    async def update_exam_evaluation(self, exam_session_id: UUID, evaluation: str):
        result = await self.session.execute(
            select(ExamSession).where(ExamSession.uuid == exam_session_id)
        )
        es = result.scalar_one_or_none()
        if es:
            es.evaluation = evaluation
            await self.session.flush()
