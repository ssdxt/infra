from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.dependencies import RequestContext, authorize
from schemas import ResponseModel
from report.service import ReportService
from report.schema import ReportCreateSchema, ReportUpdateSchema

router = APIRouter()


# 创建报告
@router.post("/spaces/{space_id}/reports/")
async def create_report(
        space_id: UUID,
        report_info: ReportCreateSchema,
        ctx: RequestContext = Depends(authorize("report:write"))
):
    svc = ReportService(ctx)
    data = await svc.create_report(space_id, report_info)
    return ResponseModel.success(data)


# 获取报告列表
@router.get("/spaces/{space_id}/reports/")
async def list_reports(
    space_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None),
    ctx: RequestContext = Depends(authorize("report:read"))
):
    svc = ReportService(ctx)
    data = await svc.list_reports(space_id, page, page_size, keyword)
    return ResponseModel.success(data)


# 获取单个报告
@router.get("/spaces/{space_id}/reports/{report_id}/")
async def get_report(
        space_id: UUID,
        report_id: UUID,
        ctx: RequestContext = Depends(authorize("report:read"))
):
    svc = ReportService(ctx)
    data = await svc.get_report(space_id, report_id)
    return ResponseModel.success(data)


# 更新报告
@router.patch("/spaces/{space_id}/reports/{report_id}/")
async def update_report(
        space_id: UUID,
        report_id: UUID,
        report_info: ReportUpdateSchema,
        ctx: RequestContext = Depends(authorize("report:write"))
):
    svc = ReportService(ctx)
    data = await svc.update_report(space_id, report_id, report_info)
    return ResponseModel.success(data)


# 删除报告
@router.delete("/spaces/{space_id}/reports/{report_id}/")
async def delete_report(
        space_id: UUID,
        report_id: UUID,
        ctx: RequestContext = Depends(authorize("report:write"))
):
    svc = ReportService(ctx)
    data = await svc.delete_report(space_id, report_id)
    return ResponseModel.success(data)
