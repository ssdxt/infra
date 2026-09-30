import json
from typing import Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
from uuid import UUID

from db.models.rag import KnowledgeBase
from memory.model import Memory


def _parse_kbase_ids(raw_kbase_ids) -> list[UUID]:
    if not raw_kbase_ids:
        return []

    if isinstance(raw_kbase_ids, str):
        try:
            raw_kbase_ids = json.loads(raw_kbase_ids)
        except json.JSONDecodeError:
            raw_kbase_ids = [raw_kbase_ids]

    if not isinstance(raw_kbase_ids, list):
        raw_kbase_ids = [raw_kbase_ids]

    kbase_ids = []
    for kbase_id in raw_kbase_ids:
        try:
            kbase_ids.append(kbase_id if isinstance(kbase_id, UUID) else UUID(str(kbase_id)))
        except (TypeError, ValueError):
            continue

    return kbase_ids


def _format_kbase_list(kbase_ids: list[UUID], kbase_map: dict[UUID, dict]) -> list[dict]:
    return [
        kbase_map.get(kbase_id, {
            "uuid": kbase_id,
            "name": None
        })
        for kbase_id in kbase_ids
    ]


class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_memory(self, space_id: UUID, kbase_ids: list[UUID], user_id: UUID, conversation_id: UUID, message_id: UUID, messages: list, feedback: int, comment: str) -> Memory:
        orm_obj = Memory(
            space_id=space_id,
            kbase_id=kbase_ids,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            messages=json.dumps(messages),
            feedback=feedback,
            comment=comment
        )
        self.session.add(orm_obj)
        await self.session.commit()
        await self.session.flush()
        await self.session.refresh(orm_obj)
        return orm_obj

    async def get_memory_list(
        self, space_id: UUID, user_id: UUID, limit: int, offset: int
    ):
        result = await self.session.execute(
            select(Memory)
            .where(and_(Memory.space_id == space_id, Memory.user_id == user_id))
            .order_by(desc(Memory.created_at))
            .limit(limit)
            .offset(offset)
        )
        mem = result.scalars().all()

        memory_kbase_ids = {m.uuid: _parse_kbase_ids(m.kbase_id) for m in mem}
        all_kbase_ids = {
            kbase_id
            for kbase_ids in memory_kbase_ids.values()
            for kbase_id in kbase_ids
        }
        kbase_map = {}
        if all_kbase_ids:
            kbase_map = await self._get_kbase_map(space_id, all_kbase_ids)

        return [
            {
                "uuid": m.uuid,
                "space_id": m.space_id,
                "conversation_id": m.conversation_id,
                "message_id": m.message_id,
                "kbase": _format_kbase_list(memory_kbase_ids[m.uuid], kbase_map),
                "feedback": m.feedback,
                "comment": m.comment,
                "created_at": m.created_at.strftime("%Y-%m-%d %H:%M:%S")
            }
            for m in mem
        ]

    async def count_memories(self, space_id: UUID, user_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count(Memory.uuid))
            .where(and_(Memory.space_id == space_id, Memory.user_id == user_id))
        )
        return result.scalar() or 0

    async def get_memory_by_id(
        self, space_id: UUID, memory_id: UUID, user_id: UUID
    ) -> Optional[Memory]:
        result = await self.session.execute(
            select(Memory).where(
                and_(
                    Memory.uuid == memory_id,
                    Memory.space_id == space_id,
                    Memory.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def format_memory_detail(self, space_id: UUID, memory: Memory) -> dict:
        kbase_ids = _parse_kbase_ids(memory.kbase_id)
        kbase_map = await self._get_kbase_map(space_id, set(kbase_ids)) if kbase_ids else {}
        msgs = json.loads(memory.messages)
        msgs.sort(key=lambda x: x.get("timestamp", 0))
        return {
            "uuid": memory.uuid,
            "space_id": memory.space_id,
            "conversation_id": memory.conversation_id,
            "kbase": _format_kbase_list(kbase_ids, kbase_map),
            "user_id": memory.user_id,
            "message_id": memory.message_id,
            "messages": msgs,
            "feedback": memory.feedback,
            "comment": memory.comment,
            "created_at": memory.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": memory.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        }

    async def delete_memory(self, memory: Memory) -> None:
        await self.session.delete(memory)
        await self.session.commit()

    async def _get_kbase_map(self, space_id: UUID, kbase_ids: set[UUID]) -> dict[UUID, dict]:
        kbase_result = await self.session.execute(
            select(KnowledgeBase.uuid, KnowledgeBase.name).where(
                KnowledgeBase.space_id == space_id,
                KnowledgeBase.uuid.in_(kbase_ids)
            )
        )
        return {
            kbase.uuid: {
                "uuid": kbase.uuid,
                "name": kbase.name
            }
            for kbase in kbase_result.all()
        }

    async def get_memory_by_message_id(self, space_id: UUID, conversation_id: UUID, message_id: UUID, user_id: UUID) -> Optional[Memory]:
        result = await self.session.execute(
            select(Memory).where(
                and_(
                    Memory.space_id == space_id,
                    Memory.conversation_id == conversation_id,
                    Memory.user_id == user_id,
                    Memory.message_id == message_id
                )
            )
        )
        return result.scalar_one_or_none()