from fastapi import HTTPException

from core.config import settings
from core.dependencies import RequestContext
from embed import EmbedClient
from memory.error import MemoryNotExistedError, MemoryExistedError
from repository import ChatRepository
from vector import MilvusClient
from memory.repository import MemoryRepository
from memory.schema import MemoryCreateSchema
from utils import logger

from pydantic import UUID4, UUID7
from uuid import UUID
import json


async def get_round_messages(prev_messages):
    """
    获取往前n轮消息记录（一轮: role=user + role=agent）
    """
    msgs = []
    user_msg = None
    for msg in reversed(prev_messages):
        if msg["role"] == "agent":
            if user_msg:
                msgs.append(user_msg)
                user_msg = None
            msgs.append(msg)
        elif msg["role"] == "user":
            user_msg = msg
        if len(msgs) >= settings.memory.limit * 2:  # 最多获取2倍轮次的对话
            break
    return list(msgs)


class MemoryService:
    def __init__(self, ctx: RequestContext):
        self.user_id = ctx.user.uuid

        # self.embed_client = EmbedClient()
        self.vector_client = MilvusClient()
        self.repo = MemoryRepository(ctx.db)
        self.chat_repo = ChatRepository(ctx.db)

    async def insert_feedback_memory(self, space_id: UUID4, conversation_id: UUID, memory: MemoryCreateSchema):
        mem = await self.repo.get_memory_by_message_id(space_id, conversation_id, memory.message_id, self.user_id)
        if mem:
            logger.info(f"已存在相似的记忆记录，消息ID：{mem.message_id}")
            raise MemoryExistedError(mem.uuid)

        # 1. 在数据库中存储记忆记录
        logger.info(f"开始创建记忆，空间ID：{space_id}，会话ID：{conversation_id}，用户ID：{self.user_id}")
        conversation = await self.chat_repo.get_conversation(space_id, str(conversation_id), self.user_id)
        if not conversation:
            raise HTTPException(status_code=404, detail=f"会话ID {conversation_id} 不存在")

        message_id = memory.message_id
        prev_messages = await self.chat_repo.get_prev_messages_by_id(space_id, conversation_id, message_id)
        logger.info(f"获取到往前的消息记录，共{len(prev_messages)}条", )

        msgs = await get_round_messages(prev_messages)
        logger.info(f"共获取到 {len(msgs)} 轮对话", )

        memory = await self.repo.create_memory(space_id, conversation.kbase_ids, self.user_id, conversation_id, message_id, msgs, memory.feedback, memory.comment)
        #todo 2. 将记忆相关的消息进行向量化，并存储到向量数据库中，方便后续检索
        return {
            "uuid": memory.uuid,
            "space_id": memory.space_id,
            "conversation_id": memory.conversation_id,
            "kbase_ids": json.loads(memory.kbase_id) if memory.kbase_id else [],
            "feedback": memory.feedback,
            "comment": memory.comment,
            "created_at": memory.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }

    async def get_memory_list(self, space_id: UUID4, page: int = 1, page_size: int = 20):
        offset = (page - 1) * page_size
        items = await self.repo.get_memory_list(space_id, self.user_id, page_size, offset)
        total = await self.repo.count_memories(space_id, self.user_id)
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_memory_detail(self, space_id: UUID4, memory_id: UUID4):
        memory = await self.repo.get_memory_by_id(space_id, memory_id, self.user_id)
        if not memory:
            raise MemoryNotExistedError(memory_id)
        return await self.repo.format_memory_detail(space_id, memory)

    async def delete_memory(self, space_id: UUID4, memory_id: UUID4):
        memory = await self.repo.get_memory_by_id(space_id, memory_id, self.user_id)
        if not memory:
            raise MemoryNotExistedError(memory_id)
        await self.repo.delete_memory(memory)
        # TODO: 同步删除向量库中对应的 embedding
