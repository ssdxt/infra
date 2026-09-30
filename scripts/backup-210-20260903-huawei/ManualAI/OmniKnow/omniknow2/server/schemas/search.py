from pydantic import BaseModel
from uuid import UUID


class HybridSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    threshold: float = 0.5
    rerank_model: bool = True