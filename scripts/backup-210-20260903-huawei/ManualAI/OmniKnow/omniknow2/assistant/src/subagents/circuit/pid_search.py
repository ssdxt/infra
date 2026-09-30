import logging
from typing import Any, List, Optional

from langchain_core.callbacks import (AsyncCallbackManagerForToolRun,
                                      CallbackManagerForToolRun)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from src.subagents.circuit.milvus_db_sop import MilvusClient_sop

logger = logging.getLogger(__name__)

class CircuitTool(BaseTool):
    name: str = "circuit_tool"
    description: str = "Useful for searching information from vector db. Input should be a search keywords, like `X1000-1`."

    searcher: MilvusClient_sop = Field(default_factory=MilvusClient_sop)
    collection_name: str = "sop8_pid"

    def _run(
        self,
        keywords: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> list[Any]:
        logger.info(
            f"Circuit tool query: {keywords}"
        )
        documents = self.searcher.kerword_search(keywords,self.collection_name)
        if not documents:
            return "No results found from the local knowledge base."
        return documents

    async def _arun(
        self,
        keywords: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> list[Any]:
        return self._run(keywords, run_manager.get_sync())


def get_circuit_tool() -> CircuitTool | None:
    logger.info(f"create circuit tool: pid_searcher")
    searcher = MilvusClient_sop()

    if not searcher:
        return None
    return CircuitTool(searcher=searcher)



if __name__ == "__main__":
    tool = get_circuit_tool()
    print(tool.invoke("X179"))
