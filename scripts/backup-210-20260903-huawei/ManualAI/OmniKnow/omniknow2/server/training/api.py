from uuid import UUID

from fastapi import APIRouter, Depends, BackgroundTasks

from core.dependencies import RequestContext, authorize
from schemas import ResponseModel
from training.schema import CreateCourseRequest, GeneratePaperRequest, SubmitExamRequest
from training.service import TrainingService


router = APIRouter()

# 新建课程并异步生成考题
@router.post("/spaces/{space_id}/courses")
async def create_course(
        space_id: UUID,
        payload: CreateCourseRequest,
        background_tasks: BackgroundTasks,
        ctx: RequestContext = Depends(authorize("training:write"))
):
    # payload_dict = payload.model_dump()
    svc = TrainingService(ctx)
    data = await svc.create_course(space_id, payload)
    background_tasks.add_task(
        svc.generate_and_insert_questions,
        space_id,
        payload.kbase_id,
        UUID(data.get("uuid", "")),
        payload.doc_id,
        payload.question_number,
    )
    return ResponseModel.success(data)


@router.get("/spaces/{space_id}/courses/{course_id}")
async def get_course_detail(
        space_id: UUID,
        course_id: UUID,
        ctx: RequestContext = Depends(authorize())
):
    svc = TrainingService(ctx)
    data = await svc.get_course_detail(space_id, course_id)
    return ResponseModel.success(data)


# 删除课程
@router.delete("/spaces/{space_id}/courses/{course_id}")
async def delete_course(
        space_id: UUID,
        course_id: UUID,
        ctx: RequestContext = Depends(authorize("training:write"))
):
    svc = TrainingService(ctx)
    data = await svc.delete_course(space_id, course_id)
    return ResponseModel.success(data)


# 获取课程列表
@router.get("/spaces/{space_id}/courses")
async def list_courses(
        space_id: UUID,
        ctx: RequestContext = Depends(authorize("training:read"))
):
    svc = TrainingService(ctx)
    data = await svc.list_courses(space_id)
    return ResponseModel.success(data)


# 获取题库列表，支持分页
@router.get("/spaces/{space_id}/courses/{course_id}/questions")
async def list_questions(
        space_id: UUID,
        course_id: UUID,
        page: int = 1,
        size: int = 10,
        ctx: RequestContext = Depends(authorize("training:read"))
):
    svc = TrainingService(ctx)
    data = await svc.list_questions(space_id, course_id, page, size)
    return ResponseModel.success(data)


# 按题型抽取试题并生成试卷
@router.post("/spaces/{space_id}/courses/{course_id}/paper")
async def generate_paper(
        space_id: UUID,
        course_id: UUID,
        payload: GeneratePaperRequest,
        ctx: RequestContext = Depends(authorize("training:write"))
):
    svc = TrainingService(ctx)
    result = await svc.generate_paper(space_id, course_id, payload)
    return ResponseModel.success(result)


@router.get("/spaces/{space_id}/courses/{course_id}/paper/{paper_id}")
async def get_paper(
        space_id: UUID,
        course_id: UUID,
        paper_id: str,
        ctx: RequestContext = Depends(authorize("training:read"))
):
    svc = TrainingService(ctx)
    data = await svc.get_paper(space_id, course_id, paper_id)
    return ResponseModel.success(data)


# 提交考试结果（JSON），异步批改，立即返回考试记录 ID
@router.post("/spaces/{space_id}/courses/{course_id}/results")
async def upload_results(
        space_id: UUID,
        course_id: UUID,
        payload: SubmitExamRequest,
        background_tasks: BackgroundTasks,
        ctx: RequestContext = Depends(authorize("training:write"))
):
    svc = TrainingService(ctx)
    exam_session_id = await svc.submit_exam(space_id, course_id, payload)
    background_tasks.add_task(
        TrainingService.grade_exam,
        course_id,
        exam_session_id,
        [item.model_dump() for item in payload.answers],
    )
    return ResponseModel.success({"exam_session_id": str(exam_session_id)})


# 获取考试结果
@router.get("/spaces/{space_id}/courses/{course_id}/results/{exam_session_id}")
async def get_exam_result(
        space_id: UUID,
        course_id: UUID,
        exam_session_id: UUID,
        ctx: RequestContext = Depends(authorize())
):
    svc = TrainingService(ctx)
    data = await svc.get_exam_result(space_id, course_id, exam_session_id)
    return ResponseModel.success(data)


# 考试评价（异步），调用外部 AI 服务对考试记录生成 Markdown 评价并入库
@router.post("/spaces/{space_id}/courses/{course_id}/results/{exam_session_id}/evaluate")
async def evaluate_exam(
        space_id: UUID,
        course_id: UUID,
        exam_session_id: UUID,
        background_tasks: BackgroundTasks,
        ctx: RequestContext = Depends(authorize())
):
    background_tasks.add_task(
        TrainingService.evaluate_exam,
        course_id,
        exam_session_id,
    )
    return ResponseModel.success({"message": "考试评价任务已提交"})


# 学员画像：可访问课程数、考试次数、平均分、考试评价（按倒序）
@router.get("/spaces/{space_id}/exams/profile")
async def get_student_profile(
        space_id: UUID,
        ctx: RequestContext = Depends(authorize("training:read"))
):
    svc = TrainingService(ctx)
    data = await svc.get_student_profile(space_id)
    return ResponseModel.success(data)


# 获取考生考试记录
@router.get("/spaces/{space_id}/exams/records")
async def list_exam_records(
        space_id: UUID,
        page: int = 1,
        page_size: int = 10,
        ctx: RequestContext = Depends(authorize("training:read"))
):
    svc = TrainingService(ctx)
    data = await svc.list_exam_records(space_id, page, page_size)
    return ResponseModel.success(data)


@router.get("/spaces/{space_id}/exams/{exam_session_id}")
async def get_exam_record(
        space_id: UUID,
        exam_session_id: UUID,
        ctx: RequestContext = Depends(authorize("training:read"))
):
    svc = TrainingService(ctx)
    data = await svc.get_exam_record_detail(space_id, exam_session_id)
    return ResponseModel.success(data)
