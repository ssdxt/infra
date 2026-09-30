"""
Milvus 直连客户端（pymilvus SDK）。

封装 pymilvus AsyncMilvusClient，提供 Collection 管理、数据增删改查、向量检索等基础操作。
业务逻辑（如文档解析写入）请通过 ParserClient 走 HTTP 服务，本类供直接操作 Milvus 的场景使用。
"""

from typing import Any

from pymilvus import AsyncMilvusClient as _SDKClient
from pymilvus import DataType, Function, FunctionType

from core.config import settings
from utils.log import logger


class MilvusClient:
    """pymilvus SDK 直连客户端，提供 Milvus 基础操作。"""

    def __init__(self):
        cfg = settings.milvus
        scheme = "https" if cfg.ssl else "http"
        uri = f"{scheme}://{cfg.host}:{cfg.port}"
        kwargs: dict = {"uri": uri, "db_name": cfg.db_name, "timeout": cfg.timeout}
        if cfg.token:
            kwargs["token"] = cfg.token
        elif cfg.user and cfg.password:
            kwargs["user"] = cfg.user
            kwargs["password"] = cfg.password
        self._c = _SDKClient(**kwargs)

    # ------------------------------------------------------------------
    # Collection 管理
    # ------------------------------------------------------------------

    async def create_collection(
        self,
        collection_name: str,
        dimension: int,
        *,
        primary_field: str = "id",
        vector_field: str = "vector",
        metric_type: str = "COSINE",
        auto_id: bool = False,
        extra_fields: list[dict] | None = None,
        index_params: dict | None = None,
    ) -> None:
        """创建 Collection，自动建立向量索引。

        extra_fields 格式：
            [{"name": "content", "dtype": DataType.VARCHAR, "max_length": 65535}, ...]
        index_params 不传时默认使用 HNSW。
        """
        from pymilvus import CollectionSchema, FieldSchema, MilvusClient as SyncClient

        if await self._c.has_collection(collection_name):
            logger.info(f"Collection 已存在，跳过创建: {collection_name}")
            return

        schema = self._c.create_schema(auto_id=auto_id, enable_dynamic_field=True)
        schema.add_field(primary_field, DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field(vector_field, DataType.FLOAT_VECTOR, dim=dimension)
        for f in (extra_fields or []):
            schema.add_field(**f)

        idx = self._c.prepare_index_params()
        if index_params:
            idx.add_index(field_name=vector_field, **index_params)
        else:
            idx.add_index(
                field_name=vector_field,
                index_type="HNSW",
                metric_type=metric_type,
                params={"M": 16, "efConstruction": 200},
            )

        await self._c.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=idx,
        )
        logger.info(f"Collection 创建成功: {collection_name}, dim={dimension}")

    async def drop_collection(self, collection_name: str) -> None:
        """删除 Collection（不存在时静默跳过）。"""
        if not await self._c.has_collection(collection_name):
            logger.info(f"Collection 不存在，跳过删除: {collection_name}")
            return
        await self._c.drop_collection(collection_name)
        logger.info(f"Collection 删除成功: {collection_name}")

    async def has_collection(self, collection_name: str) -> bool:
        return await self._c.has_collection(collection_name)

    async def list_collections(self) -> list[str]:
        return await self._c.list_collections()

    async def describe_collection(self, collection_name: str) -> dict:
        return await self._c.describe_collection(collection_name)

    async def get_collection_stats(self, collection_name: str) -> dict:
        return await self._c.get_collection_stats(collection_name)

    # ------------------------------------------------------------------
    # 数据写入
    # ------------------------------------------------------------------

    async def insert(self, collection_name: str, data: list[dict]) -> dict:
        """批量插入数据，返回 insert_count 等结果。"""
        result = await self._c.insert(collection_name=collection_name, data=data)
        logger.info(f"插入成功: collection={collection_name}, count={result.get('insert_count', len(data))}")
        return result

    async def upsert(self, collection_name: str, data: list[dict]) -> dict:
        """批量 upsert（存在则更新，不存在则插入）。"""
        result = await self._c.upsert(collection_name=collection_name, data=data)
        logger.info(f"Upsert 成功: collection={collection_name}, count={result.get('upsert_count', len(data))}")
        return result

    # ------------------------------------------------------------------
    # 数据删除
    # ------------------------------------------------------------------

    async def delete(
        self,
        collection_name: str,
        *,
        ids: list | None = None,
        filter: str | None = None,
    ) -> dict:
        """按主键列表或过滤表达式删除数据。ids 与 filter 二选一。

        filter 示例：'file_id == "abc123"' 或 'chunk_index > 10'
        """
        if ids is not None:
            result = await self._c.delete(collection_name=collection_name, ids=ids)
        elif filter:
            result = await self._c.delete(collection_name=collection_name, filter=filter)
        else:
            raise ValueError("delete 需要提供 ids 或 filter")
        logger.info(f"删除成功: collection={collection_name}, delete_count={result.get('delete_count')}")
        return result

    # ------------------------------------------------------------------
    # 数据查询
    # ------------------------------------------------------------------

    async def get(
        self,
        collection_name: str,
        ids: list,
        output_fields: list[str] | None = None,
    ) -> list[dict]:
        """按主键列表精确获取记录。"""
        return await self._c.get(
            collection_name=collection_name,
            ids=ids,
            output_fields=output_fields,
        )

    async def query(
        self,
        collection_name: str,
        filter: str,
        output_fields: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """按标量过滤条件查询，返回匹配记录。

        filter 示例：'file_id == "abc123"'
        """
        return await self._c.query(
            collection_name=collection_name,
            filter=filter,
            output_fields=output_fields,
            limit=limit,
            offset=offset,
        )

    # ------------------------------------------------------------------
    # 向量检索
    # ------------------------------------------------------------------

    async def search(
        self,
        collection_name: str,
        data: list[list[float]],
        anns_field: str,
        limit: int = 10,
        *,
        filter: str = "",
        output_fields: list[str] | None = None,
        search_params: dict | None = None,
    ) -> list[list[dict]]:
        """向量相似度检索。

        data: 查询向量列表，每条查询返回 limit 个结果。
        返回值: [[{id, distance, entity}, ...], ...]，与 data 一一对应。
        """
        params = search_params or {"metric_type": "COSINE", "params": {"ef": 100}}
        results = await self._c.search(
            collection_name=collection_name,
            data=data,
            anns_field=anns_field,
            limit=limit,
            filter=filter,
            output_fields=output_fields,
            search_params=params,
        )
        return results

    # ------------------------------------------------------------------
    # 索引管理
    # ------------------------------------------------------------------

    async def create_index(
        self,
        collection_name: str,
        field_name: str,
        index_type: str = "HNSW",
        metric_type: str = "COSINE",
        params: dict | None = None,
    ) -> None:
        index_params = self._c.prepare_index_params()
        index_params.add_index(
            field_name=field_name,
            index_type=index_type,
            metric_type=metric_type,
            params=params or {"M": 16, "efConstruction": 200},
        )
        await self._c.create_index(collection_name, index_params)
        logger.info(f"索引创建成功: collection={collection_name}, field={field_name}")

    async def drop_index(self, collection_name: str, field_name: str) -> None:
        await self._c.drop_index(collection_name, field_name)
        logger.info(f"索引删除成功: collection={collection_name}, field={field_name}")

    # ------------------------------------------------------------------
    # 加载 / 释放
    # ------------------------------------------------------------------

    async def load_collection(self, collection_name: str) -> None:
        await self._c.load_collection(collection_name)
        logger.info(f"Collection 已加载到内存: {collection_name}")

    async def release_collection(self, collection_name: str) -> None:
        await self._c.release_collection(collection_name)
        logger.info(f"Collection 已从内存释放: {collection_name}")
