import logging
from typing import Any, Optional

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import Field
from src.subagents.rag.milvus_client import MilvusDB

logger = logging.getLogger(__name__)


class CircuitTool(BaseTool):
    name: str = "circuit_tool"
    description: str = (
        "Useful for searching information from vector db. Input should be a search keywords, like `X1000-1`."
    )

    searcher: MilvusDB = Field(default_factory=MilvusDB)
    collection_name: str = "sop"

    def _run(
        self,
        keywords: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> list[Any]:
        logger.info(f"Circuit tool query: {keywords}")
        documents = self.searcher.sop_search(keywords, self.collection_name)
        if not documents:
            return "No results found from the local knowledge base."
        documents = [{**item, 'url': item['url'].replace('http://', 'https://')} for item in documents]
        return documents

    async def _arun(
        self,
        keywords: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> list[Any]:
        return self._run(keywords, run_manager.get_sync())


def get_circuit_tool(collection_name) -> CircuitTool | None:
    logger.info(f"create circuit tool: pid_searcher")
    searcher = MilvusDB()

    if not searcher:
        return None
    return CircuitTool(searcher=searcher,collection_name=collection_name)


if __name__ == "__main__":
    a  = get_circuit_tool() 
    resp = a.invoke('X179')
    print(resp)
