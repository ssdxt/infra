"""
向量库（Milvus）客户端。

统一封装所有对 Milvus 侧 HTTP API 的调用。调用方（services / resource_manager）
不应再直接使用 httpx 或硬编码 Milvus endpoint。
"""

from uuid import UUID

import httpx

from core.config import settings
from exceptions.errors.task import MilvusDeletionError
from utils.log import logger


class ParserClient:
    """Milvus HTTP API 客户端。"""

    def __init__(self):
        self._base_url = settings.parser.api_url

    async def document_insert(
        self,
        *,
        chunks: list,
        doc_summary: str,
        collection_name: str,
        img_collection_name: str = "images2",
        sum_collection_name: str = "chapter_summary",
    ) -> None:
        """写入解析完成的 chunks + 摘要到向量库。

        迁自 `core/resource_manager.py::_upload_chunks_media` 中的 Milvus 调用段。
        """
        logger.info("正在发送 chunks 向量数据库 Milvus")
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self._base_url}/document_insert"
                res = await client.post(
                    url=url,
                    json={
                        "chunks": chunks,
                        "doc_summary": doc_summary,
                        "collection_name": collection_name,
                        "img_collection_name": img_collection_name,
                        "sum_collection_name": sum_collection_name,
                    },
                    timeout=3600,
                )
                res.raise_for_status()
                data = res.json()
                if res.status_code != 200 or not data.get("success"):
                    logger.error(f"向量数据库 Milvus 写入失败: {data}")
                else:
                    logger.info(data["message"])
        except Exception as e:
            logger.error(f"向量数据库 Milvus 写入失败: {e}")
            raise

    async def delete_resource_data(self, collection_name: str, resource_id: UUID) -> bool:
        """删除单个 resource 在向量库的数据。

        迁自 `parser/dispatcher.py::delete_milvus_resource_data`。
        """
        try:
            data = {
                "collection_name": collection_name,
                "file_id": str(resource_id),
            }
            async with httpx.AsyncClient() as client:
                url = f"{self._base_url}/delete_doc_by_id"
                res = await client.post(url=url, json=data)
                res.raise_for_status()
                logger.info(
                    f"Milvus 数据删除成功: collection={collection_name}, file_id={resource_id}"
                )
                return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                logger.info("Milvus 为空，默认删除成功")
                return True
            if e.response.status_code == 500 and "未找到数据" in e.response.text:
                logger.info("Milvus 中未找到数据，默认删除成功")
                return True
            logger.error(f"Milvus 操作失败。\n响应码: {e.response.status_code}\n响应内容: {e.response.text}")
            return True
        except Exception as e:
            logger.error(f"Milvus 数据删除失败: {e}，静默处理")
            return True

    async def delete_collection(self, collection_name: str) -> bool:
        """删除整个 collection。

        迁自 `parser/dispatcher.py::delete_milvus_collection`。
        """
        try:
            data = {"collection_name": collection_name}
            async with httpx.AsyncClient() as client:
                url = f"{self._base_url}/delete_collection"
                res = await client.post(url=url, json=data)
                res.raise_for_status()
                logger.info(f"Milvus collection 删除成功: {collection_name}")
                return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                logger.info("Milvus collection 不存在，默认删除成功")
                return True
            logger.error(f"Milvus 操作失败，响应码: {e.response.status_code}")
            return False
        except Exception as e:
            logger.error(f"Milvus collection 删除失败: {e}")
            raise MilvusDeletionError("请检查向量数据库连接是否正常")
