from fastapi import APIRouter, Depends, Query
from uuid import UUID

from core.dependencies import RequestContext, authorize
from memory.schema import MemoryCreateSchema
from schemas import ResponseModel
from memory.service import MemoryService

router = APIRouter()


@router.get("/spaces/{space_id}/memory")
async def get_memory_list(
        space_id: UUID,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=1000),
        ctx: RequestContext = Depends(authorize("memory:view"))
):
    """
    获取空间下的记忆列表
    """
    memory_service = MemoryService(ctx)
    res = await memory_service.get_memory_list(space_id, page, page_size)
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/memory/{memory_id}")
async def get_memory_detail(
        space_id: UUID,
        memory_id: UUID,
        ctx: RequestContext = Depends(authorize("memory:view"))
):
    """
    获取记忆详情
    """
    memory_service = MemoryService(ctx)
    res = await memory_service.get_memory_detail(space_id, memory_id)
    return ResponseModel.success(res)


@router.post("/spaces/{space_id}/conversations/{conversation_id}/memory")
async def create_memory(
        space_id: UUID,
        conversation_id: UUID,
        memory_info: MemoryCreateSchema,
        ctx: RequestContext = Depends(authorize("memory:write"))
):
    """
    插入反馈记忆
    """
    memory_service = MemoryService(ctx)
    res = await memory_service.insert_feedback_memory(space_id, conversation_id, memory_info)
    return ResponseModel.success(res)


@router.delete("/spaces/{space_id}/memory/{memory_id}")
async def delete_memory(
        space_id: UUID,
        memory_id: UUID,
        ctx: RequestContext = Depends(authorize("memory:write"))
):
    """
    删除记忆
    """
    memory_service = MemoryService(ctx)
    await memory_service.delete_memory(space_id, memory_id)
    return ResponseModel.success()