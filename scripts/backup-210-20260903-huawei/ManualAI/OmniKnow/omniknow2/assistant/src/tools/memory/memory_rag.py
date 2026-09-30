import logging
from typing import Any, Optional, Type

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from src.subagents.rag.milvus_client import MilvusDB

logger = logging.getLogger(__name__)

class LongMemoryInput(BaseModel):
    query: str = Field(description="The query string to search in the long-term memory.")
    user_id: str = Field(description="The user ID to filter the memory search by.")

class LongMemoryTool(BaseTool):
    name: str = "long_term_memory"
    description: str = (
        "Useful for searching history messages from vector db. Use as Long-term Memory."
    )
    args_schema: Type[BaseModel] = LongMemoryInput

    searcher: MilvusDB = Field(default_factory=MilvusDB)
    collection_name: str = "long_memory"

    def _run(
        self,
        query: str,
        user_id: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> list[Any]:
        logger.info(f"Memory tool query: {query} for user_id: {user_id}")
        documents = self.searcher.memory_search(query, user_id=user_id, top_k=5, collection_name=self.collection_name)
        if not documents:
            return []
        return documents

    async def _arun(
        self,
        query: str,
        user_id: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> list[Any]:
        return self._run(query, user_id, run_manager.get_sync() if run_manager else None)

def get_long_memory_tool() -> LongMemoryTool | None:
    logger.info("create longterm memory tool")
    searcher = MilvusDB()

    if not searcher:
        return None
    return LongMemoryTool(searcher=searcher)

if __name__ == "__main__":
    a = get_long_memory_tool()
    resp = a.invoke({"query": "anything", "user_id": "123"})
    print(resp)
