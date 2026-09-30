from uuid import UUID

from fastapi import APIRouter, Depends

from core.dependencies import RequestContext, authorize
from schemas import MessageRecordSchema, ResponseModel, ConversationTitleUpdateSchema, ConversationCreateSchema
from services import ChatService


router = APIRouter()


@router.put("/spaces/{space_id}/conversations")
async def create_conversation(
        space_id: UUID,
        payload: ConversationCreateSchema,
        ctx: RequestContext = Depends(authorize("chat:write"))
):
    """新建会话"""
    chat_service = ChatService(ctx)
    res = await chat_service.create_conversation(
        space_id=space_id,
        kbase_ids=payload.kbase_ids
    )
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/conversations")
async def list_conversations(
        space_id: UUID,
        ctx: RequestContext = Depends(authorize("chat:read"))
):
    """会话列表"""
    chat_service = ChatService(ctx)
    res = await chat_service.get_conversations_list(
        space_id=space_id
    )
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/conversations/{conversation_id}")
async def get_conversation(
        space_id: UUID,
        conversation_id: UUID,
        ctx: RequestContext = Depends(authorize("chat:read"))
):
    """会话详情"""
    chat_service = ChatService(ctx)
    res = await chat_service.get_conversation_detail(
        space_id=space_id,
        conversation_id=conversation_id
    )
    return ResponseModel.success(res)


@router.post("/spaces/{space_id}/conversations/{conversation_id}/messages")
async def insert_message_to_conversation(
        space_id: UUID,
        conversation_id: UUID,
        msg: MessageRecordSchema,
        ctx: RequestContext = Depends(authorize("chat:write"))
):
    """将消息存入数据库"""
    chat_service = ChatService(ctx)
    res = await chat_service.insert_message_to_conversation(space_id, conversation_id, msg)
    return ResponseModel.success(res)


@router.patch("/spaces/{space_id}/conversations/{conversation_id}/title")
async def update_conversation_title(
        space_id: UUID,
        conversation_id: str,
        title_update_schema: ConversationTitleUpdateSchema,
        ctx: RequestContext = Depends(authorize("chat:write"))
):
    """更新会话标题"""
    chat_service = ChatService(ctx)
    res = await chat_service.update_conversation_title(space_id, conversation_id, title_update_schema.title)
    return ResponseModel.success(res)


@router.delete("/spaces/{space_id}/conversations/{conversation_id}")
async def delete_conversation(
        space_id: UUID,
        conversation_id: UUID,
        ctx: RequestContext = Depends(authorize("chat:write"))
):
    """删除会话"""
    chat_service = ChatService(ctx)
    await chat_service.delete_conversation(space_id, conversation_id)
    return ResponseModel.success()