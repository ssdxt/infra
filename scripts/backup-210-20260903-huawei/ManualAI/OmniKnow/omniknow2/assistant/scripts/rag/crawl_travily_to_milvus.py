#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
使用 LangChain 内置 Tavily 工具搜索 topic，
取前 top_k 个网页内容，分块 + embedding 后写入 Milvus。
"""
import argparse
import re
import uuid
from typing import List
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.documents import Document
from langchain_milvus import Milvus
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_milvus.vectorstores import Milvus as LangchainMilvus




def string_to_uuid(input_str, namespace=uuid.NAMESPACE_URL):
    # 使用UUID5生成固定UUID（基于命名空间和输入字符串）
    generated_uuid = uuid.uuid5(namespace, input_str)
    return str(generated_uuid)

def replace_symbols_with_underline(text):
    """
    Replace all non-alphanumeric characters in the input text with underscores.
    """
    text = text.strip()
    text = text.replace("\n", "")
    pattern = r"[^\w\s]"
    replaced = re.sub(pattern, "_", text)
    _pattern = r"_+"
    merged = re.sub(_pattern, "_", replaced)
    merged = merged.replace(' ', '-')
    return merged.strip("_")

def search_with_tavily(topic: str, top_k: int = 1) -> List[Document]:
    print(f"[1/4] Tavily 搜索主题: {topic} (top_k={top_k})")
    # LangChain 内置 Tavily 工具
    tavily_tool = TavilySearchResults(
        max_results=top_k,
        tavily_api_key="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",
        include_raw_content=True, # 一定要开，否则返回内容较少
    )
    # 调用 LangChain 工具
    results = tavily_tool.invoke({"query": topic})
    return results

# 2. 分块
def split_documents(results: List[dict],collection_name:str, topic: str) -> List[Document]:
    docs = []
    for idx, item in enumerate(results, start=1):
        content = item.get("raw_content", "").strip()
        url = item.get("url", "")
        title = item.get("title", "")
        title = replace_symbols_with_underline(title)
        if not content:
            continue
        docs.append(
            Document( 
                page_content=content, # MILVUS_CONTENT_FIELD
                metadata={
                    "id": f"{title}_{string_to_uuid(f'{url}{title}')}", # MILVUS_ID_FIELD
                    "url": f"milvus://{collection_name}/{title}",  # MILVUS_URL_FIELD
                    "title": title, # MILVUS_TITLE_FIELD
                    "source": "websites", 
                    "kb_name": topic,
                    "kb_id": string_to_uuid(topic),
                    "file": "",
                    },
            )
        )
    print(f" Tavily 返回 {len(results)} 条结果，有效内容 {len(docs)} 条")
    print("[2/4] 文档分块中...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    print(f" 分块后 {len(chunks)} 个 chunks")
    return chunks

# 3. Embedding 模型
def get_embedding_model():
    print("[3/4] 初始化 Embedding 模型 (OpenAI)...")
    embeddings = OpenAIEmbeddings(
        openai_api_base="http://0.0.0.0:8115/v1",
        openai_api_key="cc",
        model="embed",
    )
    return embeddings

# 4. 写入 Milvus
def ingest_to_milvus(results, embeddings, collection_name, topic):
    client = LangchainMilvus(
                    embedding_function=embeddings,
                    collection_name=collection_name,
                    connection_args={
                        "uri": "http://localhost:19530",
                    },
                    # optional (if collection already exists with different schema, be careful)
                    drop_old=False,
                )
    
    print(f"[4/4] 写入 Milvus: collection={collection_name}")
    chunks = split_documents(results, collection_name, topic)

    for i, chunk in enumerate(chunks):
        doc_id = chunk.metadata.get("id", str(uuid.uuid4()))
        chunk.metadata["id"] = f"{doc_id}_chunk_{i}" if len(chunks) > 1 else doc_id
    client.add_documents(chunks)
    print(" 写入完成！测试向量检索...")
    try:
        results = client.similarity_search("杭州周边旅游", k=3)
        for i, doc in enumerate(results, start=1):
            print(f" [{i}] {doc.page_content[:100]} ...")
    except Exception as e:
        print(" 检索失败：", e)

# def main():
#     parser = argparse.ArgumentParser()
#     parser.add_argument("--topic", required=True, help="搜索主题")
#     parser.add_argument("--top_k", type=int, default=10)
#     parser.add_argument("--collection", default="web_docs")
#     parser.add_argument("--uri", default=None)
#     args = parser.parse_args()
#     docs = search_with_tavily(args.topic, args.top_k)
#     chunks = split_documents(docs)
#     embeddings = build_embedding_model()
#     ingest_to_milvus(chunks, embeddings, args.collection, args.uri)
# if __name__ == "__main__":
#     main()


def run_with_default():
    topic = "杭州旅游攻略"
    top_k = 10
    collection_name = "web" # 先尝试插入examples集合 看看是否成功
    docs = search_with_tavily(topic, top_k)
    embeddings = get_embedding_model()
    ingest_to_milvus(docs, embeddings, collection_name, topic)

run_with_default()
