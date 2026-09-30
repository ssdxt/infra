import asyncio
import os
from parser.utils import download_image, get_img_embedding, async_get_img_embedding, is_img_search_enabled
from parser.utils import get_vllm_embedding as get_embedding, async_get_vllm_embedding as get_async_embedding
from parser.utils import get_vllm_rerank as get_rerank, async_get_vllm_rerank as get_async_rerank
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field
from pymilvus import (
    AnnSearchRequest,
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    Function,
    FunctionType,
    RRFRanker,
    WeightedRanker,
    connections,
    utility,
)
from pymilvus.client.types import LoadState
from schema import SearchModel

load_dotenv()

batch_size = int(os.getenv("COLLECTION_INSERT_BATCH_SIZE", 256))
sem = asyncio.Semaphore(4)

# 根据type参数映射到对应的anns_field
SEMANTICS_MAPPING = {
    "text": "embedding_text",
    "summary": "embedding_summary",
    "title": "embedding_title",
}

KEYWORD_MAPPING = {"text": "sparse_content", "title": "sparse_title"}

output_document_fields = [
    "chunk_id",
    "bbox_type",
    "title",
    "content",
    "summary",
    "media_path",
    "chunk_source",
    "file_id",
    "file_path",
    "update_time",
    "bbox",
    "page_idx",
    "others",
]
output_img_fields = ["chunk_id", "kb_id", "img_path"]
output_memory_fields = ["user_id", "thread_id", "messages"]
output_sop_fields=["pin_number", "pin_number_id", "page_name", "page_number", "connectorID", "cavityID","SOP"]


class Resource(BaseModel):
    """
    Resource is a class that represents a resource.
    """

    knowledge_id: str = Field(..., description="The id of the knowledge")
    knowledge_name: str = Field(..., description="The name of the knowledge")
    knowledge_description: str | None = Field(
        "", description="The description of the knowledge"
    )


