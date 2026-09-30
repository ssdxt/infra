import os
import json
from typing import List, Dict, Any
from uuid import uuid4
from datetime import datetime, timedelta

from vector_db import milvus_client_sop

import asyncio

def load_chunks_from_json(path: str) -> List:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    return data


if __name__ == "__main__":
    json_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/item_to_page.json"
    
    chunks = load_chunks_from_json(json_path)
    # collection_name = "sop8_pid"
    collection_name = "images"
    # print(chunks[:3])
    query = "X1004-23"
    # asyncio.run(milvus_client_sop.delete_collection(collection_name))
    print(milvus_client_sop._list_collections())
    # asyncio.run(milvus_client_sop.insert(collection_name, chunks))
    asyncio.run(milvus_client_sop.delete_collection(collection_name))
    # asyncio.run(milvus_client_sop.kerword_search_async(query, collection_name, top_k=3))
    # print(milvus_client_sop.kerword_search(query, collection_name, top_k=3))
    print(milvus_client_sop._list_collections())
    
    
    print("插入完成！")