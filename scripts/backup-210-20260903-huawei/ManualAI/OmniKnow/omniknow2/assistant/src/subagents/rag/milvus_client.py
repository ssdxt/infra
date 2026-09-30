import os
import sys
from pathlib import Path
from pydantic import BaseModel, PrivateAttr

project_root = str(Path(__file__).resolve().parents[4])
sys.path.append(os.path.join(project_root, 'parser/rag'))

from vector_db.milvus_db import MilvusClient


class MilvusDB(BaseModel):
    _client: MilvusClient = PrivateAttr(default=None)

    def __init__(self, **data):
        super().__init__(**data)
        object.__setattr__(self, "_client", MilvusClient())

    def __getattr__(self, name: str):
        client = object.__getattribute__(self, "_client")
        if client is None:
            raise AttributeError("MilvusClient not initialized")
        return getattr(client, name)
