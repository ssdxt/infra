import datetime
from uuid import UUID
import json

from core.dependencies import RequestContext
from exceptions.errors.resource import ResourceNotExistedError, ConversationNotExistedError
from repository.chat import ChatRepository
from schemas import MessageRecordSchema


class ChatService:
    def __init__(self, ctx: RequestContext):
        self.session = ctx.db
        self.user = ctx.user
        self.chat_repo = ChatRepository(ctx.db)

    async def create_conversation(self, space_id: UUID, kbase_ids: list[UUID]):
        conversation = await self.chat_repo.create_conversation(
            space_id=space_id,
            user_id=self.user.uuid,
            title="会话 - " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            kbase_ids=kbase_ids
        )
        return {
            "uuid": conversation.uuid,
            "title": conversation.title,
            "created_at": conversation.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }

    async def get_conversations_list(self, space_id: UUID):
        conversations = await self.chat_repo.get_conversations_list(space_id, self.user.uuid)
        return [
            {
                "uuid": conversation.uuid,
                "title": conversation.title,
                "kbase_ids": json.loads(conversation.kbase_ids) if conversation.kbase_ids else [],
                "created_at": conversation.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "order": i + 1
            }
            for i, conversation in enumerate(conversations)
        ]

    async def get_conversation_detail(self, space_id: UUID, conversation_id: UUID):
        conversation = await self.chat_repo.get_conversation(space_id, str(conversation_id), self.user.uuid)
        if not conversation:
            raise ResourceNotExistedError
        messages = await self.chat_repo.get_messages_by_conversation_id(conversation_id)
        messages = [
            {
                "uuid": message.uuid,
                "role": message.role,
                "content": message.content,
                "preview": message.preview,
                "created_at": message.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                # 前端根据order排序展示
                "order": i + 1
            }
            for i, message in enumerate(messages)
        ]
        return {
            "uuid": conversation.uuid,
            "title": conversation.title,
            "kbase_ids": json.loads(conversation.kbase_ids) if conversation.kbase_ids else [],
            "created_at": conversation.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "messages": messages
        }

    async def insert_message_to_conversation(self, space_id: UUID, conversation_id: UUID, msg: MessageRecordSchema):
        conversation = await self.chat_repo.get_conversation(space_id, str(conversation_id), self.user.uuid)
        if not conversation:
            raise ConversationNotExistedError(conversation_id)

        if msg.message_id:
            # 如果message_id存在，说明是更新消息
            message = await self.chat_repo.update_message(
                space_id=space_id,
                conversation_id=conversation_id,
                message_id=msg.message_id,
                content=msg.content,
                preview=self._build_preview(msg.text),
                text=msg.text
            )
        else:
            message = await self.chat_repo.create_message(
                space_id=space_id,
                conversation_id=conversation.uuid,
                role=msg.role,
                content=msg.content,
                text=msg.text,
                preview=self._build_preview(msg.text)
            )

        return {
            "uuid": message.uuid,
            "conversation_id": message.conversation_id,
            "role": message.role,
            "content": message.content,
            "preview": message.preview,
            "metadata": msg.metadata,
            "created_at": message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }

    @staticmethod
    def _build_preview(content: str) -> str | None:
        return content.strip().replace("\n", " ")[:50]

    async def update_conversation_title(self, space_id: UUID, conversation_id: str, title: str):
        conversation = await self.chat_repo.update_conversation_title(space_id, conversation_id, title)
        return {
            "uuid": conversation.uuid,
            "title": conversation.title,
            "created_at": conversation.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": conversation.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        }

    async def delete_conversation(self, space_id: UUID, conversation_id: UUID):
        await self.chat_repo.delete_conversation(space_id, conversation_id)
        return {
            "message": "Conversation deleted successfully"
        }