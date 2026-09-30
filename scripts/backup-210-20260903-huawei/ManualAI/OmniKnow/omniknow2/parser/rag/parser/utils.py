import os
from pathlib import Path
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from loguru import logger
from typing import Optional, Literal
from typing import Union, List
from io import BytesIO
from urllib.parse import urlparse
from uuid import uuid4
from urllib.parse import unquote
import requests
import os

# 导入各个解析器
from .pdf_parser import PDFParser
from .docx_parser import DocxParser
from .json_parser import JsonParser
from .excel_loader import ExcelLoader
from .markdown_parser import MarkdownParser
from .txt_parser import TxtParser
from .mineru_parser import MineruParser
from dotenv import load_dotenv
from openai import AsyncOpenAI,OpenAI
import asyncio
import os
import numpy as np
import httpx
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

# 导入各个解析器

from dotenv import load_dotenv
import logging

for name in ("httpx", "httpcore", "openai", "openai._base_client"):
    logging.getLogger(name).setLevel(logging.WARNING)

load_dotenv()

embedding_dimensions = int(os.getenv("EMBEDDING_DIMENSIONS", "0"))
embedding_max_len = int(os.getenv("EMBEDDING_MAX_LEN","8192"))
embedding_batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "1"))
embedding_model = os.getenv("EMBEDDING_MODEL")
embedding_client = OpenAI(
                        base_url=os.getenv("EMBEDDING_BASE_URL"),
                        api_key=os.getenv("EMBEDDING_KEY")
                    )
embedding_client_async = AsyncOpenAI(
                        base_url=os.getenv("EMBEDDING_BASE_URL"),
                        api_key=os.getenv("EMBEDDING_KEY")
                    )
rerank_base_url = os.getenv("RERANK_BASE_URL")
rerank_max_len = int(os.getenv("RERANK_MAX_LEN"))
rerank_key = os.getenv("RERANK_KEY")
rerank_model = os.getenv("RERANK_MODEL")

img_search = os.getenv("IMG_SEARCH", False)
img_search = img_search.strip().lower() in ("true", "1", "yes")
img_search_batch = int(os.getenv("IMG_SEARCH_BATCH", "1"))

IMG_SERVICE_HOST = os.getenv("IMG_SERVICE_HOST", "0.0.0.0")
IMG_SERVICE_PORT = int(os.getenv("IMG_SERVICE_PORT", "18080"))
#img_service_base_url = f"http://{IMG_SERVICE_HOST}:{IMG_SERVICE_PORT}"
img_service_base_url = f"http://img_service:{IMG_SERVICE_PORT}"
img_service_timeout = int(os.getenv("IMG_SERVICE_TIMEOUT", "120"))

_parser_instances: Dict[tuple, Any] = {}


def is_img_search_enabled() -> bool:
    """返回图片向量化能力是否启用。"""
    return img_search


def get_file_extension(file_path: str) -> str:
    """获取文件扩展名（小写）"""
    return Path(file_path).suffix.lower()


def get_parser(file_path: str, method: Optional[str] = "smart") -> Any:
    """
    根据文件扩展名返回对应的解析器实例（使用单例模式，避免重复初始化）
    """
    ext = get_file_extension(file_path)
    
    # 构建缓存键
    cache_key = (ext, method)
    
    # 如果已经缓存了该类型的解析器，直接返回
    if cache_key in _parser_instances:
        return _parser_instances[cache_key]
    
    # 如果 method 为 "smart"，使用 MinerUParser（目前主要支持 PDF）
    if method == "smart":
        parser_class = MineruParser
        parser_instance = parser_class()
        _parser_instances[cache_key] = parser_instance
        logger.debug(f"初始化解析器: {ext} (method={method}) -> {parser_class.__name__}")
        return parser_instance
   
    # 解析器类映射
    parser_map = {
        '.pdf': PDFParser,
        '.docx': DocxParser,
        '.json': JsonParser,
        '.jsonl': JsonParser,
        '.xlsx': ExcelLoader,
        '.xls': ExcelLoader,
        '.csv': ExcelLoader,
        '.md': MarkdownParser,
        '.markdown': MarkdownParser,
        '.txt': TxtParser,
    }
    
    parser_class = parser_map.get(ext)
    if parser_class is None:
        supported_formats = ', '.join(parser_map.keys())
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}。支持的格式: {supported_formats}"
        )
    
    # 创建解析器实例并缓存
    parser_instance = parser_class()
    _parser_instances[cache_key] = parser_instance
    
    logger.debug(f"初始化解析器: {ext} -> {parser_class.__name__}")
    
    return parser_instance


