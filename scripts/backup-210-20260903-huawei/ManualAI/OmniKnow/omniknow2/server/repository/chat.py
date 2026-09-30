import json
import time
from uuid import UUID

from typing import Sequence

from core.config import settings
from db.models.rag import Conversation, ChatMessage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from exceptions.errors.resource import ResourceNotExistedError, ConversationNotExistedError, MessageNotExistedError
from memory.error import MessageRoleError


class ChatRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_conversation(self, space_id: UUID, conversation_id: str, user_id: UUID) -> Conversation:
        result = await self.session.execute(
            select(Conversation).where(
                Conversation.uuid == conversation_id,
                Conversation.space_id == space_id,
                Conversation.user_id == user_id,
                Conversation.status == "active"
            )
        )
        conversation = result.scalar_one_or_none()
        return conversation

    async def get_conversations_list(self, space_id: UUID, user_id: UUID) -> Sequence[Conversation]:
        result = await self.session.execute(
            select(Conversation).where(
                Conversation.space_id == space_id,
                Conversation.user_id == user_id,
                Conversation.status == "active"
            ).order_by(Conversation.created_at.desc())
        )
        conversations = result.scalars().all()
        return conversations

    async def create_conversation(self, space_id: UUID, user_id: UUID, title: str, kbase_ids: list[UUID]) -> Conversation:
        orm_obj = Conversation(
            space_id=space_id,
            user_id=user_id,
            title=title,
            kbase_ids=json.dumps([str(kbase_id) for kbase_id in kbase_ids]),
            status="active"
        )
        self.session.add(orm_obj)
        await self.session.commit()
        await self.session.flush()
        await self.session.refresh(orm_obj)
        return orm_obj

    async def create_message(
            self,
            space_id: UUID,
            conversation_id: str,
            role: str,
            content: str,
            text: str,
            preview: str
    ) -> ChatMessage:
        orm_obj = ChatMessage(
            space_id=space_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            text=text,
            preview=preview,
            status="active",
            timestamp=int(time.time())
        )
        self.session.add(orm_obj)
        await self.session.commit()
        await self.session.flush()
        await self.session.refresh(orm_obj)
        return orm_obj

    async def update_message(self, space_id: UUID, conversation_id: UUID, message_id: UUID, content: str, text: str, preview: str) -> ChatMessage:
        message = await self.get_message_by_id(space_id=space_id, conversation_id=conversation_id, message_id=message_id)
        if not message:
            raise MessageNotExistedError(str(message_id))
        message.content = content
        message.preview = preview
        message.text = text
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def get_messages_by_conversation_id(self, conversation_id: UUID) -> Sequence[ChatMessage]:
        result = await self.session.execute(
            select(ChatMessage).where(
                ChatMessage.conversation_id == str(conversation_id),
                ChatMessage.status == "active"
            ).order_by(ChatMessage.timestamp.asc())
        )
        messages = result.scalars().all()
        return messages

    async def get_message_by_id(self, space_id, conversation_id: UUID, message_id: UUID) -> ChatMessage:
        result = await self.session.execute(
            select(ChatMessage).where(
                ChatMessage.space_id == space_id,
                ChatMessage.uuid == str(message_id),
                ChatMessage.conversation_id == str(conversation_id),
                ChatMessage.status == "active"
            )
        )
        message = result.scalar_one_or_none()
        return message

    async def update_conversation_title(self,space_id: UUID, conversation_id: str, new_title: str):
        result = await self.session.execute(
            select(Conversation).where(
                Conversation.space_id == space_id,
                Conversation.uuid == str(conversation_id),
                Conversation.status == "active"
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise ResourceNotExistedError
        conversation.title = new_title
        self.session.add(conversation)
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def delete_conversation(self, space_id: UUID, conversation_id: UUID):
        result = await self.session.execute(
            select(Conversation).where(
                Conversation.space_id == space_id,
                Conversation.uuid == str(conversation_id),
                Conversation.status == "active"
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise ConversationNotExistedError(conversation_id)
        conversation.status = "deleted"
        self.session.add(conversation)
        messages = await self.get_messages_by_conversation_id(conversation_id)
        for message in messages:
            message.status = "deleted"
            self.session.add(message)
        await self.session.commit()
        return True

    async def get_prev_messages_by_id(self, space_id, conversation_id: UUID, message_id: UUID) -> Sequence:
        result = await self.session.execute(
            select(ChatMessage).where(
                ChatMessage.space_id == space_id,
                ChatMessage.conversation_id == str(conversation_id),
                ChatMessage.uuid == str(message_id),
                ChatMessage.status == "active"
            )
        )
        target_msg = result.scalar_one_or_none()
        if not target_msg:
            raise MessageNotExistedError(str(message_id))
        elif target_msg.role == "user":
            raise MessageRoleError

        result = await self.session.execute(
            select(ChatMessage)
            .where(
                ChatMessage.conversation_id == str(conversation_id),
                ChatMessage.uuid <= target_msg.uuid,
            )
            .order_by(ChatMessage.uuid.desc())
            .limit(settings.memory.limit * 4)
        )
        prev_msgs = result.scalars().all()
        return [
            {
                "uuid": msg.uuid,
                "role": msg.role,
                "text": msg.text,
                "timestamp": msg.timestamp
            }
            for msg in prev_msgs
        ]