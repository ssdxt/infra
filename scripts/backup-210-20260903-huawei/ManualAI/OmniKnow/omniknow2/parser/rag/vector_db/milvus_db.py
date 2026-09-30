import asyncio
import os
import time
from typing import Any, Dict, List, Optional, Set

from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel, Field
from parser.utils import (
    download_image,
    get_img_embedding,
    async_get_img_embedding,
    is_img_search_enabled,
    get_vllm_embedding as get_embedding,
    async_get_vllm_embedding as async_get_embedding,
    get_vllm_rerank as get_rerank,
)
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
# LRU 缓存配置：最大同时加载的集合数量
MAX_LOADED_COLLECTIONS = int(os.getenv("MILVUS_MAX_LOADED_COLLECTIONS", 20))
IMG_DOWNLOAD_DIR = os.getenv("IMG_DOWNLOAD_DIR")

# 根据type参数映射到对应的anns_field
SEMANTICS_MAPPING = {
    "text": "embedding_text",
    "summary": "embedding_summary",
    "title": "embedding_title",
}

KEYWORD_MAPPING = {"text": "sparse_content", "title": "sparse_title"}

output_fields = [
    "chunk_id",
    "chunk_index",
    "bbox_type",
    "title",
    "cur_title",
    "par_title",
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
output_sop_fields = ["pin_number", "pin_number_id", "page_name", "page_number", "connectorID", "cavityID", "SOP", "url"]

# 通用索引参数，供 doc/image/memory 等集合复用
VECTOR_INDEX_PARAMS = {
    "index_type": "IVF_FLAT",
    "metric_type": "COSINE",
    "index_name": "vector_index",
    "params": {"nlist": 128},
}
BM25_INDEX_PARAMS = {
    "index_type": "SPARSE_INVERTED_INDEX",
    "metric_type": "BM25",
    "params": {
        "inverted_index_algo": "DAAT_MAXSCORE",
        "bm25_k1": 1.2,
        "bm25_b": 0.75,
    },
}


class Resource(BaseModel):
    """
    Resource is a class that represents a resource.
    """

    knowledge_id: str = Field(..., description="The id of the knowledge")
    knowledge_name: str = Field(..., description="The name of the knowledge")
    knowledge_description: str | None = Field(
        "", description="The description of the knowledge"
    )


class LRUCache:
    """LRU 缓存，用于跟踪集合的访问时间和顺序"""
    def __init__(self, max_size: int = MAX_LOADED_COLLECTIONS):
        self.max_size = max_size
        self.access_order: List[str] = []  # 按访问时间排序，最久未使用的在最后
        self.access_time: Dict[str, float] = {}  # 记录每个集合的最后访问时间
    
    def touch(self, key: str):
        """更新集合的访问时间"""
        current_time = time.time()
        # 如果已存在，从访问顺序中移除
        if key in self.access_order:
            self.access_order.remove(key)
        # 添加到最前面（最近访问）
        self.access_order.insert(0, key)
        self.access_time[key] = current_time
    
    def get_lru(self) -> Optional[str]:
        """获取最久未使用的集合名称"""
        if not self.access_order:
            return None
        return self.access_order[-1]
    
    def remove(self, key: str):
        """移除集合"""
        if key in self.access_order:
            self.access_order.remove(key)
        if key in self.access_time:
            del self.access_time[key]
    
    def size(self) -> int:
        """返回当前缓存的集合数量"""
        return len(self.access_order)
    
    def clear(self):
        """清空缓存"""
        self.access_order.clear()
        self.access_time.clear()


def _hit_to_search_model(hit, collection_name: str, score_attr: str = "score") -> SearchModel:
    """将 hybrid_search 的 hit 转为 SearchModel"""
    entity = hit.entity
    score = getattr(hit, score_attr, hit.distance if hasattr(hit, "distance") else 0.0)
    return SearchModel(
        chunk_id=entity.chunk_id,
        chunk_index=getattr(entity, "chunk_index", 0),
        content=entity.content,
        summary=entity.summary,
        title=entity.title,
        cur_title=getattr(entity, "cur_title", ""),
        par_title=getattr(entity, "par_title", ""),
        media_path=entity.media_path,
        chunk_source=entity.chunk_source,
        file_id=entity.file_id,
        file_path=entity.file_path,
        update_time=entity.update_time,
        bbox_type=entity.bbox_type,
        bbox=entity.bbox,
        page_idx=entity.page_idx,
        others=entity.others or {},
        score=float(score),
        collection_name=collection_name,
    )


def _entity_dict_to_search_model(entity: dict, score: float, collection_name: str) -> SearchModel:
    """将 query 返回的 entity 字典转为 SearchModel"""
    return SearchModel(
        chunk_id=entity.get("chunk_id", ""),
        chunk_index=entity.get("chunk_index", 0),
        content=entity.get("content", ""),
        summary=entity.get("summary", ""),
        title=entity.get("title", ""),
        cur_title=entity.get("cur_title", ""),
        par_title=entity.get("par_title", ""),
        media_path=entity.get("media_path", ""),
        chunk_source=entity.get("chunk_source", ""),
        file_id=entity.get("file_id", ""),
        file_path=entity.get("file_path", ""),
        update_time=entity.get("update_time", ""),
        bbox_type=entity.get("bbox_type", ""),
        bbox=entity.get("bbox", []),
        page_idx=entity.get("page_idx", []),
        others=entity.get("others", {}),
        score=float(score),
        collection_name=collection_name,
    )


def _normalize_pages(value) -> List[int]:
    """将 page_idx 规范为 int 列表"""
    if value is None:
        return []
    if isinstance(value, list):
        return [int(v) for v in value if isinstance(v, (int, float))]
    if isinstance(value, (int, float)):
        return [int(value)]
    return []


class MilvusClient:
    def __init__(self, **kwargs):
        self.milvus_host = os.getenv("MILVUS_HOST")
        self.milvus_port = os.getenv("MILVUS_PORT")
        self.collections: Dict[str, Collection] = {}
        self.loaded_collections: set = set()  # 跟踪已加载的集合
        self.lru_cache = LRUCache(max_size=MAX_LOADED_COLLECTIONS)  # LRU 缓存

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
        """确保集合被加载到内存中（懒加载），实现 LRU 缓存机制"""
        collection_name = collection.name

        # 检查是否需要释放最久未使用的集合
        if collection_name not in self.loaded_collections:
            # 如果已达到最大加载数量，释放最久未使用的集合
            while len(self.loaded_collections) >= MAX_LOADED_COLLECTIONS:
                lru_collection_name = self.lru_cache.get_lru()
                if lru_collection_name and lru_collection_name != collection_name and lru_collection_name in self.loaded_collections:
                    logger.info(
                        f"Reaching max loaded collections limit ({MAX_LOADED_COLLECTIONS}), "
                        f"unloading LRU collection: '{lru_collection_name}'"
                    )
                    self._unload_collection_internal(lru_collection_name)
                else:
                    # 如果没有其他集合可以释放，或者当前集合就是最久未使用的，直接加载
                    # 如果 LRU 缓存为空，清空已加载集合的缓存状态
                    if not lru_collection_name:
                        # 同步 LRU 缓存和实际加载状态
                        for loaded_name in list(self.loaded_collections):
                            if loaded_name not in self.lru_cache.access_order:
                                self.lru_cache.touch(loaded_name)
                    break

        # 如果已经加载过，更新访问时间并返回
        if utility.load_state(collection_name) == LoadState.Loaded:
            self.loaded_collections.add(collection_name)
            self.lru_cache.touch(collection_name)
            return True

        try:
            # 尝试加载集合
            collection.load()
            self.loaded_collections.add(collection_name)
            self.lru_cache.touch(collection_name)
            logger.info(f"Collection '{collection_name}' loaded successfully")
            return True
        except Exception as e:
            # 如果加载失败，可能是因为集合已经加载或其他原因
            try:
                # 尝试通过简单查询来验证集合是否可用
                self.loaded_collections.add(collection_name)
                self.lru_cache.touch(collection_name)
                logger.info(f"Collection '{collection_name}' is already loaded")
                return True
            except Exception as inner_e:
                logger.error(
                    f"Failed to load collection '{collection_name}': {e}, verification failed: {inner_e}"
                )
                return False
    
    def _unload_collection_internal(self, collection_name: str) -> bool:
        """内部方法：卸载集合（不记录日志，用于自动释放）"""
        try:
            if collection_name in self.collections:
                collection = self.collections[collection_name]
                try:
                    collection.release()
                    self.loaded_collections.discard(collection_name)
                    self.lru_cache.remove(collection_name)
                    logger.debug(f"Collection '{collection_name}' unloaded automatically")
                    return True
                except Exception as e:
                    logger.debug(f"Failed to release collection '{collection_name}': {e}")
                    return False
            return False
        except Exception as e:
            logger.debug(f"Error unloading collection '{collection_name}': {e}")
            return False

    def _get_collection_safe(self, collection_name: str) -> Optional[Collection]:
        """安全地获取集合，按需加载（懒加载），实现 LRU 缓存机制"""
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

            # 懒加载：只有在实际使用时才加载到内存，并更新 LRU 缓存
            if not self._ensure_collection_loaded(collection):
                logger.warning(
                    f"Collection '{collection_name}' may not be fully loaded, but will try to proceed"
                )
            else:
                # 更新访问时间（即使已经加载，也要更新 LRU 状态）
                self.lru_cache.touch(collection_name)

            return collection

        except Exception as e:
            logger.error(f"Error getting collection '{collection_name}': {e}")
            return None

    def _collection_exists(self, collection_name: str) -> bool:
        """检查集合是否存在"""
        return utility.has_collection(collection_name)

    async def create_doc_collection(self, collection_name: str, analyzer: str = "chinese"):
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
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
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
                    max_length=1024,
                    enable_analyzer=True,
                    analyzer_params=analyzer_params,
                    enable_match=True,
                ),
                FieldSchema(name="cur_title", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="par_title", dtype=DataType.VARCHAR, max_length=512),
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
            for field in ("embedding_text", "embedding_summary", "embedding_title"):
                collection.create_index(field, VECTOR_INDEX_PARAMS)
            for field in ("sparse_content", "sparse_title"):
                collection.create_index(field, BM25_INDEX_PARAMS)

            # 加载集合
            collection.load()

            self.collections[collection_name] = collection
            self.loaded_collections.add(collection_name)
            self.lru_cache.touch(collection_name)
            logger.info(
                f"Successfully created and loaded collection: {collection_name}"
            )

        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            raise
    
        
    async def document_insert(self, collection_name: str, chunks, summary: bool = False) -> bool:
        """插入数据到指定集合"""
        if collection_name not in self.collections:
            await self.create_doc_collection(collection_name)

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
                chunk_index_list = []
                file_id_list, file_path_list, update_time_list, media_path_list = [], [], [], []
                content_embedding_list = []
                cur_title_list = []
                par_title_list = []
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
                    if chunk.others and chunk.others.get("table_body"):
                        md_content = md(chunk.others["table_body"])
                        parts.append(md_content)

                    bbox_type_list.append(chunk.bbox_type)
                    title_list.append(chunk.title)
                    cur_title_list.append(chunk.cur_title)
                    par_title_list.append(chunk.par_title)
                    bbox_list.append(chunk.bbox)
                    page_idx_list.append(chunk.page_idx)
                    content_list.append(chunk.content)
                    content_embedding_list.append("\n".join(parts))  # 给embedding用的
                    summary_list.append(chunk.summary)
                    media_path_list.append(chunk.media_path)
                    chunk_source_list.append(chunk.chunk_source)
                    chunk_id_list.append(chunk.chunk_id)
                    chunk_index_list.append(chunk.chunk_index)
                    file_id_list.append(chunk.file_id)
                    file_path_list.append(chunk.file_path)
                    update_time_list.append(chunk.update_time)
                    others_list.append(chunk.others if chunk.others else {})

                # 生成嵌入向量
                embedding_text_list = await async_get_embedding(content_embedding_list)
                embedding_title_list = await async_get_embedding(title_list)
                if summary:
                    embedding_summary_list = await async_get_embedding(summary_list)
                else:
                    embedding_summary_list = [[0.0] * 1024 for _ in range(len(batch))]

                data = [
                    chunk_id_list,
                    chunk_index_list,
                    content_list,
                    file_id_list,
                    file_path_list,
                    update_time_list,
                    bbox_type_list,
                    title_list,
                    cur_title_list,
                    par_title_list,
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
                logger.error(f"Failed to insert batch into collection '{collection_name}': {e}")
                # return False
                raise
        collection.flush()
        logger.info(
            f"Successfully inserted {len(chunks)} chunks into collection '{collection_name}'"
        )
        return True
    
    
    def list_chunks_by_par_title(self, collection_name: str, file_id: str, par_title: str) -> List:
        """根据file_id和par_title获取所有的chunk
        
        Args:
            collection_name: 集合名称
            file_id: 文件ID
            par_title: 父级标题
            
        Returns:
            List: 匹配的chunk列表
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot query from collection '{collection_name}' - collection not available"
            )
            return []

        try:
            # 查询所有匹配的chunk
            results = collection.query(
                expr=(f"file_id == '{file_id}' " f"AND par_title == '{par_title}'"),
                output_fields=output_fields,
            )

            logger.info(
                f"Found {len(results)} chunks for file_id='{file_id}' and par_title='{par_title}' in collection '{collection_name}'"
            )
            return results

        except Exception as e:
            logger.error(
                f"Failed to query chunks by file_id and par_title from collection '{collection_name}': {e}"
            )
            return []
    
    
    def list_chunks_by_chunk_index(self, collection_name: str, file_id: str, chunk_index: int, return_number: int=3) -> List:
        """根据file_id和chunk_index获取所有的chunk
        
        Args:
            collection_name: 集合名称
            file_id: 文件ID
            return_number: 前后各返回的chunk数量，默认3（共返回2*return_number+1个）

            
        Returns:
            List: 匹配的chunk列表
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot query from collection '{collection_name}' - collection not available"
            )
            return []

        try:
            # 查询所有匹配的chunk
            results = collection.query(
                expr=f"file_id == '{file_id}'",
                output_fields=output_fields,
            )
            
            if not results:
                logger.info(
                    f"No chunks found for file_id='{file_id}' in collection '{collection_name}'"
                )
                return []
            
           # 按chunk_index排序
            sorted_results = sorted(results, key=lambda x: x.get("chunk_index", 0))

            # 找到目标chunk_index的位置
            target_idx = None
            for idx, chunk in enumerate(sorted_results):
                if chunk.get("chunk_index") == chunk_index:
                    target_idx = idx
                    break

            if target_idx is None:
                logger.warning(
                    f"Chunk with chunk_index={chunk_index} not found for file_id='{file_id}' in collection '{collection_name}'"
                )
                return []

            # 计算前后索引范围
            start_idx = max(0, target_idx - return_number)
            end_idx = min(len(sorted_results), target_idx + return_number + 1)

            # 提取结果
            result_chunks = sorted_results[start_idx:end_idx]

            logger.info(
                f"Found {len(result_chunks)} chunks (target chunk_index={chunk_index}, "
                f"range: {sorted_results[start_idx].get('chunk_index')} to "
                f"{sorted_results[end_idx-1].get('chunk_index')}) "
                f"for file_id='{file_id}' in collection '{collection_name}'"
            )
            return result_chunks

        except Exception as e:
            logger.error(
                f"Failed to query chunks by file_id and par_title from collection '{collection_name}': {e}"
            )
            return []
    
    def doc_search_single_collection(
        self,
        query: str,
        collection_name: str,
        top_k: int = 10,
        dense_type: str = "text",
        sparse_type: str = "text",
        reranker_type: str = "weight",
        context_chars: int = 800,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        **kwargs
    ) -> List[SearchModel]:
        """
        Milvus 原生混合检索（Dense + BM25）- 同步版本
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(f"Collection '{collection_name}' not available")
            return []

        try:
            start_time = time.perf_counter()
            expr = kwargs.get("expr", "")
            # parent_context = kwargs.get("parent_context", False)
            # get_chunks_by_par_title = kwargs.get("get_chunks_by_par_title", False)
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
                logger.debug(f"query embedding 耗时: {(time.perf_counter() - start_time) * 1000:.0f}ms")
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
                expr=expr
            )

            sparse_request = AnnSearchRequest(
                data=[query],  # BM25 直接传文本
                anns_field=sparse_field,
                param={"params": {"drop_ratio_search": 0.2}},
                limit=top_k,
                expr=expr
                
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

            documents = [_hit_to_search_model(hit, collection_name) for hit in results[0]]
            logger.debug(f"检索总耗时: {(time.perf_counter() - start_time) * 1000:.0f}ms")
            return documents

        except Exception as e:
            logger.error(f"Hybrid search failed in '{collection_name}': {e}")
            return []

    def doc_search(
        self,
        query: str,
        collection_names: list,
        top_k: int = 10,
        dense_type: str = "text",
        sparse_type: str = "text",
        reranker_type: str = "weight",
        context_chars: int = 600,
        threshold: float = 0.5,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        rerank_model: bool = False,
        **kwargs
    ) -> List[SearchModel]:

        if not collection_names:
            return []

        documents: List[SearchModel] = []

        for col in collection_names:
            try:
                res = self.doc_search_single_collection(
                    query=query,
                    collection_name=col,
                    top_k=top_k * 6,  # 单库多取一点
                    dense_type=dense_type,
                    context_chars=context_chars,
                    sparse_type=sparse_type,
                    reranker_type=reranker_type,
                    dense_weight=dense_weight,
                    sparse_weight=sparse_weight,
                    **kwargs
                )
                
                documents.extend(res)
            except Exception as e:
                logger.error(f"Hybrid search error in '{col}': {e}")
        print('=====================================',documents)
        # 去重（file_id + chunk_id）
        unique = {}
        for doc in documents:
            key = (doc.file_id, doc.chunk_id)
            if key not in unique:
                unique[key] = doc

        documents = list(unique.values())
        
        # 是否使用 rerank 模型
        if rerank_model:
            content_list = [doc.title +'\n'+ doc.content for doc in documents]

            rerank_results = get_rerank(query, content_list)
            # print("rerank_results:", rerank_results)
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
    
    async def keyword_search(
        self,
        query: str,
        collection_name: str,
        # threshold: float = 0.5,
        top_k: int = 10,
        search_type: str = "text",
    ) -> List[SearchModel]:
        """在指定集合中按 BM25 关键词搜索

        Args:
            query: 查询文本
            collection_name: 集合名称
            threshold: 分数阈值
            top_k: 返回结果数量
            search_type: 搜索字段，可选 "text"(sparse_content) 或 "title"(sparse_title)
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(f"Cannot search in collection '{collection_name}' - collection not available")
            return []

        try:
            if search_type not in KEYWORD_MAPPING:
                logger.warning(f"Invalid search_type '{search_type}', fallback to 'text'")
                search_type = "text"
            anns_field = KEYWORD_MAPPING[search_type]

            results = collection.search(
                data=[query],
                anns_field=anns_field,
                param={"params": {"drop_ratio_search": 0.2}},
                limit=top_k,
                output_fields=output_fields,
            )

            documents = [
                _hit_to_search_model(hit, collection_name, score_attr="distance")
                for hit in results[0]
            ]
            # documents = [d for d in documents if d.score >= threshold]
            documents.sort(key=lambda x: x.score, reverse=True)
            return documents[:top_k]
            

        except Exception as e:
            logger.error(f"Search failed in collection '{collection_name}': {e}")
            return []

    def _get_chunk_with_context(
        self,
        chunk_id: str,
        file_id: str,
        collection_name: str,
        context_chars: int = 800,
    ) -> str:
        """
        获取chunk及其前后指定字符数的上下文
        
        Args:
            chunk_id: 当前chunk的ID
            file_id: 文件ID
            collection_name: 集合名称
            context_chars: 前后各获取的字符数，默认500
            
        Returns:
            包含上下文的完整内容
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(f"Collection '{collection_name}' not available")
            return ""

        try:
            # 查询同一file_id的所有chunk
            query_expr = f'file_id == "{file_id}"'
            results = collection.query(
                query_expr,
                output_fields=["chunk_id", "content", "page_idx", "title", "cur_title","par_title"],
            )

            if not results:
                logger.warning(f"No chunks found for file_id: {file_id}")
                return ""

            # 找到当前chunk
            current_chunk = None
            for chunk in results:
                if chunk.get("chunk_id") == chunk_id:
                    current_chunk = chunk
                    break

            if not current_chunk:
                logger.warning(f"Chunk {chunk_id} not found in file {file_id}")
                # 如果找不到chunk，返回空字符串，调用方会使用原始content
                return ""

            # 按page_idx和chunk_id排序
            def sort_key(chunk):
                page_idx = chunk.get("page_idx", [])
                # 取最小页码作为排序依据
                first_page = min(page_idx) if page_idx and len(page_idx) > 0 else 0
                
                # 提取chunk_id末尾的数字部分（count）用于排序
                chunk_id = chunk.get("chunk_id", "")
                count = 0
                if chunk_id:
                    # chunk_id格式: {file_name}_{uuid}-{count}
                    # 提取末尾的数字
                    parts = chunk_id.rsplit("-", 1)
                    if len(parts) == 2:
                        try:
                            count = int(parts[1])
                        except (ValueError, IndexError):
                            count = 0
                
                # 先按页码排序，页码相同则按count排序
                return (first_page, count)

            sorted_chunks = sorted(results, key=sort_key)

            # 拼接所有chunk的content
            full_text = ""
            chunk_positions = []  # 记录每个chunk在full_text中的位置
            for chunk in sorted_chunks:
                content = chunk.get("content", "") or ""
                cur_title = chunk.get("cur_title", "") or ""
                start_pos = len(full_text)
                if full_text:
                    full_text += "\n"
                    start_pos += 1
                full_text += cur_title + "\n" + content
                chunk_positions.append((chunk.get("chunk_id"), start_pos, len(full_text)))

            # 找到当前chunk在full_text中的位置
            current_start = None
            current_end = None
            for cid, start, end in chunk_positions:
                if cid == chunk_id:
                    current_start = start
                    current_end = end
                    break

            if current_start is None or current_end is None:
                logger.warning(f"Could not find position for chunk {chunk_id}")
                return current_chunk.get("content", "")

            # 提取前后context_chars个字符
            context_start = max(0, current_start - context_chars)
            context_end = min(len(full_text), current_end + context_chars)

            return full_text[context_start:context_end]

        except Exception as e:
            logger.error(f"Error getting chunk context: {e}")
            # 如果出错，返回原始content
            return current_chunk.get("content", "") if current_chunk else ""

    
    def doc_search_with_page_context(
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
        """
        在 doc_search 基础上，增加前一页、当前页、后一页的上下文 chunk。

        说明：
            - 先调用原有 doc_search 拿到命中的 chunk
            - 再基于 file_id + page_idx，从同一文件中取出前一页、当前页、后一页的所有 chunk 作为上下文
            - 最终结果去重，主命中 chunk 保留原始 score，上下文 chunk 复用其对应主 chunk 的 score
        """

        # 先做基础检索
        main_docs = self.doc_search(
            query=query,
            collection_names=collection_names,
            top_k=top_k,
            dense_type=dense_type,
            sparse_type=sparse_type,
            reranker_type=reranker_type,
            threshold=threshold,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
            rerank_model=rerank_model,
        )

        if not main_docs:
            return []

        # 结果去重：file_id + chunk_id
        unique: Dict[tuple, SearchModel] = {}
        for doc in main_docs:
            key = (doc.file_id, doc.chunk_id)
            if key not in unique:
                unique[key] = doc

        # 按 (collection_name, file_id) 缓存查询结果，避免重复 query
        file_chunks_cache: Dict[tuple, List[Dict[str, Any]]] = {}

        # 为每个主命中 chunk 扩展前后页的上下文
        for doc in main_docs:
            collection_name = getattr(doc, "collection_name", None)
            file_id = getattr(doc, "file_id", None)
            if not collection_name or not file_id:
                continue

            base_pages = _normalize_pages(getattr(doc, "page_idx", []))
            if not base_pages:
                continue

            # 计算前一页、当前页、后一页
            target_pages: Set[int] = set()
            for p in base_pages:
                target_pages.add(p - 1)
                target_pages.add(p)
                target_pages.add(p + 1)

            cache_key = (collection_name, file_id)

            # 从缓存或 Milvus 中取出该文件的所有 chunk
            if cache_key in file_chunks_cache:
                all_chunks = file_chunks_cache[cache_key]
            else:
                collection = self._get_collection_safe(collection_name)
                if not collection:
                    logger.error(
                        f"Cannot query context for collection '{collection_name}' - collection not available"
                    )
                    continue

                try:
                    # 先按 file_id 取出该文件的所有 chunk，再在内存中过滤页码
                    all_chunks = collection.query(
                        expr=f'file_id == "{file_id}"', output_fields=output_fields
                    )
                    file_chunks_cache[cache_key] = all_chunks
                except Exception as e:
                    logger.error(
                        f"Failed to query context chunks for file_id={file_id} in collection '{collection_name}': {e}"
                    )
                    continue

            # 过滤出前一页、当前页、后一页的 chunk
            for entity in all_chunks:
                pages = _normalize_pages(entity.get("page_idx"))
                if not pages:
                    continue

                # 判断是否与目标页有交集
                if not any(p in target_pages for p in pages):
                    continue

                chunk_id = entity.get("chunk_id")
                file_id_entity = entity.get("file_id")
                if not chunk_id or not file_id_entity:
                    continue

                key = (file_id_entity, chunk_id)
                if key in unique:
                    # 已经在主结果或已有上下文中
                    continue

                try:
                    context_doc = _entity_dict_to_search_model(
                        entity,
                        score=float(getattr(doc, "score", 0.0)),
                        collection_name=collection_name,
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to build SearchModel for context chunk_id={chunk_id} in collection '{collection_name}': {e}"
                    )
                    continue

                unique[key] = context_doc

        # 检查是否存在父级标题，如果存在则返回父级标题的全部内容
        # 对每个主 chunk，检查其 3 页范围内是否有父级标题
        # 如果找到了，立即返回该父级标题的全部内容（不再处理其他主 chunk）
        for doc in main_docs:
            collection_name = getattr(doc, "collection_name", None)
            file_id = getattr(doc, "file_id", None)
            if not collection_name or not file_id:
                continue
            
            base_pages = _normalize_pages(getattr(doc, "page_idx", []))
            if not base_pages:
                continue
            
            # 计算前一页、当前页、后一页
            target_pages: Set[int] = set()
            for p in base_pages:
                target_pages.add(p - 1)
                target_pages.add(p)
                target_pages.add(p + 1)
            
            cache_key = (collection_name, file_id)
            if cache_key not in file_chunks_cache:
                continue
            
            all_chunks = file_chunks_cache[cache_key]
            main_title = getattr(doc, "title", "").strip()
            main_chunk_id = getattr(doc, "chunk_id", "")
            
            # 从主 chunk 的 title 中提取可能的父级标题
            # title 使用 \n (换行符) 分隔层级，例如：
            # "第一章\n第一节\n第一小节" -> 父级标题可以是 "第一章" 或 "第一章\n第一节"
            parent_titles: List[str] = []
            if main_title:
                # 用换行符分割 title，提取父级标题
                title_lines = [line.strip() for line in main_title.split("\n") if line.strip()]
                if len(title_lines) > 1:
                    # 提取所有可能的父级标题（从最顶层到直接父级）
                    for i in range(len(title_lines) - 1):
                        parent_title = "\n".join(title_lines[:i+1])
                        if parent_title:
                            parent_titles.append(parent_title)
                # 如果只有一行，说明没有父级标题
            
            # 先找到主 chunk 在 all_chunks 中的位置（用于判断前后顺序和距离）
            main_chunk_idx = -1
            for idx, chunk in enumerate(all_chunks):
                if chunk.get("chunk_id") == main_chunk_id:
                    main_chunk_idx = idx
                    break
            
            # 在 3 页范围内查找父级标题的 chunk
            parent_title_candidates: List[Dict[str, Any]] = []
            
            for idx, chunk in enumerate(all_chunks):
                chunk_pages = _normalize_pages(chunk.get("page_idx"))
                if not chunk_pages:
                    continue
                
                # 必须在目标页范围内（前一页、当前页、后一页）
                if not any(p in target_pages for p in chunk_pages):
                    continue
                
                chunk_title = chunk.get("title", "").strip()
                if not chunk_title:
                    continue
                
                # 检查是否是父级标题（完全匹配或作为前缀）
                is_parent_title = False
                matched_parent_title = ""
                
                # 完全匹配父级标题
                if chunk_title in parent_titles:
                    is_parent_title = True
                    matched_parent_title = chunk_title
                # 或者父级标题是当前 chunk title 的前缀（考虑换行符分隔符）
                elif parent_titles:
                    for parent_title in parent_titles:
                        # 检查 parent_title 是否是 chunk_title 的前缀（考虑换行符）
                        if chunk_title == parent_title or chunk_title.startswith(parent_title + "\n"):
                            is_parent_title = True
                            matched_parent_title = parent_title
                            break
                
                if not is_parent_title:
                    continue
                
                # 计算与主 chunk 的距离（用于选择最近的）
                distance = float('inf')
                if main_chunk_idx >= 0:
                    distance = abs(idx - main_chunk_idx)
                else:
                    # 如果无法通过索引判断，则通过 page_idx 判断
                    chunk_min_page = min(chunk_pages) if chunk_pages else float('inf')
                    main_min_page = min(base_pages) if base_pages else float('inf')
                    distance = abs(chunk_min_page - main_min_page)
                
                parent_title_candidates.append({
                    "chunk": chunk,
                    "title": chunk_title,
                    "matched_parent_title": matched_parent_title,
                    "distance": distance,
                    "idx": idx,
                    "page_idx": chunk_pages,
                })
            
            # 如果找到父级标题候选，选择离主 chunk 最近的
            if parent_title_candidates:
                # 按距离升序排序，选择最近的
                parent_title_candidates.sort(key=lambda x: x["distance"])
                selected_parent = parent_title_candidates[0]
                parent_title = selected_parent["matched_parent_title"]
                
                # 在三页范围内，找出所有使用该父级标题的 chunk
                parent_section_chunks: List[SearchModel] = []
                seen_chunk_ids: Set[str] = set()
                
                for chunk in all_chunks:
                    chunk_pages = _normalize_pages(chunk.get("page_idx"))
                    if not chunk_pages:
                        continue
                    
                    # 只取三页范围内的 chunk
                    if not any(p in target_pages for p in chunk_pages):
                        continue
                    
                    chunk_title = chunk.get("title", "").strip()
                    # 检查是否使用该父级标题（完全匹配或作为前缀，考虑换行符分隔符）
                    if chunk_title != parent_title and not chunk_title.startswith(parent_title + "\n"):
                        continue
                    
                    chunk_id = chunk.get("chunk_id")
                    if not chunk_id or chunk_id in seen_chunk_ids:
                        continue
                    
                    try:
                        parent_doc = _entity_dict_to_search_model(
                            chunk,
                            score=float(getattr(doc, "score", 0.0)),
                            collection_name=collection_name,
                        )
                        parent_section_chunks.append(parent_doc)
                        seen_chunk_ids.add(chunk_id)
                    except Exception as e:
                        logger.error(
                            f"Failed to build SearchModel for parent section chunk_id={chunk_id} in collection '{collection_name}': {e}"
                        )
                        continue
                
                # 如果找到了父级标题的内容，立即返回（丢弃其他内容）
                if parent_section_chunks:
                    # 按 page_idx 和 chunk_id 排序，保证顺序
                    parent_section_chunks.sort(
                        key=lambda x: (
                            min(_normalize_pages(getattr(x, "page_idx", [])) or [0]),
                            getattr(x, "chunk_id", ""),
                        )
                    )
                    # 去重：按 (file_id, chunk_id) 去重
                    unique_parent: Dict[tuple, SearchModel] = {}
                    for parent_doc in parent_section_chunks:
                        key = (parent_doc.file_id, parent_doc.chunk_id)
                        if key not in unique_parent:
                            unique_parent[key] = parent_doc
                    # 找到父级标题后，立即返回，不再处理其他主 chunk
                    return list(unique_parent.values())
        
        # 如果没有找到父级标题，则返回原来的结果（主 chunk + 3 页上下文）
        # 主命中结果保持原有顺序，上下文 chunk 按加入顺序附加在后面
        context_docs: List[SearchModel] = []
        for key, doc in unique.items():
            # 跳过已经在 main_docs 里的（保持 main_docs 原有顺序）
            # 这里通过 (file_id, chunk_id) 是否出现在 main_docs 来判断
            if any(
                (d.file_id, d.chunk_id) == key for d in main_docs
            ):
                continue
            context_docs.append(doc)

        return list(main_docs) + context_docs
    
    async def delete_chunks_by_kbid(self, collection_name: str, delete_collection_name: str) -> bool:
        """
        优先按 chunk_id + file_id 删除；
        若未提供 chunk_id，则仅按 file_id 删除
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot delete from collection '{collection_name}' - collection not available"
            )
            return False

        try:

            query_expr = f'kb_id == "{delete_collection_name}"'

            results = collection.query(query_expr, output_fields=["id"])
            delete_ids = [r["id"] for r in results]

            if not delete_ids:
                logger.info(
                    f"No documents found for kb_id == {delete_collection_name}"
                )
                return True

            delete_expr = f"id in {delete_ids}"
            collection.delete(delete_expr)
            collection.flush()

            logger.info(
                f"Successfully deleted {len(delete_ids)} documents "
            )
            return True

        except Exception as e:
            logger.error(
                f"Error deleting documents "
                f"from collection {collection_name}: {e}"
            )
            return False
        

    async def delete_doc_by_id(self, collection_name: str, file_id: str, chunk_id: str | None = None) -> bool:
        """
        优先按 chunk_id + file_id 删除；
        若未提供 chunk_id，则仅按 file_id 删除
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot delete from collection '{collection_name}' - collection not available"
            )
            raise ValueError(f"当前知识库不存在: {collection_name}")
            # return False


        try:
            # 构造查询条件
            if chunk_id:
                query_expr = f'file_id == "{file_id}" AND chunk_id == "{chunk_id}"'
            else:
                query_expr = f'file_id == "{file_id}"'

            results = collection.query(query_expr, output_fields=["id"])
            delete_ids = [r["id"] for r in results]

            if not delete_ids:
                logger.info(
                    f"No documents found for file_id={file_id}, chunk_id={chunk_id}"
                )
                raise ValueError(
                    f"未找到数据: file_id={file_id}, chunk_id={chunk_id}"
                )
                

            delete_expr = f"id in {delete_ids}"
            collection.delete(delete_expr)
            collection.flush()

            logger.info(
                f"Successfully deleted {len(delete_ids)} documents "
                f"(file_id={file_id}, chunk_id={chunk_id})"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error deleting documents "
                f"(file_id={file_id}, chunk_id={chunk_id}) "
                f"from collection {collection_name}: {e}"
            )
            # return False
            raise RuntimeError(f"删除失败: {str(e)}")

    def create_collection_chatper_summary(self, collection_name: str):
        """创建 Milvus 集合（如果不存在）"""
        if self._collection_exists(collection_name):
            logger.info(f"Collection '{collection_name}' already exists")
            return

        try:
            fields = [
                FieldSchema(
                    name="id", dtype=DataType.INT64, is_primary=True, auto_id=True
                ),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
                FieldSchema(name="kb_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="file_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(
                    name="embedding_content", dtype=DataType.FLOAT_VECTOR, dim=1024
                ),
            ]

            schema = CollectionSchema(
                fields, description=f"RAG Collection: {collection_name}"
            )

            collection = Collection(collection_name, schema)

            collection.create_index("embedding_content", VECTOR_INDEX_PARAMS)
            collection.load()

            self.collections[collection_name] = collection
            self.loaded_collections.add(collection_name)
            self.lru_cache.touch(collection_name)
            logger.info(
                f"Successfully created and loaded collection: {collection_name}"
            )

        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            raise
        
    # async def summary_insert(self, chunks: list, collection_name: str="chapter_summary") -> bool:
    #     """插入数据到指定集合"""
    #     if collection_name not in self.collections:
    #         self.create_collection_chatper_summary(collection_name)

    #     collection = self._get_collection_safe(collection_name)
    #     if not collection:
    #         logger.error(
    #             f"Cannot insert into collection '{collection_name}' - collection not available"
    #         )
    #         return False

    #     for start in range(0, len(chunks), batch_size):
    #         batch = chunks[start : start + batch_size]
    #         try:
    #             # 准备数据
                
    #             kb_id_list, content_list, file_id_list = [], [], []
    #             embedding_content_list = []
                
    #             for chunk in batch:
    #                 content_list.append(chunk.content)
    #                 file_id_list.append(chunk.file_id)
    #                 kb_id_list.append(collection_name)

    #             # 生成嵌入向量
    #             embedding_content_list = get_img_embedding(content_list)

    #             data = [
    #                 content_list,
    #                 kb_id_list,
    #                 file_id_list,
    #                 embedding_content_list,
    #             ]

    #             # 插入数据
    #             collection.insert(data)
    #         except Exception as e:
    #             logger.error(
    #                 f"Failed to insert batch into collection '{collection_name}': {e}"
    #             )
    #             # logger.error(f"Failed to insert batch into collection '{data}'")
    #             return False
    #     collection.flush()
    #     logger.info(
    #         f"Successfully inserted {len(chunks)} chunks into collection '{collection_name}'"
    #     )
    #     return True

    async def summary_insert(self, content: str, file_id:str, doc_collection_name: str, collection_name: str = "chapter_summary") -> bool:
        """插入单个章节摘要到指定集合"""
        if collection_name not in self.collections:
            self.create_collection_chatper_summary(collection_name)

        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot insert into collection '{collection_name}' - collection not available"
            )
            return False

        try:
            # 准备数据（单个 chunk 也按字段列表形式插入）
            content_list = [content]
            file_id_list = [file_id]
            kb_id_list = [doc_collection_name]

            # 生成嵌入向量
            embedding_content_list = await async_get_embedding(content_list)
            
            data = [
                content_list,
                kb_id_list,
                file_id_list,
                embedding_content_list,
            ]

            # 插入数据
            collection.insert(data)
        except Exception as e:
            logger.error(
                f"Failed to insert summary into collection '{collection_name}': {e}"
            )
            return False

        collection.flush()
        logger.info(
            f"Successfully inserted 1 chunk into collection '{collection_name}'"
        )
        return True
    
    
    def create_collection_image(self, collection_name: str):
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
                FieldSchema(name="img_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="kb_id", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="img_path", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(
                    name="embedding_img", dtype=DataType.FLOAT_VECTOR, dim=1024
                ),
                FieldSchema(name="others", dtype=DataType.JSON),
                
            ]

            schema = CollectionSchema(
                fields, description=f"RAG Collection: {collection_name}"
            )

            collection = Collection(collection_name, schema)

            collection.create_index("embedding_img", VECTOR_INDEX_PARAMS)
            collection.load()

            self.collections[collection_name] = collection
            self.loaded_collections.add(collection_name)
            self.lru_cache.touch(collection_name)
            logger.info(
                f"Successfully created and loaded collection: {collection_name}"
            )

        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            raise

    async def img_insert(self, chunks: list, collection_name: str="images") -> bool:
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
            self.create_collection_image(collection_name)

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
                chunk_id_list, kb_id_list, media_path_list = [], [], []
                img_id_list = []
                real_img_paths = []
                others_list = []

                for chunk in batch:
                    chunk_id_list.append(chunk.chunk_id)
                    img_id_list.append(chunk.img_id)
                    kb_id_list.append(chunk.kb_id)
                    media_path_list.append(chunk.media_path)
                    real_img_paths.append(chunk.source_media_path)
                    # others_list.append(chunk.others)
                    others_list.append(chunk.others if chunk.others else {})
                    

                # 生成嵌入向量
                embedding_img_list = get_img_embedding(real_img_paths)

                data = [
                    chunk_id_list,
                    img_id_list,
                    kb_id_list,
                    media_path_list,
                    embedding_img_list,
                    others_list                    
                ]

                # 插入数据
                collection.insert(data)
            except Exception as e:
                logger.error(
                    f"Failed to insert batch into collection '{collection_name}': {e}"
                )
                # logger.error(f"Failed to insert batch into collection '{data}'")
                # return False
                raise
        collection.flush()
        logger.info(
            f"Successfully inserted {len(chunks)} chunks into collection '{collection_name}'"
        )
        return True

    def img_search(
        self,
        query_img: str,
        collection_name: str = "images2",
        threshold: float = 0.5,
        kb_ids: list = None,
        top_k: int = 10,
    ) -> List:
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
            return f"Cannot search in collection '{collection_name}' - collection not available"

        if query_img.startswith("http"):
            try:
                query_img = download_image(query_img, save_dir= IMG_DOWNLOAD_DIR)
            except Exception as e:
                logger.error(f"Failed to download image from URL '{query_img}': {e}")
                return e
            
        try:
            # 生成查询向量
            query_img_embedding = get_img_embedding(query_img)

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
            # print(results)
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
            return e

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
                FieldSchema(name="update_time", dtype=DataType.VARCHAR, max_length=256),
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
            collection.create_index("sparse_messages", BM25_INDEX_PARAMS)
            collection.create_index("embedding_messages", VECTOR_INDEX_PARAMS)
            collection.load()

            self.collections[collection_name] = collection
            self.loaded_collections.add(collection_name)
            self.lru_cache.touch(collection_name)
            logger.info(
                f"Successfully created and loaded collection: {collection_name}"
            )

        except Exception as e:
            logger.error(f"Failed to create collection '{collection_name}': {e}")
            raise

    async def memory_insert(
        self,
        messages: [],
        user_id: str,
        thread_id: str,
        update_time: str,
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
            messages = "\n".join([f"{m.role}: {m.content}" for m in messages])
            message_embed = await async_get_embedding(messages)

            data = [
                {
                    "messages": messages,
                    "user_id": user_id,
                    "thread_id": thread_id,
                    "embedding_messages": message_embed,
                    "update_time": update_time
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

    async def delete_memory_by_id(self, user_id: str, thread_id: str, collection_name:str="long_memory") -> bool:
        """根据文件ID删除数据"""
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot delete from collection '{collection_name}' - collection not available"
            )
            return False

        try:
            # 构造查询表达式
            query_expr=(f"user_id == '{user_id}' " f"AND thread_id == '{thread_id}'")

            # 查询符合条件的文档
            results = collection.query(query_expr, output_fields=["id"])
            delete_ids = [result["id"] for result in results]

            # 如果找到匹配的文档，执行删除操作
            if delete_ids:
                delete_expr = f"id in {delete_ids}"
                collection.delete(delete_expr)
                collection.flush()  # 确保删除操作立即生效
                logger.info(
                    f"Successfully deleted {len(delete_ids)} documents for user_id: {user_id}"
                )
                return True
            else:
                logger.info(f"No documents found for user_id: {user_id}")
                return True

        except Exception as e:
            logger.error(
                f"Error deleting user_id {user_id} from collection {collection_name}: {e}"
            )
            return False

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
            collection.create_index("sparse_pin_number", BM25_INDEX_PARAMS)
            collection.load()

            self.collections[collection_name] = collection
            self.loaded_collections.add(collection_name)
            self.lru_cache.touch(collection_name)
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
                return False
        collection.flush()
        logger.info(f"Successfully inserted {len(chunks)} chunks into collection '{collection_name}'")
        return True
    
    def sop_search(self, query: str, collection_name: str="sop8_pid", top_k: int = 10) -> List:
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
        """根据 chunk_id 在指定集合中查询单条记录

        Args:
            chunk_id: 块 ID
            collection_name: 集合名称

        Returns:
            匹配的 chunk 列表（通常为单条）
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
                expr=(f"chunk_id == '{chunk_id}' "), output_fields=output_fields
            )

            return results[0]

        except Exception as e:
            logger.error(f"Search failed in collection '{collection_name}': {e}")
            return []

    def list_chunks_by_title_fileid(self, collection_name: str, title: str, file_id: str) -> List:
        """根据 cur_title 和 file_id 查询匹配的 chunk 列表

        Args:
            collection_name: 集合名称
            title: 当前标题
            file_id: 文件 ID

        Returns:
            匹配的 chunk 列表
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
                expr=(f"cur_title == '{title}' " f"AND file_id == '{file_id}'"),
                output_fields=output_fields,
            )

            return results

        except Exception as e:
            logger.error(
                f"Failed to list knowledge_ids from collection '{collection_name}': {e}"
            )
            return []
        
    def list_curtitle_by_fileid(self, collection_name: str, file_ids: list = []) -> List:
        """根据 collection_name 和 file_id 查询匹配的 chunk 列表

        Args:
            collection_name: 集合名称
            title: 当前标题
            file_ids: 文件 ID List

        Returns:
            匹配的 chunk 列表
        """
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot query from collection '{collection_name}' - collection not available"
            )
            return []

        try:
            # 查询所有记录，只返回chunk_id, cur_title, file_id字段
            results = collection.query(
                expr=f"file_id in {file_ids}",
                output_fields=["cur_title", "file_id"],
            )
            # files = []
            # seen = []
            # for item in results:
            #     cur_title = str(item.get("cur_title") or "").strip()
            #     file_id = str(item.get("file_id") or "").strip()

            #     # 根据cur_title和file_id去重，确保同一文件的同一标题只保留一条记录
            #     dedupe_key = (cur_title, file_id)
            #     if dedupe_key in seen:
            #         continue
            #     seen.append(dedupe_key)
                               
            #     files.append(
            #         {
            #             "cur_title": cur_title,
            #             "file_id": file_id
            #         }
            #     )
            
            return results

        except Exception as e:
            logger.error(
                f"Failed to list file_id from collection '{collection_name}': {e}"
            )
            return []

    def list_collection_files(self, collection_name: str) -> List[Dict[str, str]]:
        """列出指定 collection 中的去重文件列表。"""
        collection = self._get_collection_safe(collection_name)
        if not collection:
            logger.error(
                f"Cannot query files from collection '{collection_name}' - collection not available"
            )
            return []

        try:
            results = collection.query(
                expr='file_id != ""',
                output_fields=["file_id", "file_path", "update_time"],
            )

            files: List[Dict[str, str]] = []
            seen: Set[tuple[str, str]] = set()
            for item in results:
                file_id = str(item.get("file_id") or "").strip()
                file_path = str(item.get("file_path") or "").strip()
                update_time = str(item.get("update_time") or "").strip()

                if not file_id and not file_path:
                    continue

                dedupe_key = (file_id, file_path)
                if dedupe_key in seen:
                    continue

                seen.add(dedupe_key)
                files.append(
                    {
                        "file_id": file_id,
                        "file_name": os.path.basename(file_path) if file_path else file_id,
                        "file_path": file_path,
                        "update_time": update_time,
                    }
                )

            files.sort(
                key=lambda item: (
                    item["file_name"],
                    item["file_id"],
                    item["file_path"],
                )
            )
            return files

        except Exception as e:
            logger.error(
                f"Failed to list files from collection '{collection_name}': {e}"
            )
            return []

    def delete_collection(self, collection_name: str) -> bool:
        """删除整个集合（包括所有数据）

        Args:
            collection_name: 要删除的集合名称

        Returns:
            bool: 删除是否成功
        """
        # 检查集合是否存在
        if not self._collection_exists(collection_name):
            logger.warning(f"Collection '{collection_name}' does not exist")
            raise ValueError(f"当前知识库不存在: {collection_name}")

        try:
            # 如果集合在缓存中，先释放它
            if collection_name in  self.collections:
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
            self.lru_cache.remove(collection_name)

            logger.info(f"Collection '{collection_name}' deleted successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to delete collection '{collection_name}': {e}")
            # return False
            raise RuntimeError(f"删除失败: {str(e)}")
        

    def unload_collection(self, collection_name: str) -> bool:
        """卸载集合以释放内存"""
        try:
            if collection_name in self.collections:
                collection = self.collections[collection_name]
                collection.release()
                self.loaded_collections.discard(collection_name)
                self.lru_cache.remove(collection_name)
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

            # 清空 LRU 缓存
            self.lru_cache.clear()

            connections.disconnect("default")
            logger.info("Milvus connection closed and all collections unloaded")
        except Exception as e:
            logger.error(f"Error closing Milvus connection: {e}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    milvus_client = MilvusClient()
    # milvus_client.memory_insert(messages="叫爸爸", user_id="123", thread_id="789")
    # milvus_client.memory_search(query="爸爸",user_id="123")
    
    # milvus_client.img_insert()
    milvus_client.img_search("/mnt/ddata2/cc007/omniknow2/parser/rag/3DD77259-CF60-437E-A388-97B3F4051483.jpg",threshold=0,top_k=3)
    
    
    # milvus_client.sop_search("X179")
    
    