def truncate_text(text: str, max_len: int=8192) -> str:
    """Returns truncated text if the length of text exceed max_len."""
    # return self.encoding.decode(self.encoding.encode(text)[:max_len])
    return text[:max_len]


def build_embedding_kwargs(input_data):
    kwargs = {
        "model": embedding_model,
        "input": input_data,
    }
    if embedding_model=="qwen-embedding":
        kwargs["dimensions"] = embedding_dimensions
        kwargs["encoding_format"] = "float"
    return kwargs


def get_vllm_embedding(query: Union[str, List[str]]):
    zero_vector = [0.0] * embedding_dimensions

    # 单条文本
    if isinstance(query, str):
        if not query:  # 空文本处理
            return zero_vector

        text = truncate_text(query, embedding_max_len)
        kwargs = build_embedding_kwargs(text)
        responses = embedding_client.embeddings.create(**kwargs)
        return responses.data[0].embedding

    # 批处理
    results = []

    batches = [
        query[i:i + embedding_batch_size]
        for i in range(0, len(query), embedding_batch_size)
    ]

    for batch in batches:
        batch = [truncate_text(t, embedding_max_len) for t in batch]
        kwargs = build_embedding_kwargs(batch)
        responses = embedding_client.embeddings.create(**kwargs)
        results.extend([resp.embedding for resp in responses.data])

    return results


async def async_get_vllm_embedding(query: Union[str, List[str]]):
    zero_vector = [0.0] * embedding_dimensions
    
    # 如果是字符串，则为query，直接处理
    if isinstance(query, str):
        if not query:  # 空文本处理
            return zero_vector
        text = truncate_text(query, embedding_max_len)
        kwargs = build_embedding_kwargs(text) 
        responses = await embedding_client_async.embeddings.create(**kwargs)  
        # print(responses.data[0].embedding)
        return responses.data[0].embedding
    
    query = [q if q else 'none' for q in query]

    # 批处理
    semaphore = asyncio.Semaphore(1)  # 限制并发数

    async def process_batch(batch):
        batch = [truncate_text(t, embedding_max_len) for t in batch]
        kwargs = build_embedding_kwargs(batch)
        async with semaphore:
            responses = await embedding_client_async.embeddings.create(**kwargs)
            return [response.embedding for response in responses.data]

    # 将查询分成每组10条
    batches = [query[i:i + embedding_batch_size] for i in range(0, len(query), embedding_batch_size)]

    # 并发处理所有批次
    tasks = [process_batch(batch) for batch in batches]
    results = await asyncio.gather(*tasks)

    res = [embedding for batch_result in results for embedding in batch_result]
    # print(res)
    # print(len(res))
    # print(len(tasks))
    # print(len(res[0]))
    return res
    

def _build_rerank_payload(query: str, texts: list) -> tuple[str, list[str], int]:
    """构建 rerank 请求的 query、documents 和 max_len，消除 qwen-rerank 模板重复"""
    if rerank_model == "qwen-rerank":
        prefix = '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
        suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
        instruction = "Given a web search query, retrieve relevant passages that answer the query"
        query_str = f"{prefix}<Instruct>: {instruction}\n<Query>: {query}\n"
        formatted_texts = [f"<Document>: {doc}{suffix}" for doc in texts]
        return query_str, formatted_texts, 32768
    return query, texts, 8192


def get_vllm_rerank(query: str, texts: list):
    if len(texts) == 0:
        return np.array([]), 0

    query_str, formatted_texts, max_len = _build_rerank_payload(query, texts)
    truncated_texts = [truncate_text(t, max_len) for t in formatted_texts]
    headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
        "Authorization": f"Bearer {rerank_key}",
    }
    data = {"model": rerank_model, "query": query_str, "documents": truncated_texts}

    resp = requests.post(rerank_base_url, headers=headers, json=data, timeout=3600)
    resp.raise_for_status()
    res = resp.json()
    return [{"index": item["index"], "score": item["relevance_score"]} for item in res["results"]]


