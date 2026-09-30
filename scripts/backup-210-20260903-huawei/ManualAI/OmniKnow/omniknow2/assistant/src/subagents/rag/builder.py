from src.config.tools import SELECTED_RAG_PROVIDER, RAGProvider
from src.subagents.rag.dify import DifyProvider
from src.subagents.rag.milvus import MilvusProvider
from src.subagents.rag.moi import MOIProvider
from src.subagents.rag.qdrant import QdrantProvider
from src.subagents.rag.ragflow import RAGFlowProvider
from src.subagents.rag.retriever import Retriever
from src.subagents.rag.vikingdb_knowledge_base import VikingDBKnowledgeBaseProvider
from src.subagents.rag.milvus_rag import MilvusAPIRetriever
# from src.subagents.rag.milvus_api import MilvusAPIRetriever


def build_retriever() -> Retriever | None:
    if SELECTED_RAG_PROVIDER == RAGProvider.DIFY.value:
        return DifyProvider()
    if SELECTED_RAG_PROVIDER == RAGProvider.RAGFLOW.value:
        return RAGFlowProvider()
    elif SELECTED_RAG_PROVIDER == RAGProvider.MOI.value:
        return MOIProvider()
    elif SELECTED_RAG_PROVIDER == RAGProvider.VIKINGDB_KNOWLEDGE_BASE.value:
        return VikingDBKnowledgeBaseProvider()
    elif SELECTED_RAG_PROVIDER == RAGProvider.MILVUS.value:
        return MilvusProvider()
    elif SELECTED_RAG_PROVIDER == RAGProvider.QDRANT.value:
        return QdrantProvider()
    elif SELECTED_RAG_PROVIDER == RAGProvider.MILVUS_API.value:
        return MilvusAPIRetriever()
    elif SELECTED_RAG_PROVIDER:
        raise ValueError(f"Unsupported RAG provider: {SELECTED_RAG_PROVIDER}")
    return None
