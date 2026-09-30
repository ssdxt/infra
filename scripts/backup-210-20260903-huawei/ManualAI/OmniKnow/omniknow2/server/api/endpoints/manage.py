from fastapi import APIRouter, Depends, UploadFile, File
from uuid import UUID

from core.dependencies import authorize, RequestContext
from schemas import ResponseModel, ResourceGrantSchema
from services.manage import ManageService


router = APIRouter()


@router.get("/manage/statistic/spaces/{space_id}/users")
async def get_statistic_user_data(
        space_id: UUID,
        ctx: RequestContext = Depends(authorize("admin:view"))
):
    """
    获取用户角色列表
    """
    manager = ManageService(ctx)
    res = await manager.get_total_user_count(space_id)
    return ResponseModel.success(res)


@router.get("/manage/statistic/spaces/{space_id}")
async def get_statistic_space_data(
        space_id: UUID,
        ctx: RequestContext = Depends(authorize("admin:view"))
):
    """
    获取空间统计数据
    """
    manager = ManageService(ctx)
    res = await manager.get_total_kbase_count(space_id)
    return ResponseModel.success(res)


@router.patch("/manage/spaces/{space_id}/users/{user_id}/grant")
async def grant_user_resource_access(
        space_id: UUID,
        user_id: UUID,
        resource_grant: ResourceGrantSchema,
        ctx: RequestContext = Depends(authorize("admin:manage"))
):
    """
    授予用户资源权限
    """
    manager = ManageService(ctx)
    await manager.grant_resource_access(space_id, user_id)
    return ResponseModel.success()