async def async_get_vllm_rerank(query: str, texts: list):
    if len(texts) == 0:
        return np.array([]), 0

    query_str, formatted_texts, max_len = _build_rerank_payload(query, texts)
    truncated_texts = [truncate_text(t, max_len) for t in formatted_texts]
    headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
        "Authorization": f"Bearer {rerank_key}",
    }
    data = {"model": rerank_model, "query": query_str, "documents": truncated_texts}

    async with httpx.AsyncClient(timeout=3600) as client:
        resp = await client.post(rerank_base_url, headers=headers, json=data)
        resp.raise_for_status()
        res = resp.json()
    return [{"index": item["index"], "score": item["relevance_score"]} for item in res["results"]]


def _normalize_img_paths(query_img: Union[str, List[str]]) -> List[str]:
    if isinstance(query_img, str):
        return [query_img]
    return list(query_img)


async def async_get_img_embedding(query_img: Union[str, List[str]]):    
    if not img_search:
        raise RuntimeError("IMG_SEARCH=False，图片向量化功能未启用。")

    is_single = isinstance(query_img, str)
    normalized_paths = _normalize_img_paths(query_img)
    all_embeddings: List[List[float]] = []
    batches = [
        normalized_paths[i:i + img_search_batch]
        for i in range(0, len(normalized_paths), img_search_batch)
    ]

    async with httpx.AsyncClient(timeout=img_service_timeout) as client:
        for batch in batches:
            payload = {"paths": batch}
            resp = await client.post(
                f"{img_service_base_url}/v1/embeddings/image",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            all_embeddings.extend(data["embeddings"])

    return all_embeddings[0] if is_single else all_embeddings
    # print(len(res))


def get_img_embedding(query_img: Union[str, List[str]]):
    if not img_search:
        raise RuntimeError("IMG_SEARCH=False，图片向量化功能未启用。")

    is_single = isinstance(query_img, str)
    normalized_paths = _normalize_img_paths(query_img)
    all_embeddings: List[List[float]] = []
    batches = [
        normalized_paths[i:i + img_search_batch]
        for i in range(0, len(normalized_paths), img_search_batch)
    ]
    
    with httpx.Client(timeout=img_service_timeout) as client:
        for batch in batches:
            payload = {"paths": batch}
            resp = client.post(
                f"{img_service_base_url}/v1/embeddings/image",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            all_embeddings.extend(data["embeddings"])

    return all_embeddings[0] if is_single else all_embeddings



def _detect_image_ext_by_magic(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "gif"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return "webp"
    return None


def download_image(url: str, save_dir: str = ".", file_name: str | None = None) -> str:
    url = url.strip()  # 关键：去掉复制时的空格/换行
    os.makedirs(save_dir, exist_ok=True)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": f"{urlparse(url).scheme}://{urlparse(url).netloc}/",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"请求失败: {e}") from e

    content = resp.content
    content_type = (resp.headers.get("Content-Type") or "").lower()
    magic_ext = _detect_image_ext_by_magic(content[:32])

    # 双重判断：Content-Type 或 文件头任一满足即可
    is_image_by_type = content_type.startswith("image/")
    if not is_image_by_type and magic_ext is None:
        preview = content[:200].decode("utf-8", errors="ignore")
        raise ValueError(
            f"返回内容不是图片。Content-Type={content_type or '未知'}，"
            f"响应前200字符={preview!r}"
        )

    # 后缀优先级：魔数 > Content-Type
    ext = magic_ext
    if ext is None:
        ext = content_type.split("/")[-1].split(";")[0].strip()
        if ext == "jpeg":
            ext = "jpg"

    if not file_name:
        path_name = unquote(os.path.basename(urlparse(url).path))
        file_name = path_name if "." in path_name else f"downloaded_image.{ext}"

    if "." not in file_name:
        file_name = f"{file_name}.{ext}"

    file_path = os.path.join(save_dir, file_name)
    with open(file_path, "wb") as f:
        f.write(content)

    return file_path



if __name__ == "__main__":
    # asyncio.run(get_vllm_rerank('中国的首都是哪里',["上海是中国的经济中心。","北京是中国的首都。"],model_name="qwen-rerank"))
    asyncio.run(async_get_img_embedding(["/mnt/ddata2/cc007/omniknow2/parser/rag/parser/mineru_output/ap1000/auto/images/0b0d1f1ee7328ae897b13c9767eef1e1aca535f6c4cf26c638c7014ed1314e1d.jpg","/mnt/ddata2/cc007/omniknow2/parser/rag/parser/mineru_output/ap1000/auto/images/0b0d1f1ee7328ae897b13c9767eef1e1aca535f6c4cf26c638c7014ed1314e1d.jpg"]))
    # img_list = ["/mnt/ddata2/cc007/MinerU-2.6.6/my_project/output/0d477c61-e242-43bd-abcf-403eb44b2185/ap1000_test/auto/images/325b211945259420bc64c994724aab3aa92866261f58218dac2e289446daccf5.jpg", "/mnt/ddata2/cc007/MinerU-2.6.6/my_project/output/0d477c61-e242-43bd-abcf-403eb44b2185/ap1000_test/auto/images/325b211945259420bc64c994724aab3aa92866261f58218dac2e289446daccf5.jpg"]
    # img_list = ["/mnt/ddata2/cc007/MinerU-2.6.6/my_project/output/0d477c61-e242-43bd-abcf-403eb44b2185/ap1000_test/auto/images/325b211945259420bc64c994724aab3aa92866261f58218dac2e289446daccf5.jpg", "/mnt/ddata2/cc007/MinerU-2.6.6/my_project/output/0d477c61-e242-43bd-abcf-403eb44b2185/ap1000_test/auto/images/325b211945259420bc64c994724aab3aa92866261f58218dac2e289446daccf5.jpg", "/mnt/ddata2/cc007/MinerU-2.6.6/my_project/output/0d477c61-e242-43bd-abcf-403eb44b2185/ap1000_test/auto/images/325b211945259420bc64c994724aab3aa92866261f58218dac2e289446daccf5.jpg", "/mnt/ddata2/cc007/MinerU-2.6.6/my_project/output/0d477c61-e242-43bd-abcf-403eb44b2185/ap1000_test/auto/images/325b211945259420bc64c994724aab3aa92866261f58218dac2e289446daccf5.jpg"]
    # img_list = "/mnt/ddata2/cc007/MinerU-2.6.6/my_project/output/0d477c61-e242-43bd-abcf-403eb44b2185/ap1000_test/auto/images/325b211945259420bc64c994724aab3aa92866261f58218dac2e289446daccf5.jpg"
    # asyncio.run(get_img_embedding(img_list))
    # a = get_img_embedding(["/mnt/ddata2/cc007/omniknow2/parser/rag/parser/mineru_output/ap1000/auto/images/0b0d1f1ee7328ae897b13c9767eef1e1aca535f6c4cf26c638c7014ed1314e1d.jpg","/mnt/ddata2/cc007/omniknow2/parser/rag/parser/mineru_output/ap1000/auto/images/0b0d1f1ee7328ae897b13c9767eef1e1aca535f6c4cf26c638c7014ed1314e1d.jpg"])
    # # b = get_img_embedding2("/mnt/ddata2/cc007/omniknow2/parser/rag/3DD77259-CF60-437E-A388-97B3F4051483.jpg")
    # b = get_img_embedding("/mnt/ddata2/cc007/omniknow2/parser/rag/IMG_2694.HEIC.JPG")
    # print(len(a))
    # def cosine_similarity_normed(a, b):
    #     return float(np.dot(a, b))
    # print(cosine_similarity_normed(a, b))
    # download_image2("http://183.129.232.94:8372/public/Tesla/2024_model3/media/中控台总成 （（拆卸和更换））/GUID-D8056675-AD7D-4558-92C0-E09DF56338B8-online-en-US.jpg","/mnt/ddata2/cc007/omniknow2/parser/rag/img_search")
    # download_image("http://omni-oss.czy3d.com:8372/public/Tesla/2024_model3/media/HVAC 模块总成 （（拆卸和更换））/GUID-B054DB41-B001-466B-8EF5-4D20944F1B9B-online-en-US.jpg","/mnt/ddata2/cc007/omniknow2/parser/rag/img_search")

    # try:
    #     saved = download_image("http://omni-oss.czy3d.com:8372/public/Tesla/2024_model3/media/中控台总成 （（拆卸和更换））/GUID-D8056675-AD7D-4558-92C0-E09DF56338B8-online-en-US.jpg","/mnt/ddata2/cc007/omniknow2/parser/rag/img_search")
    #     print(f"下载成功: {saved}")
    # except Exception as err:
    #     print(f"下载失败: {err}")
