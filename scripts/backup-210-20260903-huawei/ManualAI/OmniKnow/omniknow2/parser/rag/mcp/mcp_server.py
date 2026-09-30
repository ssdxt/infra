# server.py
from fastmcp import FastMCP
from vector_db import milvus_client
from schema import ParseRequest, ParseResponse,SearchRequest,SearchResponse
from dotenv import load_dotenv
import os
load_dotenv()
os.environ["FASTMCP_PORT"] = os.getenv("FASTMCP_PORT", "8008")
os.environ["FASTMCP_HOST"] = os.getenv("FASTMCP_HOST", "0.0.0.0")

mcp = FastMCP("文档搜索 MCP 接口")

# @mcp.tool(name="hybrid_search", description="在指定 Milvus collection 中进行混合搜索")
# async def hybrid_search(request: SearchRequest) -> SearchResponse:
#     try:
#         results = await milvus_client.hybrid_search(query=request.query,
#                                                     collection_name=request.collection_name,
#                                                     top_k=request.top_k,
#                                                     threshold=request.threshold,
#                                                     dense_type=request.dense_type,
#                                                     sparse_type=request.sparse_type,
#                                                     reranker_type=request.reranker_type,
#                                                     dense_weight=request.dense_weight,
#                                                     sparse_weight=request.sparse_weight,
#                                                     rerank_model=request.rerank_model
#                                                     )

@mcp.tool(name="hybrid_search", description="在指定 Milvus collection 中进行混合搜索")
async def hybrid_search(query:str, 
                        collection_name:str, 
                        top_k:int=5, 
                        threshold:float=0.5,
                        dense_type="text",
                        sparse_type="text"
                        ,reranker_type="weight",
                        dense_weight=0.7,
                        sparse_weight=0.3,
                        rerank_model=True,
                        **kwargs)  -> SearchResponse:
    try:
        results = await milvus_client.hybrid_search(query=query,
                                                    collection_name=collection_name,
                                                    top_k=top_k,
                                                    threshold=threshold,
                                                    dense_type=dense_type,
                                                    sparse_type=sparse_type,
                                                    reranker_type=reranker_type,
                                                    dense_weight=dense_weight,
                                                    sparse_weight=sparse_weight,
                                                    rerank_model=rerank_model)
        return SearchResponse(
            success=True,
            message=f"搜索成功，返回 {len(results)} 个结果",
            results=results
        )
    
    except Exception as e:
        raise RuntimeError(f"Milvus search failed: {e}")

 
if __name__ == "__main__":
    mcp.run(transport="sse")
    