class MilvusClient:
    def __init__(self, **kwargs):
        self.milvus_host = os.getenv("MILVUS_HOST")
        self.milvus_port = os.getenv("MILVUS_PORT")
        self.collections: Dict[str, Collection] = {}
        self.loaded_collections: set = set()  # 跟踪已加载的集合

        # 连接管理
        self._connect()

    def _connect(self):
        """建立 Milvus 连接"""
        try:
            connections.connect("default", host=self.milvus_host, port=self.milvus_port)
            logger.info(
                f"Successfully connected to Milvus at {self.milvus_host}:{self.milvus_port}"
            )

        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise

    def _list_collections(self):
        return utility.list_collections()

    def _initialize_collections(self):
        """移除此方法，改为懒加载模式"""
        pass

    def _ensure_collection_loaded(self, collection: Collection) -> bool:
        """确保集合被加载到内存中（懒加载）"""
        collection_name = collection.name

        # 如果已经加载过，直接返回
        if utility.load_state(collection_name) == LoadState.Loaded:
            self.loaded_collections.add(collection_name)
            return True

        try:
            # 尝试加载集合
            collection.load()
            self.loaded_collections.add(collection_name)
            logger.info(f"Collection '{collection_name}' loaded successfully")
            return True
        except Exception as e:
            # 如果加载失败，可能是因为集合已经加载或其他原因
            try:
                # 尝试通过简单查询来验证集合是否可用
                self.loaded_collections.add(collection_name)
                logger.info(f"Collection '{collection_name}' is already loaded")
                return True
            except Exception as inner_e:
                logger.error(
                    f"Failed to load collection '{collection_name}': {e}, verification failed: {inner_e}"
                )
                return False

    def _get_collection_safe(self, collection_name: str) -> Optional[Collection]:
        """安全地获取集合，按需加载（懒加载）"""
        try:
            # 如果集合不在缓存中，先检查是否存在
            if collection_name not in self.collections:
                if not self._collection_exists(collection_name):
                    logger.error(f"Collection '{collection_name}' does not exist")
                    return None

                # 创建集合对象但不立即加载
                collection = Collection(collection_name)
                self.collections[collection_name] = collection
                logger.debug(f"Collection '{collection_name}' added to cache")

            collection = self.collections[collection_name]

            # 懒加载：只有在实际使用时才加载到内存
            if not self._ensure_collection_loaded(collection):
                logger.warning(
                    f"Collection '{collection_name}' may not be fully loaded, but will try to proceed"
                )

            return collection

        except Exception as e:
            logger.error(f"Error getting collection '{collection_name}': {e}")
            return None

    def _collection_exists(self, collection_name: str) -> bool:
        """检查集合是否存在"""
        return utility.has_collection(collection_name)

    async def create_collection(self, collection_name: str, analyzer: str = "chinese"):
        """创建 Milvus 集合（如果不存在）"""
        if self._collection_exists(collection_name):
            logger.info(f"Collection '{collection_name}' already exists")
            return

        analyzer_params = {"type": analyzer}

        try:
            fields = [
                FieldSchema(
                    name="id", dtype=DataType.INT64, is_primary=True, auto_id=True
                ),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(
                    name="content",
                    dtype=DataType.VARCHAR,
                    max_length=32768,
                    enable_analyzer=True,
                    analyzer_params=analyzer_params,
                    enable_match=True,
                ),
                FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="file_path", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="update_time", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="bbox_type", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(
                    name="title",
                    dtype=DataType.VARCHAR,
                    max_length=256,
                    enable_analyzer=True,
                    analyzer_params=analyzer_params,
                    enable_match=True,
                ),
                FieldSchema(name="summary", dtype=DataType.VARCHAR, max_length=8192),
                FieldSchema(name="media_path", dtype=DataType.VARCHAR, max_length=1024),
                FieldSchema(
                    name="chunk_source", dtype=DataType.VARCHAR, max_length=128
                ),
                FieldSchema(
                    name="embedding_summary", dtype=DataType.FLOAT_VECTOR, dim=1024
                ),
                FieldSchema(name="bbox", dtype=DataType.JSON),
                FieldSchema(name="page_idx", dtype=DataType.JSON),
                FieldSchema(
                    name="embedding_text", dtype=DataType.FLOAT_VECTOR, dim=1024
                ),
                FieldSchema(
                    name="embedding_title", dtype=DataType.FLOAT_VECTOR, dim=1024
                ),
                FieldSchema(name="sparse_content", dtype=DataType.SPARSE_FLOAT_VECTOR),
                FieldSchema(name="sparse_title", dtype=DataType.SPARSE_FLOAT_VECTOR),
                # FieldSchema(name="others", dtype=DataType.VARCHAR, max_length=8192),
                FieldSchema(name="others", dtype=DataType.JSON),
            ]

            content_bm25_function = Function(
                name="content_bm25_emb",  # Function name
                input_field_names=[
                    "content"
                ],  # Name of the VARCHAR field containing raw text data
                output_field_names=[
                    "sparse_content"
                ],  # Name of the SPARSE_FLOAT_VECTOR field reserved to store generated embeddings
                function_type=FunctionType.BM25,  # Set to `BM25`
            )
            title_bm25_function = Function(
                name="title_bm25_emb",  # Function name
                input_field_names=[
                    "title"
                ],  # Name of the VARCHAR field containing raw text data
                output_field_names=[
                    "sparse_title"
                ],  # Name of the SPARSE_FLOAT_VECTOR field reserved to store generated embeddings
                function_type=FunctionType.BM25,  # Set to `BM25`
            )

            schema = CollectionSchema(
                fields, description=f"RAG Collection: {collection_name}"
            )
            schema.add_function(content_bm25_function)
            schema.add_function(title_bm25_function)
            collection = Collection(collection_name, schema)

            # 创建语义索引
            index_params = {
                "index_type": "IVF_FLAT",
                # "metric_type": "L2",
                "metric_type": "COSINE",
                "index_name": "vector_index",
                "params": {"nlist": 128},
            }

            # 创建关键字索引
            bm_index_params = {
                "index_type": "SPARSE_INVERTED_INDEX",
                "metric_type": "BM25",
                "params": {
                    "inverted_index_algo": "DAAT_MAXSCORE",
                    "bm25_k1": 1.2,
                    "bm25_b": 0.75,
                },
            }

            collection.create_index("embedding_text", index_params)
            collection.create_index("embedding_summary", index_params)
            collection.create_index("embedding_title", index_params)
            collection.create_index("sparse_content", bm_index_params)
            collection.create_index("sparse_title", bm_index_params)

            # time.sleep(1)
            # 加载集合
            collection.load()

            self.collections[collection_name] = collection
            logger.info(
                f"Successfully created and loaded collection: {collection_name}"
            )

        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            raise

    async def create_collection_image(self, collection_name: str):
        """创建 Milvus 集合（如果不存在）"""
        if self._collection_exists(collection_name):
            logger.info(f"Collection '{collection_name}' already exists")
            return

        try:
            fields = [
                FieldSchema(
                    name="id", dtype=DataType.INT64, is_primary=True, auto_id=True
                ),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="kb_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="img_path", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(
                    name="embedding_img", dtype=DataType.FLOAT_VECTOR, dim=1024
                ),
            ]

            schema = CollectionSchema(
                fields, description=f"RAG Collection: {collection_name}"
            )

            collection = Collection(collection_name, schema)

            # 创建语义索引
            index_params = {
                "index_type": "IVF_FLAT",
                # "metric_type": "L2",
                "metric_type": "COSINE",
                "index_name": "vector_index",
                "params": {"nlist": 128},
            }

            collection.create_index("embedding_img", index_params)

            # time.sleep(1)
            # 加载集合
            collection.load()

            self.collections[collection_name] = collection
            logger.info(
                f"Successfully created and loaded collection: {collection_name}"
            )

        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            raise

    async def img_insert(self, collection_name: str, chunks: list) -> bool:
        """插入数据到指定集合"""
        if not is_img_search_enabled():
            logger.info(
                f"IMG_SEARCH=False，跳过 collection '{collection_name}' 的图片向量化与插入。"
            )
            return True

        if not chunks:
            logger.info(
                f"No image chunks provided for collection '{collection_name}', skipping insert."
            )
            return True

        if collection_name not in self.collections:
            await self.create_collection_image(collection_name)

        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot insert into collection '{collection_name}' - collection not available"
            )
            return False

        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            try:
                # 准备数据
                chunk_id_list, kb_id_list, img_path_list = [], [], []

                for chunk in batch:
                    chunk_id_list.append(chunk.chunk_id)
                    # kb_id_list.append(chunk.kb_id)
                    kb_id_list.append("tesla_manual_oss")
                    # img_path_list.append(chunk.img_path)
                    img_path_list.append(chunk.img_path)

                # 生成嵌入向量
                embedding_img_list = await get_img_embedding(img_path_list)

                data = [
                    chunk_id_list,
                    kb_id_list,
                    img_path_list,
                    embedding_img_list,
                ]

                # 插入数据
                collection.insert(data)
            except Exception as e:
                logger.error(
                    f"Failed to insert batch into collection '{collection_name}': {e}"
                )
                # logger.error(f"Failed to insert batch into collection '{data}'")
                return False
        collection.flush()
        logger.info(
            f"Successfully inserted {len(chunks)} chunks into collection '{collection_name}'"
        )
        return True

    async def async_img_search(
        self,
        query_img: str,
        collection_name: str,
        threshold: float = 0.5,
        kb_ids: list = None,
        top_k: int = 10,
    ) -> List[SearchModel]:
        """在指定集合中搜索语义相似数据图片

        Args:
            query_img: 查询图片路径
            collection_name: 集合名称
            top_k: 返回结果数量
            type: 搜索类型，可选值: "text" (对应embedding_text), "summary" (对应embedding_summary), "title" (对应embedding_title)
        """

        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot search in collection '{collection_name}' - collection not available"
            )
            return []

        try:
            # 生成查询向量
            query_img_embedding = await get_img_embedding(query_img)

            # 定义搜索参数
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}

            expr = None
            if kb_ids:
                expr = f"kb_id in {kb_ids}"

            # 执行搜索
            results = collection.search(
                data=[query_img_embedding],
                anns_field="embedding_img",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=output_img_fields,
            )

            # print('======================',results)
            # 格式化结果
            documents = []
            for hit in results[0]:
                if hit["distance"] < threshold:
                    continue
                entity = hit["entity"].copy()
                entity["score"] = hit["distance"]
                chunk_id = hit["entity"]["chunk_id"]
                collection_name = hit["entity"]["kb_id"]
                # print(self.list_chunk_by_id(chunk_id, collection_name))
                documents.append(self.list_chunk_by_id(chunk_id, collection_name))

            return documents

        except Exception as e:
            logger.error(f"Search failed in collection '{collection_name}': {e}")
            return []


    def create_collection_memory(self, collection_name: str, analyzer: str = "chinese"):
        """创建 Milvus 集合（如果不存在）"""
        if self._collection_exists(collection_name):
            logger.info(f"Collection '{collection_name}' already exists")
            return

        analyzer_params = {"type": analyzer}

        try:
            fields = [
                FieldSchema(
                    name="id", dtype=DataType.INT64, is_primary=True, auto_id=True
                ),
                FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(
                    name="messages",
                    dtype=DataType.VARCHAR,
                    max_length=32768,
                    enable_analyzer=True,
                    analyzer_params=analyzer_params,
                    enable_match=True,
                ),
                FieldSchema(name="thread_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(
                    name="embedding_messages", dtype=DataType.FLOAT_VECTOR, dim=1024
                ),
                FieldSchema(name="sparse_messages", dtype=DataType.SPARSE_FLOAT_VECTOR),
            ]

            content_bm25_function = Function(
                name="messages_bm25_emb",  # Function name
                input_field_names=[
                    "messages"
                ],  # Name of the VARCHAR field containing raw text data
                output_field_names=[
                    "sparse_messages"
                ],  # Name of the SPARSE_FLOAT_VECTOR field reserved to store generated embeddings
                function_type=FunctionType.BM25,  # Set to `BM25`
            )

            schema = CollectionSchema(
                fields, description=f"RAG Collection: {collection_name}"
            )
            schema.add_function(content_bm25_function)
            collection = Collection(collection_name, schema)

            # 创建语义索引
            index_params = {
                "index_type": "IVF_FLAT",
                # "metric_type": "L2",
                "metric_type": "COSINE",
                "index_name": "vector_index",
                "params": {"nlist": 128},
            }
            
            bm_index_params = {
                "index_type": "SPARSE_INVERTED_INDEX",
                "metric_type": "BM25",
                "params": {
                    "inverted_index_algo": "DAAT_MAXSCORE",
                    "bm25_k1": 1.2,
                    "bm25_b": 0.75,
                },
            }

          
            collection.create_index("sparse_messages", bm_index_params)
            collection.create_index("embedding_messages", index_params)

            # time.sleep(1)
            # 加载集合
            collection.load()

            self.collections[collection_name] = collection
            logger.info(
                f"Successfully created and loaded collection: {collection_name}"
            )

        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            raise

    def memory_insert(
        self,
        messages: str,
        user_id: str,
        thread_id: str,
        collection_name="long_memory",
    ):
        """插入数据到指定集合"""
        if collection_name not in self.collections:
            self.create_collection_memory(collection_name)

        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot insert into collection '{collection_name}' - collection not available"
            )
            return False

        try:
            message_embed = get_embedding(messages)

            data = [
                {
                    "messages": messages,
                    "user_id": user_id,
                    "thread_id": thread_id,
                    "embedding_messages": message_embed,
                }
            ]

            collection.insert(data)
        except Exception as e:
            logger.error(
                f"Failed to insert batch into collection '{collection_name}': {e}"
            )
            # logger.error(f"Failed to insert batch into collection '{data}'")
            return False
        collection.flush()
        logger.info(f"Successfully inserted into collection '{collection_name}'")
        return True

    def memory_search(
        self,
        query: str,
        user_id: str,
        top_k: int = 5,
        collection_name="long_memory",
        dense_weight=0.7,
        sparse_weight=0.3,
    ):
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot search in collection '{collection_name}' - collection not available"
            )
            return []

        try:
            query_embedding = get_embedding(query)
        except Exception as e:
            logger.error(f"Embedding model error: {e}")
            return []

        dense_request = AnnSearchRequest(
            data=[query_embedding],
            anns_field="embedding_messages",
            param={
                "metric_type": "COSINE",
                "params": {"nprobe": 16},
            },
            limit=top_k,
            expr=(f"user_id == '{user_id}' ")
        )

        sparse_request = AnnSearchRequest(
            data=[query],
            anns_field="sparse_messages",
            param={"params": {"drop_ratio_search": 0.2}},
            limit=top_k,
            expr=(f"user_id == '{user_id}' ")
        )

        reranker = WeightedRanker(dense_weight, sparse_weight)

        results = collection.hybrid_search(
            reqs=[dense_request, sparse_request],
            rerank=reranker,
            limit=top_k,
            output_fields=output_memory_fields,
        )

        documents: list[dict] = []
        for hit in results[0]:
            entity = hit.entity
            documents.append(
                {
                    "user_id": entity.user_id,
                    "messages": entity.messages,
                    "thread_id": entity.thread_id,
                    "score": hit.score,
                }
            )

        return documents

    def img_search(
        self,
        query_img: str,
        collection_name: str = "images",
        threshold: float = 0.5,
        kb_ids: list = None,
        top_k: int = 10,
    ) -> List[SearchModel]:
        """在指定集合中搜索语义相似数据图片

        Args:
            query_img: 查询图片路径
            collection_name: 集合名称
            top_k: 返回结果数量
            type: 搜索类型，可选值: "text" (对应embedding_text), "summary" (对应embedding_summary), "title" (对应embedding_title)
        """

        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot search in collection '{collection_name}' - collection not available"
            )
            return []

        save_img = download_image(query_img)
        try:
            # 生成查询向量
            query_img_embedding = get_img_embedding(save_img)

            # 定义搜索参数
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}

            expr = None
            if kb_ids:
                expr = f"kb_id in {kb_ids}"

            # 执行搜索
            results = collection.search(
                data=[query_img_embedding],
                anns_field="embedding_img",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=output_img_fields,
            )

            # 格式化结果
            documents = []
            for hit in results[0]:
                if hit["distance"] < threshold:
                    continue
                entity = hit["entity"].copy()
                entity["score"] = hit["distance"]
                chunk_id = hit["entity"]["chunk_id"]
                collection_name = hit["entity"]["kb_id"]
                # print(self.list_chunk_by_id(chunk_id, collection_name))
                documents.append(self.list_chunk_by_id(chunk_id, collection_name))

            return documents

        except Exception as e:
            logger.error(f"Search failed in collection '{collection_name}': {e}")
            return []

    def create_sop_collection(self, collection_name: str, analyzer:str='english'):
        """创建 Milvus 集合（如果不存在）"""
        if self._collection_exists(collection_name):
            logger.info(f"Collection '{collection_name}' already exists")
            return


        analyzer_params = {
            "type": analyzer
        }
        
        try:
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="pin_number", dtype=DataType.VARCHAR, max_length=256,enable_analyzer=True, analyzer_params=analyzer_params, enable_match=True),
                FieldSchema(name="pin_number_id", dtype=DataType.INT64),
                FieldSchema(name="page_name", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="page_number", dtype=DataType.INT64),
                FieldSchema(name="connectorID", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="cavityID", dtype=DataType.VARCHAR, max_length=32),
                FieldSchema(name="SOP", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="url", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="details", dtype=DataType.JSON),
                FieldSchema(name="sparse_pin_number", dtype=DataType.SPARSE_FLOAT_VECTOR),
                
            ]

            pin_number_bm25_function = Function(
                name="content_bm25_emb", # Function name
                input_field_names=["pin_number"], # Name of the VARCHAR field containing raw text data
                output_field_names=["sparse_pin_number"], # Name of the SPARSE_FLOAT_VECTOR field reserved to store generated embeddings
                function_type=FunctionType.BM25, # Set to `BM25`
            )


            schema = CollectionSchema(fields, description=f"RAG Collection: {collection_name}")
            schema.add_function(pin_number_bm25_function)
            collection = Collection(collection_name, schema)

            
            # 创建关键字索引
            bm_index_params = {
                "index_type": "SPARSE_INVERTED_INDEX",
                "metric_type": "BM25",
                "params": {
                    "inverted_index_algo": "DAAT_MAXSCORE",
                    "bm25_k1": 1.2,
                    "bm25_b": 0.75
                },
            }

            collection.create_index("sparse_pin_number", bm_index_params)

            # time.sleep(1)
            # 加载集合
            collection.load()

            self.collections[collection_name] = collection
            logger.info(f'Successfully created and loaded collection: {collection_name}')

        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            raise

    def sop_insert(self, collection_name: str, chunks) -> bool:
        """插入数据到指定集合"""
        if collection_name not in self.collections:
            self.create_sop_collection(collection_name)

        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(f"Cannot insert into collection '{collection_name}' - collection not available")
            return False

        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            try:
                # 准备数据
                pin_number_list, pin_number_id_list, page_name_list, page_number_list = [], [], [], []
                connectorID_list, cavityID_list, SOP_list = [], [], []
                url_list, details_list = [], []
                
                for chunk in batch:
                    pin_number_list.append(chunk["pin_number"])
                    pin_number_id_list.append(chunk["pin_number_id"])
                    page_name_list.append(chunk["page_name"])
                    page_number_list.append(chunk["page_number"])
                    connectorID_list.append(chunk["connectorID"])
                    cavityID_list.append(chunk["cavityID"] if chunk["cavityID"] else "")
                    SOP_list.append(chunk["SOP"])
                    url_list.append(chunk["url"])
                    details_list.append(chunk["details"] if chunk["details"] else {})

                data = [
                    pin_number_list,
                    pin_number_id_list,
                    page_name_list,
                    page_number_list,
                    connectorID_list,
                    cavityID_list,
                    SOP_list,
                    url_list,
                    details_list,
                ]

                # 插入数据
                collection.insert(data)
            except Exception as e:
                logger.error(f"Failed to insert batch into collection '{collection_name}': {e}")
                logger.error("Failed to insert batch into collection '{data}'")
                return False
        collection.flush()
        logger.info(f"Successfully inserted {len(chunks)} chunks into collection '{collection_name}'")
        return True
    
    def sop_search(self, query: str, collection_name: str, top_k: int = 10, type: str = "text") -> List:
        """在指定集合中搜索sop相似数据
        
        Args:
            query: 查询文本
            collection_name: 集合名称
            top_k: 返回结果数量
            type: 搜索类型，可选值: "text" (对应pin_number)
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(f"Cannot search in collection '{collection_name}' - collection not available")
            return []

        try:
        # 验证type参数
            if type not in KEYWORD_MAPPING:
                logger.warning(f"Invalid type '{type}', using default 'text'")
                type = "text"
            
            anns_field = KEYWORD_MAPPING[type]

            # 定义搜索参数
            search_params = {
                'params': {'drop_ratio_search': 0.2},
            }
            
            # print('keyword query: ',query)
            
            # 执行搜索
            results = collection.search(
                data=[query],
                anns_field=anns_field,
                param=search_params,
                limit=top_k,
                output_fields=output_sop_fields
            )

            documents = []
            for hit in results[0]:
                entity = hit["entity"].copy()
                entity["score"] = hit["distance"]
                documents.append(entity)

            return documents 


        except Exception as e:
            logger.error(f"Search failed in collection '{collection_name}': {e}")
            return []

    def list_chunk_by_id(self, chunk_id: str, collection_name: str) -> List:
        """在指定集合中搜索语义相似数据图片

        Args:
            query_img: 查询图片路径
            collection_name: 集合名称
            top_k: 返回结果数量
            type: 搜索类型，可选值: "text" (对应embedding_text), "summary" (对应embedding_summary), "title" (对应embedding_title)
        """

        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot search in collection '{collection_name}' - collection not available"
            )
            return []

        try:
            # 查询所有记录，只返回knowledge_id, knowledge_name, knowledge_description字段
            results = collection.query(
                expr=(f"chunk_id == '{chunk_id}' "), output_fields=output_docment_fields
            )

            return results[0]

        except Exception as e:
            logger.error(f"Search failed in collection '{collection_name}': {e}")
            return []

    async def async_sop_search(self, query: str, collection_name: str, top_k: int = 10, type: str = "text") -> List:
        """在指定集合中搜索sop相似数据
        
        Args:
            query: 查询文本
            collection_name: 集合名称
            top_k: 返回结果数量
            type: 搜索类型，可选值: "text" (对应pin_number)
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(f"Cannot search in collection '{collection_name}' - collection not available")
            return []

        try:
            # 定义搜索参数
            search_params = {
                'params': {'drop_ratio_search': 0.2},
            }
            
            # print('keyword query: ',query)
            
            # 执行搜索
            results = collection.search(
                data=[query],
                anns_field="sparse_pin_number",
                param=search_params,
                limit=top_k,
                output_fields=output_docment_fields
            )

            documents = []
            for hit in results[0]:
                entity = hit["entity"].copy()
                entity["score"] = hit["distance"]
                documents.append(entity)

            return documents 

        except Exception as e:
            logger.error(f"Search failed in collection '{collection_name}': {e}")
            return []
    
    async def list_resources(self, collection_name: str) -> List[Resource]:
        """列出指定集合中所有唯一的knowledge_id，返回Resource列表

        Args:
            collection_name: 集合名称

        Returns:
            List[Resource]: Resource列表，包含去重后的knowledge_id及其相关信息
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot query from collection '{collection_name}' - collection not available"
            )
            return []

        try:
            # 查询所有记录，只返回knowledge_id, knowledge_name, knowledge_description字段
            results = collection.query(
                expr='knowledge_id != ""',  # 用于查询所有记录
                # output_fields=["knowledge_id", "knowledge_name", "knowledge_description"]
                output_fields=["knowledge_id"],
            )

            # 使用字典去重，以knowledge_id为key
            unique_knowledge = {}
            for result in results:
                knowledge_id = result.get("knowledge_id", "")
                if knowledge_id and knowledge_id not in unique_knowledge:
                    unique_knowledge[knowledge_id] = {
                        "knowledge_id": knowledge_id,
                        "knowledge_name": result.get("knowledge_name", ""),
                        "knowledge_description": result.get(
                            "knowledge_description", ""
                        ),
                    }

            # 构造Resource对象列表
            resources = [
                Resource(
                    knowledge_id=item["knowledge_id"],
                    knowledge_name=item["knowledge_name"],
                    knowledge_description=item["knowledge_description"],
                )
                for item in unique_knowledge.values()
            ]

            logger.info(
                f"Found {len(resources)} unique knowledge_ids in collection '{collection_name}'"
            )
            return resources

        except Exception as e:
            logger.error(
                f"Failed to list knowledge_ids from collection '{collection_name}': {e}"
            )
            return []

    async def semantics_search(
        self, query: str, collection_name: str, top_k: int = 10, type: str = "text"
    ) -> List[SearchModel]:
        """在指定集合中搜索语义相似数据

        Args:
            query: 查询文本
            collection_name: 集合名称
            top_k: 返回结果数量
            type: 搜索类型，可选值: "text" (对应embedding_text), "summary" (对应embedding_summary), "title" (对应embedding_title)
        """

        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot search in collection '{collection_name}' - collection not available"
            )
            return []

        try:
            # 验证type参数
            if type not in SEMANTICS_MAPPING:
                logger.warning(f"Invalid type '{type}', using default 'text'")
                type = "text"

            anns_field = SEMANTICS_MAPPING[type]
            # 生成查询向量
            query_embedding = await get_vllm_embedding(query)

            # 定义搜索参数
            search_params = {
                # "metric_type": "L2",
                "metric_type": "COSINE",
                "params": {"nprobe": 16},
            }

            # 执行搜索
            results = collection.search(
                data=[query_embedding],
                anns_field=anns_field,
                param=search_params,
                limit=top_k,
                output_fields=output_docment_fields,
            )

            documents = []
            for hit in results[0]:
                documents.append(
                    SearchModel(
                        chunk_id=hit.entity.chunk_id,
                        content=hit.entity.content,
                        summary=hit.entity.summary,
                        file_id=hit.entity.file_id,
                        file_path=hit.entity.file_path,
                        media_path=hit.entity.media_path,
                        chunk_source=hit.entity.chunk_source,
                        update_time=hit.entity.update_time,
                        bbox_type=hit.entity.bbox_type,
                        bbox=hit.entity.bbox,
                        title=hit.entity.title,
                        page_idx=hit.entity.page_idx,
                        others=hit.entity.others,
                        score=hit.distance,
                    )
                )

            return documents

        except Exception as e:
            logger.error(f"Search failed in collection '{collection_name}': {e}")
            return []

    async def kerword_search(
        self, query: str, collection_name: str, top_k: int = 10, type: str = "text"
    ) -> List[SearchModel]:
        """在指定集合中搜索语义相似数据

        Args:
            query: 查询文本
            collection_name: 集合名称
            top_k: 返回结果数量
            type: 搜索类型，可选值: "text" (对应embedding_text), "title" (对应embedding_title)
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot search in collection '{collection_name}' - collection not available"
            )
            return []

        try:
            # 验证type参数
            if type not in KEYWORD_MAPPING:
                logger.warning(f"Invalid type '{type}', using default 'text'")
                type = "text"

            anns_field = KEYWORD_MAPPING[type]

            # 定义搜索参数
            search_params = {
                "params": {"drop_ratio_search": 0.2},
            }

            print("keyword query: ", query)

            # 执行搜索
            results = collection.search(
                data=[query],
                anns_field=anns_field,
                param=search_params,
                limit=top_k,
                output_fields=output_docment_fields,
            )

            # print('======================',results)
            # 格式化结果

            documents = []
            for hit in results[0]:
                documents.append(
                    SearchModel(
                        chunk_id=hit.entity.chunk_id,
                        content=hit.entity.content,
                        summary=hit.entity.summary,
                        file_id=hit.entity.file_id,
                        file_path=hit.entity.file_path,
                        # knowledge_id=hit.entity.knowledge_id,
                        update_time=hit.entity.update_time,
                        media_path=hit.entity.media_path,
                        bbox_type=hit.entity.bbox_type,
                        bbox=hit.entity.bbox,
                        title=hit.entity.title,
                        page_idx=hit.entity.page_idx,
                        others=hit.entity.others,
                        score=hit.distance,
                    )
                )

            return documents

        except Exception as e:
            logger.error(f"Search failed in collection '{collection_name}': {e}")
            return []

    def hybrid_search_single_collection(
        self,
        query: str,
        collection_name: str,
        top_k: int = 10,
        dense_type: str = "text",
        sparse_type: str = "text",
        reranker_type: str = "weight",
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ) -> List[SearchModel]:
        """
        Milvus 原生混合检索（Dense + BM25）- 同步版本
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(f"Collection '{collection_name}' not available")
            return []

        try:
            if dense_type not in SEMANTICS_MAPPING:
                logger.warning(f"Invalid dense_type '{dense_type}', fallback to 'text'")
                dense_type = "text"

            if sparse_type not in KEYWORD_MAPPING:
                logger.warning(
                    f"Invalid sparse_type '{sparse_type}', fallback to 'text'"
                )
                sparse_type = "text"

            dense_field = SEMANTICS_MAPPING[dense_type]
            sparse_field = KEYWORD_MAPPING[sparse_type]

            try:
                query_embedding = get_embedding(query)
            except Exception as e:
                logger.error(f"Embedding model error: {e}")
                return []

            dense_request = AnnSearchRequest(
                data=[query_embedding],
                anns_field=dense_field,
                param={
                    "metric_type": "COSINE",
                    "params": {"nprobe": 16},
                },
                limit=top_k,
            )

            sparse_request = AnnSearchRequest(
                data=[query],  # BM25 直接传文本
                anns_field=sparse_field,
                param={"params": {"drop_ratio_search": 0.2}},
                limit=top_k,
            )

            if reranker_type != "weight":
                reranker = RRFRanker()
            else:
                reranker = WeightedRanker(dense_weight, sparse_weight)

            results = collection.hybrid_search(
                reqs=[dense_request, sparse_request],
                rerank=reranker,
                limit=top_k,
                output_fields=output_fields,
            )

            documents: List[SearchModel] = []
            for hit in results[0]:
                documents.append(
                    SearchModel(
                        chunk_id=hit.entity.chunk_id,
                        content=hit.entity.content,
                        summary=hit.entity.summary,
                        title=hit.entity.title,
                        media_path=hit.entity.media_path,
                        chunk_source=hit.entity.chunk_source,
                        file_id=hit.entity.file_id,
                        file_path=hit.entity.file_path,
                        update_time=hit.entity.update_time,
                        bbox_type=hit.entity.bbox_type,
                        bbox=hit.entity.bbox,
                        page_idx=hit.entity.page_idx,
                        others=hit.entity.others,
                        score=hit.score,
                    )
                )

            return documents

        except Exception as e:
            logger.error(f"Hybrid search failed in '{collection_name}': {e}")
            return []

    def hybrid_search(
        self,
        query: str,
        collection_names: list,
        top_k: int = 10,
        dense_type: str = "text",
        sparse_type: str = "text",
        reranker_type: str = "weight",
        threshold: float = 0.5,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        rerank_model: bool = False,
    ) -> List[SearchModel]:

        if not collection_names:
            return []

        documents: List[SearchModel] = []

        for col in collection_names:
            try:
                res = self.hybrid_search_single_collection(
                    query=query,
                    collection_name=col,
                    top_k=top_k * 2,  # 单库多取一点
                    dense_type=dense_type,
                    sparse_type=sparse_type,
                    reranker_type=reranker_type,
                    dense_weight=dense_weight,
                    sparse_weight=sparse_weight,
                )
                documents.extend(res)
            except Exception as e:
                logger.error(f"Hybrid search error in '{col}': {e}")

        # 去重（file_id + chunk_id）
        unique = {}
        for doc in documents:
            key = (doc.file_id, doc.chunk_id)
            if key not in unique:
                unique[key] = doc

        documents = list(unique.values())

        # 是否使用 rerank 模型
        if rerank_model:
            content_list = [doc.content for doc in documents]

            rerank_results = get_rerank(query, content_list)

            for item in rerank_results:
                idx = item["index"]
                documents[idx].score = float(item["score"])

            documents = [doc for doc in documents if doc.score >= threshold]
            documents.sort(key=lambda x: x.score, reverse=True)
            return documents[:top_k]

        # 不使用 rerank
        documents = [d for d in documents if d.score >= threshold]
        documents.sort(key=lambda x: x.score, reverse=True)
        return documents[:top_k]

    async def async_hybrid_search_single_collection(
        self,
        query: str,
        collection_name: str,
        top_k: int = 10,
        dense_type: str = "text",  # embedding_text / embedding_summary / embedding_title
        sparse_type: str = "text",  # sparse_content
        reranker_type: str = "weight",
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ) -> List[SearchModel]:
        """
        Milvus 原生混合检索（Dense + BM25）

        Args:
            query: 查询文本
            collection_name: 集合名
            top_k: 返回结果数
            dense_type: Dense 向量字段类型
            sparse_type: Sparse/BM25 字段类型
            threshold: 阈值过滤，目前使用cos，范围0-1
            dense_weight: Dense 权重
            sparse_weight: Sparse 权重
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(f"Collection '{collection_name}' not available")
            return []

        try:
            if dense_type not in SEMANTICS_MAPPING:
                logger.warning(f"Invalid dense_type '{dense_type}', fallback to 'text'")
                dense_type = "text"

            if sparse_type not in KEYWORD_MAPPING:
                logger.warning(
                    f"Invalid sparse_type '{sparse_type}', fallback to 'text'"
                )
                sparse_type = "text"

            dense_field = SEMANTICS_MAPPING[dense_type]
            sparse_field = KEYWORD_MAPPING[sparse_type]

            try:
                query_embedding = await get_async_embedding(query)
            except Exception as e:
                logger.error(f"Embedding model error: {e}")
                return []

            dense_request = AnnSearchRequest(
                data=[query_embedding],
                anns_field=dense_field,
                param={
                    "metric_type": "COSINE",
                    "params": {"nprobe": 16},
                },
                limit=top_k,
            )

            sparse_request = AnnSearchRequest(
                data=[query],  # 注意：BM25 直接传文本
                anns_field=sparse_field,
                param={"params": {"drop_ratio_search": 0.2}},
                limit=top_k,
            )

            if reranker_type != "weight":
                reranker = RRFRanker()

            else:
                reranker = WeightedRanker(dense_weight, sparse_weight)

            results = collection.hybrid_search(
                reqs=[dense_request, sparse_request],
                rerank=reranker,
                limit=top_k,
                output_fields=output_fields,
            )

            documents: List[SearchModel] = []
            for hit in results[0]:
                documents.append(
                    SearchModel(
                        chunk_id=hit.entity.chunk_id,
                        content=hit.entity.content,
                        summary=hit.entity.summary,
                        title=hit.entity.title,
                        media_path=hit.entity.media_path,
                        chunk_source=hit.entity.chunk_source,
                        file_id=hit.entity.file_id,
                        file_path=hit.entity.file_path,
                        update_time=hit.entity.update_time,
                        bbox_type=hit.entity.bbox_type,
                        bbox=hit.entity.bbox,
                        page_idx=hit.entity.page_idx,
                        others=hit.entity.others,
                        score=hit.score,
                    )
                )

            return documents

        except Exception as e:
            logger.error(f"Hybrid search failed in '{collection_name}': {e}")
            return []

    async def async_hybrid_search(
        self,
        query: str,
        collection_names: list,
        top_k: int = 10,
        dense_type: str = "text",  # embedding_text / embedding_summary / embedding_title
        sparse_type: str = "text",  # sparse_content
        reranker_type: str = "weight",
        threshold: float = 0.5,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        rerank_model: bool = False,
    ) -> List[SearchModel]:

        if not collection_names:
            return []

        async def _run(col):
            async with sem:
                return await self.async_hybrid_search_single_collection(
                    query=query,
                    collection_name=col,
                    top_k=top_k * 2,  # 单库多取一点，避免被截断
                    dense_type=dense_type,
                    sparse_type=sparse_type,
                    reranker_type=reranker_type,
                    dense_weight=dense_weight,
                    sparse_weight=sparse_weight,
                )

        # 并发执行每个 collection 的 hybrid_search
        tasks = [_run(col) for col in collection_names]

        results_per_collection = await asyncio.gather(*tasks, return_exceptions=True)

        documents: List[SearchModel] = []
        for res in results_per_collection:
            if isinstance(res, Exception):
                logger.error(f"Hybrid search error: {res}")
                continue
            documents.extend(res)

        unique = {}
        for doc in documents:
            key = (doc.file_id, doc.chunk_id)
            if key not in unique:
                unique[key] = doc

        documents = list(unique.values())

        if rerank_model:
            content_list = [doc.content for doc in documents]
            rerank_results = await get_async_rerank(query, content_list)
            for items in rerank_results:
                idx = items["index"]
                documents[idx].score = float(items["score"])

            # 根据score阈值过滤
            filtered_docs = [doc for doc in documents if doc.score >= threshold]

            filtered_docs.sort(key=lambda x: x.score, reverse=True)
            return filtered_docs[:top_k]

        documents = [d for d in documents if d.score >= threshold]
        documents.sort(key=lambda x: x.score, reverse=True)
        return documents[:top_k]

    # async def hybrid_search(
    #     self,
    #     query: str,
    #     collection_name: str,
    #     top_k: int = 10,
    #     dense_type: str = "text",      # embedding_text / embedding_summary / embedding_title
    #     sparse_type: str = "text",     # sparse_content
    #     reranker_type: str = "weight",
    #     threshold: float = 0.5,
    #     dense_weight: float = 0.7,
    #     sparse_weight: float = 0.3,
    #     rerank_model : bool=False
    # ) -> List[SearchModel]:
    #     """
    #     Milvus 原生混合检索（Dense + BM25）

    #     Args:
    #         query: 查询文本
    #         collection_name: 集合名
    #         top_k: 返回结果数
    #         dense_type: Dense 向量字段类型
    #         sparse_type: Sparse/BM25 字段类型
    #         threshold: 阈值过滤，目前使用cos，范围0-1
    #         dense_weight: Dense 权重
    #         sparse_weight: Sparse 权重
    #     """
    #     collection = self._get_collection_safe(collection_name)
    #     if not collection:
    #         logger.error(f"Collection '{collection_name}' not available")
    #         return []
    #     if rerank_model:
    #         top_k = top_k * 2

    #     try:
    #         if dense_type not in SEMANTICS_MAPPING:
    #             logger.warning(f"Invalid dense_type '{dense_type}', fallback to 'text'")
    #             dense_type = "text"

    #         if sparse_type not in KEYWORD_MAPPING:
    #             logger.warning(f"Invalid sparse_type '{sparse_type}', fallback to 'text'")
    #             sparse_type = "text"

    #         dense_field = SEMANTICS_MAPPING[dense_type]
    #         sparse_field = KEYWORD_MAPPING[sparse_type]

    #         try:
    #             query_embedding = await get_async_embedding(query)
    #         except Exception as e:
    #             logger.error(f"Embedding model error: {e}")
    #             return []

    #         dense_request = AnnSearchRequest(
    #             data=[query_embedding],
    #             anns_field=dense_field,
    #             param={
    #                 "metric_type": "COSINE",
    #                 "params": {"nprobe": 16},
    #             },
    #             limit=top_k,
    #         )

    #         sparse_request = AnnSearchRequest(
    #             data=[query],                  # 注意：BM25 直接传文本
    #             anns_field=sparse_field,
    #             param={
    #                 "params": {
    #                     "drop_ratio_search": 0.2
    #                 }
    #             },
    #             limit=top_k,
    #         )

    #         if reranker_type != "weight":
    #             reranker = RRFRanker()

    #         else:
    #             reranker = WeightedRanker(dense_weight, sparse_weight)

    #         results = collection.hybrid_search(
    #             reqs=[dense_request, sparse_request],
    #             rerank=reranker,
    #             limit=top_k,
    #             output_fields=output_fields
    #         )

    #         documents: List[SearchModel] = []
    #         content_list = []
    #         for hit in results[0]:
    #             if not rerank_model and hit.score < threshold:
    #                 continue
    #             content_list.append(hit.entity.content)
    #             documents.append(
    #                 SearchModel(
    #                     chunk_id=hit.entity.chunk_id,
    #                     content=hit.entity.content,
    #                     summary=hit.entity.summary,
    #                     title=hit.entity.title,
    #                     media_path=hit.entity.media_path,
    #                     chunk_source=hit.entity.chunk_source,
    #                     file_id=hit.entity.file_id,
    #                     file_path=hit.entity.file_path,
    #                     update_time=hit.entity.update_time,
    #                     bbox_type=hit.entity.bbox_type,
    #                     bbox=hit.entity.bbox,
    #                     page_idx=hit.entity.page_idx,
    #                     others=hit.entity.others,
    #                     score=hit.score,  # ⚠️ hybrid 用 score，不是 distance
    #                 )
    #             )

    #         # print('yuancheng---------',documents)
    # if rerank_model and content_list:
    #     rerank_results = await get_async_rerank(query, content_list)
    #     for items in rerank_results:
    #         idx = items['index']
    #         new_score = items['score']

    #         documents[idx].score = float(new_score)

    #     # 根据score阈值过滤
    #     filtered_docs = [doc for doc in documents if doc.score >= threshold]

    #     filtered_docs.sort(key=lambda x: x.score, reverse=True)
    #     return filtered_docs[:top_k//2]

    # return documents

    #     except Exception as e:
    #         logger.error(f"Hybrid search failed in '{collection_name}': {e}")
    #         return []

    async def delete_by_file_id(self, file_id: str, collection_name: str) -> bool:
        """根据文件ID删除数据"""
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot delete from collection '{collection_name}' - collection not available"
            )
            return False

        try:
            # 构造查询表达式
            query_expr = f'file_id == "{file_id}"'

            # 查询符合条件的文档
            results = collection.query(query_expr, output_fields=["id"])
            delete_ids = [result["id"] for result in results]

            # 如果找到匹配的文档，执行删除操作
            if delete_ids:
                delete_expr = f"id in {delete_ids}"
                collection.delete(delete_expr)
                collection.flush()  # 确保删除操作立即生效
                logger.info(
                    f"Successfully deleted {len(delete_ids)} documents for file_id: {file_id}"
                )
                return True
            else:
                logger.info(f"No documents found for file_id: {file_id}")
                return True

        except Exception as e:
            logger.error(
                f"Error deleting file_id {file_id} from collection {collection_name}: {e}"
            )
            return False

    async def delete_by_chunk_id(self, chunk_id: str, collection_name: str) -> bool:
        """根据chunk_id删除数据"""
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot delete from collection '{collection_name}' - collection not available"
            )
            return False

        try:
            # 构造查询表达式
            query_expr = f'chunk_id == "{chunk_id}"'

            # 查询符合条件的文档
            results = collection.query(query_expr, output_fields=["id"])
            delete_ids = [result["id"] for result in results]

            # 如果找到匹配的文档，执行删除操作
            if delete_ids:
                delete_expr = f"id in {delete_ids}"
                collection.delete(delete_expr)
                collection.flush()  # 确保删除操作立即生效
                logger.info(
                    f"Successfully deleted {len(delete_ids)} documents for chunk_id: {chunk_id}"
                )
                return True
            else:
                logger.info(f"No documents found for chunk_id: {chunk_id}")
                return True

        except Exception as e:
            logger.error(
                f"Error deleting chunk_id {chunk_id} from collection {collection_name}: {e}"
            )
            return False

    async def delete_by_knowledge_id(
        self, knowledge_id: str, collection_name: str
    ) -> bool:
        """根据knowledge_id删除数据"""
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot delete from collection '{collection_name}' - collection not available"
            )
            return False

        try:
            # 构造查询表达式
            query_expr = f'knowledge_id == "{knowledge_id}"'

            # 查询符合条件的文档
            results = collection.query(query_expr, output_fields=["id"])
            delete_ids = [result["id"] for result in results]

            # 如果找到匹配的文档，执行删除操作
            if delete_ids:
                delete_expr = f"id in {delete_ids}"
                collection.delete(delete_expr)
                collection.flush()  # 确保删除操作立即生效
                logger.info(
                    f"Successfully deleted {len(delete_ids)} documents for knowledge_id: {knowledge_id}"
                )
                return True
            else:
                logger.info(f"No documents found for knowledge_id: {knowledge_id}")
                return True

        except Exception as e:
            logger.error(
                f"Error deleting knowledge_id {knowledge_id} from collection {collection_name}: {e}"
            )
            return False

    async def insert(self, collection_name: str, chunks, summary: bool = False) -> bool:
        """插入数据到指定集合"""
        if collection_name not in self.collections:
            await self.create_collection(collection_name)

        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot insert into collection '{collection_name}' - collection not available"
            )
            return False
        from markdownify import markdownify as md

        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            try:
                # 准备数据
                bbox_type_list, title_list, bbox_list, page_idx_list = [], [], [], []
                content_list, summary_list, chunk_id_list = [], [], []
                file_id_list, file_path_list, update_time_list, media_path_list = [], [], [], []
                others_list = []
                chunk_source_list = []

                for chunk in batch:
                    # if not chunk.content:   # 针对没有 title 的图和表，后面做优化
                    #     continue
                    if not chunk.summary and summary and chunk.content:
                        chunk.summary = chunk.content

                    parts = []
                    if chunk.title:
                        parts.append(chunk.title)
                    if chunk.content:
                        parts.append(chunk.content)
                    if chunk.others:
                        md_content = md(chunk.others["table_body"])
                        parts.append(md_content)

                    bbox_type_list.append(chunk.bbox_type)
                    title_list.append(chunk.title)
                    bbox_list.append(chunk.bbox)
                    page_idx_list.append(chunk.page_idx)
                    # content_list.append(chunk.content)
                    content_list.append("\n".join(parts))
                    summary_list.append(chunk.summary)
                    media_path_list.append(chunk.media_path)
                    chunk_source_list.append(chunk.chunk_source)
                    chunk_id_list.append(chunk.chunk_id)
                    file_id_list.append(chunk.file_id)
                    file_path_list.append(chunk.file_path)
                    update_time_list.append(chunk.update_time)
                    others_list.append(chunk.others if chunk.others else {})

                # 生成嵌入向量
                embedding_text_list = await get_async_embedding(content_list)
                embedding_title_list = await get_async_embedding(title_list)
                if summary:
                    embedding_summary_list = await get_async_embedding(summary_list)
                else:
                    embedding_summary_list = [[0.0] * 1024 for _ in range(len(batch))]

                data = [
                    chunk_id_list,
                    content_list,
                    file_id_list,
                    file_path_list,
                    update_time_list,
                    bbox_type_list,
                    title_list,
                    summary_list,
                    media_path_list,
                    chunk_source_list,
                    embedding_summary_list,
                    bbox_list,
                    page_idx_list,
                    embedding_text_list,
                    embedding_title_list,
                    others_list,
                ]

                # 插入数据
                collection.insert(data)
            except Exception as e:
                logger.error(
                    f"Failed to insert batch into collection '{collection_name}': {e}"
                )
                logger.error("Failed to insert batch into collection '{data}'")
                return False
        collection.flush()
        logger.info(
            f"Successfully inserted {len(chunks)} chunks into collection '{collection_name}'"
        )
        return True


    async def list_chunks(self, collection_name: str, title: str, file_id: str) -> List:
        """列出指定集合中所有唯一的knowledge_id，返回Resource列表

        Args:
            collection_name: 集合名称

        Returns:
            List[Resource]: Resource列表，包含去重后的knowledge_id及其相关信息
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot query from collection '{collection_name}' - collection not available"
            )
            return []

        try:
            # 查询所有记录，只返回knowledge_id, knowledge_name, knowledge_description字段
            results = collection.query(
                expr=(f"title == '{title}' " f"AND file_id == '{file_id}'"),
                output_fields=output_fields,
            )

            return results

        except Exception as e:
            logger.error(
                f"Failed to list knowledge_ids from collection '{collection_name}': {e}"
            )
            return []

    async def list_chunks_by_title(self, collection_name: str, title: str) -> List:
        """列出指定集合中所有唯一的knowledge_id，返回Resource列表

        Args:
            collection_name: 集合名称

        Returns:
            List[Resource]: Resource列表，包含去重后的knowledge_id及其相关信息
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot query from collection '{collection_name}' - collection not available"
            )
            return []

        try:
            # 查询所有记录，只返回knowledge_id, knowledge_name, knowledge_description字段
            results = collection.query(
                expr=(f"title == '{title}' "), output_fields=output_fields
            )

            return results

        except Exception as e:
            logger.error(
                f"Failed to list knowledge_ids from collection '{collection_name}': {e}"
            )
            return []

    async def delete_collection(self, collection_name: str) -> bool:
        """删除整个集合（包括所有数据）

        Args:
            collection_name: 要删除的集合名称

        Returns:
            bool: 删除是否成功
        """
        # 检查集合是否存在
        if not self._collection_exists(collection_name):
            logger.warning(f"Collection '{collection_name}' does not exist")
            return False

        try:
            # 如果集合在缓存中，先释放它
            if collection_name in self.collections:
                collection = self.collections[collection_name]
                try:
                    collection.release()
                except Exception as e:
                    logger.debug(
                        f"Failed to release collection '{collection_name}': {e}"
                    )

            # 删除集合
            Collection(collection_name).drop()

            # 从缓存中移除
            self.collections.pop(collection_name, None)
            self.loaded_collections.discard(collection_name)

            logger.info(f"Collection '{collection_name}' deleted successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to delete collection '{collection_name}': {e}")
            return False

    def unload_collection(self, collection_name: str) -> bool:
        """卸载集合以释放内存"""
        try:
            if collection_name in self.collections:
                collection = self.collections[collection_name]
                collection.release()
                self.loaded_collections.discard(collection_name)
                logger.info(f"Collection '{collection_name}' unloaded successfully")
                return True
            else:
                logger.warning(f"Collection '{collection_name}' not found in cache")
                return False
        except Exception as e:
            logger.error(f"Failed to unload collection '{collection_name}': {e}")
            return False

    def get_loaded_collections(self) -> List[str]:
        """获取当前已加载的集合列表"""
        return list(self.loaded_collections)

    def get_all_collections(self) -> List[str]:
        """获取所有可用集合列表（不加载）"""
        try:
            return utility.list_collections()
        except Exception as e:
            logger.error(f"Failed to get collection list: {e}")
            return []

    def close(self):
        """关闭连接并清理资源"""
        try:
            # 卸载所有已加载的集合
            for collection_name in list(self.loaded_collections):
                self.unload_collection(collection_name)

            connections.disconnect("default")
            logger.info("Milvus connection closed and all collections unloaded")
        except Exception as e:
            logger.error(f"Error closing Milvus connection: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# if __name__ == "__main__":
#     milvus_client = MilvusClient()
    # milvus_client.memory_insert(messages="叫爸爸", user_id="123", thread_id="789")
    # milvus_client.memory_search(query="爸爸",user_id="123")
