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


class ImageSearchTool(BaseTool):
    name: str = "image_search_tool"
    description: str = (
        "Useful for searching imgae for similiar images. Return relevant desciption text."
    )
    searcher: MilvusDB = Field(default_factory=MilvusDB)
    collection_name: str = "images2" # 默认存图向量的地方

    def _run(
        self,
        query_img: str,
        kb_ids: list,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> list[Any]:
        logger.info(f"Image search tool query: {query_img}")
        imgs = self.searcher.img_search(
            query_img, self.collection_name, threshold=0.5, top_k=3, kb_ids=kb_ids
        )
        
        if type(imgs) is list:
            if not imgs:
                return "No results found."
            else:
                img = imgs[0] # 只取最相关的一张信息
                img_content = img.get("content") if img.get("content") else img.get("title")
                return img_content
        
        # exception msg
        return str(imgs)

    async def _arun(
        self,
        query_img: str,
        kb_ids: list,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> list[Any]:
        return self._run(query_img, kb_ids, run_manager.get_sync())




class ImageSearchByTextTool(BaseTool):
    name: str = "image_search_by_text_tool"
    description: str = (
        "Useful for searching imgae for similiar images. Return relevant desciption text."
    )
    searcher: MilvusDB = Field(default_factory=MilvusDB)
    collection_name: str = "hedian2"

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> list[Any]:
        logger.info(f"Image search tool query: {query}")
        expr = "media_path like '%.png' or media_path like '%.jpg' or media_path like '%.jpeg' or media_path like '%.bmp' or media_path like '%.gif' or media_path like '%.webp'"
        imgs = self.searcher.doc_search(
            query, 
            [self.collection_name], 
            threshold=0.7, 
            top_k=3,    
            expr = expr
        )
        if not imgs:
            return "No results found."
        img = imgs[0]
        img_content = img.content if img.content else img.title
        return {"image_name": img_content, "image_url": img.media_path}

    async def _arun(
        self,
        query: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> list[Any]:
        return self._run(query, run_manager.get_sync())


def get_image_search_tool() -> ImageSearchTool | None:
    logger.info(f"create image search tool")
    searcher = MilvusDB()

    if not searcher:
        return None
    return ImageSearchTool(searcher=searcher)


def get_image_search_by_text_tool() -> ImageSearchByTextTool | None:
    logger.info(f"create image search tool")
    searcher = MilvusDB()

    if not searcher:
        return None
    return ImageSearchByTextTool(searcher=searcher)


if __name__ == "__main__":
    # a = get_image_search_tool()
    # resp = a.invoke(
    #     "http://127.0.0.1:8372/public/Tesla/SOP1/Interactive%20Schematics/G011.jpg"
    # )
    # print(resp)
    b = get_image_search_by_text_tool()
    b.invoke('余热排出系统流程图')
