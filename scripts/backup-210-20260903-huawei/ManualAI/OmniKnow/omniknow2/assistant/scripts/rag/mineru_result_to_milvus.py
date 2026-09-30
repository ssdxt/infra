#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
从 MinerU 解析结果 JSON 生成 LangChain Document，并写入 Milvus。

规则：
- 按 JSON 中的顺序遍历
- type == "text": 按顺序累加 text，直到总长度接近 / 将超过 1000 字符时，切一个新的 chunk
- type == "image": 直接用 image_caption 作为 page_content，单独成一个 chunk
- type == "table": 直接用 table_caption 作为 page_content，单独成一个 chunk
- 每个 chunk 有自增的 chunk_id（0,1,2,...）
- metadata:
    "id":      f"{filename}_{chunk_id}"
    "url":     f"milvus://{collection_name}/{filename}"
    "title":   ""
    "source":  "mineru"
    "file":    content_path
    "type":    "text" | "image" | "table"
    "img_path":  对 text 为空字符串，对 image/table 取原字段
    "table_body": 对 table 取原字段，其他类型为空字符串
"""

import uuid
import json
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_milvus import Milvus as LangchainMilvus
from langchain_openai import OpenAIEmbeddings


MAX_TEXT_LEN = 200  # text chunk 最大长度（按字符数）


def string_to_uuid(input_str, namespace=uuid.NAMESPACE_URL):
    # 使用UUID5生成固定UUID（基于命名空间和输入字符串）
    generated_uuid = uuid.uuid5(namespace, input_str)
    return str(generated_uuid)


def get_embedding_model():
    print("初始化 Embedding 模型 (OpenAI)...")
    embeddings = OpenAIEmbeddings(
        openai_api_base="http://0.0.0.0:8115/v1",
        openai_api_key="cc",
        model="embed",
    )
    return embeddings

def mineru_json_to_docs(
    content_path: str,
    collection_name: str = "cctest",
) -> List[Document]:
    """将 MinerU json 转成一组 LangChain Document。"""
    content_path = str(content_path)
    filename = Path(content_path).stem

    with open(content_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    chunks: List[Document] = []
    chunk_id = 0

    # text 累加缓存
    current_text_parts: List[str] = []
    current_length = 0

    def flush_text_chunk():
        """把当前累积的 text flush 成一个 Document。"""
        nonlocal chunks, chunk_id, current_text_parts, current_length
        if not current_text_parts:
            return
        content = "\n".join(current_text_parts).strip()
        if not content:
            # 重置缓存然后返回
            current_text_parts = []
            current_length = 0
            return

        doc = Document(
            page_content=content,
            metadata={
                "id": f"{filename}_{chunk_id}",
                "url": f"milvus://{collection_name}/{filename}",
                "title": "",
                "source": "mineru",
                "file": content_path,
                "type": "text",
                "img_path": "",
                "table_body": "",
                "page_idx": item.get("page_idx"),
            },
        )
        chunks.append(doc)
        chunk_id += 1
        current_text_parts = []
        current_length = 0

    for item in items:
        item_type = item.get("type")

        # 先处理 text 类型
        if item_type == "text":
            text = (item.get("text") or "").strip()
            if not text:
                continue

            # 如果再加上当前这段会超过 MAX_TEXT_LEN，就把之前的 flush 掉
            if current_length > 0 and current_length + len(text) > MAX_TEXT_LEN:
                flush_text_chunk()

            # 新 chunk 起点
            current_text_parts.append(text)
            current_length += len(text)

        # image / table 单独成 chunk
        elif item_type == "image":
            # 先把尚未 flush 的 text 写入
            # flush_text_chunk()

            caption_list = item.get("image_caption") or []
            caption = " ".join(caption_list).strip()
            if not caption:
                # 如果没 caption，就可以选择跳过，或者用一个占位符
                continue

            doc = Document(
                page_content=caption,
                metadata={
                    "id": f"{filename}_{chunk_id}",
                    "url": f"milvus://{collection_name}/{filename}",
                    "title": "",
                    "source": "mineru",
                    "file": content_path,
                    "type": "image",
                    "img_path": item.get("img_path", ""),
                    "table_body": "",
                    "page_idx": item.get("page_idx"),
                },
            )
            chunks.append(doc)
            chunk_id += 1

        elif item_type == "table":
            # 先把尚未 flush 的 text 写入
            # flush_text_chunk()

            caption_list = item.get("table_caption") or []
            caption = " ".join(caption_list).strip()
            if not caption:
                # caption = "[表格]"
                continue  # 如果没 caption，就直接跳过
            doc = Document(
                page_content=caption,
                metadata={
                    "id": f"{filename}_{chunk_id}",
                    "url": f"milvus://{collection_name}/{filename}",
                    "title": "",
                    "source": "mineru",
                    "file": content_path,
                    "type": "table",
                    "img_path": item.get("img_path", ""),
                    "table_body": item.get("table_body", "") or "",
                    "page_idx": item.get("page_idx"),
                },
            )
            chunks.append(doc)
            chunk_id += 1

        else:
            # 其它未知类型直接忽略
            continue

    # 循环结束后，把最后一段 text flush 掉
    flush_text_chunk()

    return chunks


def get_milvus_client(
    collection_name: str = "metest",
    uri: str = "http://localhost:19530",
) -> LangchainMilvus:
    """构造 LangchainMilvus 客户端。"""
    embeddings = get_embedding_model()
    client = LangchainMilvus(
        embedding_function=embeddings,
        collection_name=collection_name,
        connection_args={
            "uri": uri,
        },
        drop_old=False,
    )
    return client


content_path = "/mnt/ddata2/user/zhangga/MinerU/demo/test/柴油机维修快速入门60天/auto/柴油机维修快速入门60天_content_list.json"
collection_name = "metest"
uri = "http://localhost:19530"
docs = mineru_json_to_docs(content_path, collection_name)
print(f"生成 Document 数量: {len(docs)}, 写入 Milvus: collection={collection_name}")
client = get_milvus_client(collection_name=collection_name, uri=uri)
client.add_documents(docs)
print("✅ 完成写入 Milvus")


