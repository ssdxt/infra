import os
from dotenv import load_dotenv
import logging
from typing import Any, Dict, List, Optional
import requests
from uuid import uuid4

import torch
from PIL import Image
from pymilvus import Collection, connections, utility
from pymilvus.client.types import LoadState
from transformers import AutoImageProcessor, AutoModel

output_fields = [
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
logger = logging.getLogger(__name__)
load_dotenv()

def download_image(url: str, save_dir: str = "/mnt/ddata2/_temp/"):
    os.makedirs(save_dir, exist_ok=True)

    # 从 URL 中提取文件名
    filename = str(uuid4().hex) + ".jpg"
    if not filename:
        raise ValueError("URL 中无法解析出文件名")

    save_path = os.path.join(save_dir, filename)

    response = requests.get(url, timeout=10)
    response.raise_for_status()

    with open(save_path, "wb") as f:
        f.write(response.content)

    return save_path


class MilvusImageClient:
    def __init__(self):
        self.milvus_host = os.getenv("MILVUS_HOST")
        self.milvus_port = os.getenv("MILVUS_PORT")
        self.collections: Dict[str, Collection] = {}
        self.loaded_collections: set = set()  # 跟踪已加载的集合
        self.model = None
        self.processor = None

        # 连接管理
        self._connect()
        self.init_img_embedding()

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

    def init_img_embedding(self):
        model_path = "/mnt/ddata2/models/dinov3-vitl16-pretrain-lvd1689m"
        device = torch.device('cuda:0' if torch.cuda.is_available() else "cpu")
        self.processor = AutoImageProcessor.from_pretrained(model_path)
        self.model = AutoModel.from_pretrained(model_path)
        self.model.to(device)
        self.model.eval()


    def get_img_embedding(self, query_img: str):
        device = torch.device('cuda:0' if torch.cuda.is_available() else "cpu")
        images = Image.open(query_img).convert("RGB")
        with torch.no_grad():
            inputs = self.processor(images=images, return_tensors="pt").to(device)
            outputs = self.model(**inputs)
            pooled_output = outputs.pooler_output
            embedding = torch.nn.functional.normalize(pooled_output, p=2, dim=-1)
        return embedding[0].cpu().numpy().tolist()
    

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

    def img_search(
        self,
        query_img: str,
        collection_name: str = "images",
        threshold: float = 0.5,
        kb_ids: list = None,
        top_k: int = 5,
    ) -> List[Any]:
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
            query_img_embedding = self.get_img_embedding(save_img)

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
                documents.append(self.list_chunk_by_id(chunk_id, collection_name))

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
                expr=(f"chunk_id == '{chunk_id}' "), output_fields=output_fields
            )

            return results[0]

        except Exception as e:
            logger.error(f"Search failed in collection '{collection_name}': {e}")
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

