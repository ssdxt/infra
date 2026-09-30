import os
from typing import Any, Dict, Iterable, List, Optional
import logging
from dotenv import load_dotenv
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    Function,
    FunctionType,
    connections,
    utility,
)
from pymilvus.client.types import LoadState

logger = logging.getLogger(__name__)
load_dotenv()

batch_size = int(os.getenv("COLLECTION_INSERT_BATCH_SIZE", 256))


KEYWORD_MAPPING = {
    "text": "sparse_pin_number",
}

output_fields = [
    "pin_number",
    "pin_number_id",
    "page_name",
    "page_number",
    "connectorID",
    "cavityID",
    "SOP",
    "url",
    "details"
]


class MilvusClient_sop:
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

    def create_collection(self, collection_name: str, analyzer: str = "english"):
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
                FieldSchema(
                    name="pin_number",
                    dtype=DataType.VARCHAR,
                    max_length=256,
                    enable_analyzer=True,
                    analyzer_params=analyzer_params,
                    enable_match=True,
                ),
                FieldSchema(name="pin_number_id", dtype=DataType.INT64),
                FieldSchema(name="page_name", dtype=DataType.VARCHAR, max_length=256),
                FieldSchema(name="page_number", dtype=DataType.INT64),
                FieldSchema(name="connectorID", dtype=DataType.VARCHAR, max_length=128),
                FieldSchema(name="cavityID", dtype=DataType.VARCHAR, max_length=32),
                FieldSchema(name="SOP", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(
                    name="sparse_pin_number", dtype=DataType.SPARSE_FLOAT_VECTOR
                ),
            ]

            pin_number_bm25_function = Function(
                name="content_bm25_emb",  # Function name
                input_field_names=[
                    "pin_number"
                ],  # Name of the VARCHAR field containing raw text data
                output_field_names=[
                    "sparse_pin_number"
                ],  # Name of the SPARSE_FLOAT_VECTOR field reserved to store generated embeddings
                function_type=FunctionType.BM25,  # Set to `BM25`
            )

            schema = CollectionSchema(
                fields, description=f"RAG Collection: {collection_name}"
            )
            schema.add_function(pin_number_bm25_function)
            collection = Collection(collection_name, schema)

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

            collection.create_index("sparse_pin_number", bm_index_params)

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

    async def kerword_search_async(
        self, query: str, collection_name: str, top_k: int = 10, type: str = "text"
    ) -> List:
        """在指定集合中搜索语义相似数据

        Args:
            query: 查询文本
            collection_name: 集合名称
            top_k: 返回结果数量
            type: 搜索类型，可选值: "text" (对应pin_number)
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
                # search_params=search_params,
                output_fields=output_fields,
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

    def kerword_search(
        self, query: str, collection_name: str, top_k: int = 5, type: str = "text"
    ) -> List:
        """在指定集合中搜索语义相似数据

        Args:
            query: 查询文本
            collection_name: 集合名称
            top_k: 返回结果数量
            type: 搜索类型，可选值: "text" (对应pin_number)
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
                # search_params=search_params,
                output_fields=output_fields,
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

    async def insert(self, collection_name: str, chunks) -> bool:
        """插入数据到指定集合"""
        if collection_name not in self.collections:
            await self.create_collection(collection_name)

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
                (
                    pin_number_list,
                    pin_number_id_list,
                    page_name_list,
                    page_number_list,
                ) = ([], [], [], [])
                connectorID_list, cavityID_list, SOP_list = [], [], []

                for chunk in batch:
                    pin_number_list.append(chunk["pin_number"])
                    pin_number_id_list.append(chunk["pin_number_id"])
                    page_name_list.append(chunk["page_name"])
                    page_number_list.append(chunk["page_number"])
                    connectorID_list.append(chunk["connectorID"])
                    cavityID_list.append(chunk["cavityID"] if chunk["cavityID"] else "")
                    SOP_list.append(chunk["SOP"])

                data = [
                    pin_number_list,
                    pin_number_id_list,
                    page_name_list,
                    page_number_list,
                    connectorID_list,
                    cavityID_list,
                    SOP_list,
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

