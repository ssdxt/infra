import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

import psycopg
from langgraph.store.memory import InMemoryStore
from psycopg.rows import dict_row
from pymongo import MongoClient

from src.config.loader import get_bool_env, get_str_env


class ChatStreamManager:
    """Persist streamed chat chunks for later retrieval."""

    def __init__(
        self, checkpoint_saver: bool = False, db_uri: Optional[str] = None
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.store = InMemoryStore()
        self.checkpoint_saver = checkpoint_saver
        self.db_uri = db_uri
        self.mongo_client = None
        self.mongo_db = None
        self.postgres_conn = None

        if self.checkpoint_saver:
            if self.db_uri.startswith("mongodb://"):
                self._init_mongodb()
            elif self.db_uri.startswith("postgresql://") or self.db_uri.startswith(
                "postgres://"
            ):
                self._init_postgresql()
            else:
                self.logger.warning(
                    "Unsupported database URI scheme: %s. Supported schemes: mongodb://, postgresql://, postgres://",
                    self.db_uri,
                )

    def _init_mongodb(self) -> None:
        try:
            self.mongo_client = MongoClient(self.db_uri)
            self.mongo_db = self.mongo_client.checkpointing_db
            self.mongo_client.admin.command("ping")
        except Exception as exc:
            self.logger.error("Failed to connect to MongoDB: %s", exc)

    def _init_postgresql(self) -> None:
        try:
            self.postgres_conn = psycopg.connect(self.db_uri, row_factory=dict_row)
            self._create_chat_streams_table()
        except Exception as exc:
            self.logger.error("Failed to connect to PostgreSQL: %s", exc)

    def _create_chat_streams_table(self) -> None:
        try:
            with self.postgres_conn.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chat_streams (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        thread_id VARCHAR(255) NOT NULL UNIQUE,
                        messages JSONB NOT NULL,
                        ts TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
                    );

                    CREATE INDEX IF NOT EXISTS idx_chat_streams_thread_id ON chat_streams(thread_id);
                    CREATE INDEX IF NOT EXISTS idx_chat_streams_ts ON chat_streams(ts);
                    """
                )
                self.postgres_conn.commit()
        except Exception as exc:
            self.logger.error("Failed to create chat_streams table: %s", exc)
            if self.postgres_conn:
                self.postgres_conn.rollback()

    def process_stream_message(
        self, thread_id: str, message: str, finish_reason: str
    ) -> bool:
        if not thread_id or not isinstance(thread_id, str) or not message:
            return False

        try:
            store_namespace: Tuple[str, str] = ("messages", thread_id)
            cursor = self.store.get(store_namespace, "cursor")
            current_index = 0

            if cursor is None:
                self.store.put(store_namespace, "cursor", {"index": 0})
            else:
                current_index = int(cursor.value.get("index", 0)) + 1
                self.store.put(store_namespace, "cursor", {"index": current_index})

            self.store.put(store_namespace, f"chunk_{current_index}", message)

            if finish_reason in ("stop", "interrupt"):
                return self._persist_complete_conversation(
                    thread_id, store_namespace, current_index
                )

            return True
        except Exception as exc:
            self.logger.error(
                "Error processing stream message for thread %s: %s",
                thread_id,
                exc,
            )
            return False

    def _persist_complete_conversation(
        self, thread_id: str, store_namespace: Tuple[str, str], final_index: int
    ) -> bool:
        try:
            memories = self.store.search(store_namespace, limit=final_index + 2)
            messages: List[str] = []
            for item in memories:
                value = item.dict().get("value", "")
                if value and not isinstance(value, dict):
                    messages.append(str(value))

            if not messages or not self.checkpoint_saver:
                return False

            success = False
            if self.mongo_db is not None:
                success = self._persist_to_mongodb(thread_id, messages)
            elif self.postgres_conn is not None:
                success = self._persist_to_postgresql(thread_id, messages)

            if success:
                for item in memories:
                    self.store.delete(store_namespace, item.key)

            return success
        except Exception as exc:
            self.logger.error(
                "Error persisting conversation for thread %s: %s",
                thread_id,
                exc,
            )
            return False

    def _persist_to_mongodb(self, thread_id: str, messages: List[str]) -> bool:
        try:
            collection = self.mongo_db.chat_streams
            existing_document = collection.find_one({"thread_id": thread_id})
            current_timestamp = datetime.now()

            if existing_document:
                update_result = collection.update_one(
                    {"thread_id": thread_id},
                    {"$set": {"messages": messages, "ts": current_timestamp}},
                )
                return update_result.modified_count > 0

            new_document = {
                "thread_id": thread_id,
                "messages": messages,
                "ts": current_timestamp,
                "id": uuid.uuid4().hex,
            }
            insert_result = collection.insert_one(new_document)
            return insert_result.inserted_id is not None
        except Exception as exc:
            self.logger.error("Error persisting to MongoDB: %s", exc)
            return False

    def _persist_to_postgresql(self, thread_id: str, messages: List[str]) -> bool:
        try:
            with self.postgres_conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM chat_streams WHERE thread_id = %s", (thread_id,)
                )
                existing_record = cursor.fetchone()
                current_timestamp = datetime.now()
                messages_json = json.dumps(messages)

                if existing_record:
                    cursor.execute(
                        """
                        UPDATE chat_streams
                        SET messages = %s, ts = %s
                        WHERE thread_id = %s
                        """,
                        (messages_json, current_timestamp, thread_id),
                    )
                    affected_rows = cursor.rowcount
                    self.postgres_conn.commit()
                    return affected_rows > 0

                conversation_id = uuid.uuid4()
                cursor.execute(
                    """
                    INSERT INTO chat_streams (id, thread_id, messages, ts)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (conversation_id, thread_id, messages_json, current_timestamp),
                )
                affected_rows = cursor.rowcount
                self.postgres_conn.commit()
                return affected_rows > 0
        except Exception as exc:
            self.logger.error("Error persisting to PostgreSQL: %s", exc)
            if self.postgres_conn:
                self.postgres_conn.rollback()
            return False

    def close(self) -> None:
        try:
            if self.mongo_client is not None:
                self.mongo_client.close()
        except Exception as exc:
            self.logger.error("Error closing MongoDB connection: %s", exc)

        try:
            if self.postgres_conn is not None:
                self.postgres_conn.close()
        except Exception as exc:
            self.logger.error("Error closing PostgreSQL connection: %s", exc)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


_default_manager = ChatStreamManager(
    checkpoint_saver=get_bool_env("LANGGRAPH_CHECKPOINT_SAVER", False),
    db_uri=get_str_env("LANGGRAPH_CHECKPOINT_DB_URL", "mongodb://localhost:27017"),
)


def chat_stream_message(thread_id: str, message: str, finish_reason: str) -> bool:
    checkpoint_saver = get_bool_env("LANGGRAPH_CHECKPOINT_SAVER", False)
    if checkpoint_saver:
        return _default_manager.process_stream_message(
            thread_id, message, finish_reason
        )
    return False
