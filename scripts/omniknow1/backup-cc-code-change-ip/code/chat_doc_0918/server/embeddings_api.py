from langchain.docstore.document import Document
from configs import EMBEDDING_MODEL, logger, EMBEDDING_SERVER
from server.model_workers.base import ApiEmbeddingsParams
from server.utils import BaseResponse, get_model_worker_config, list_embed_models, list_online_embed_models
from fastapi import Body
from typing import Dict, List
from langchain.embeddings.huggingface import HuggingFaceEmbeddings
from configs.model_config import EMBEDDING_MODEL_SERVER
from server.utils import load_local_embeddings

online_embed_models = list_online_embed_models()
embeddings = None

def embed_texts(
    texts: List[str],
    embed_model: str = EMBEDDING_MODEL,
    to_query: bool = False,
) -> BaseResponse:
    '''
    对文本进行向量化。返回数据格式：BaseResponse(data=List[List[float]])
    TODO: 也许需要加入缓存机制，减少 token 消耗
    '''
    
    try:
        if embed_model in list_online_embed_models(): # 使用在线API
            config = get_model_worker_config(embed_model)
            worker_class = config.get("worker_class")
            worker = worker_class()
            if worker_class.can_embedding():
                params = ApiEmbeddingsParams(texts=texts, to_query=to_query)
                resp = worker.do_embeddings(params)
                return BaseResponse(**resp)
        if embed_model in list_embed_models() and not EMBEDDING_SERVER: # 使用本地Embeddings模型
            embeddings = load_local_embeddings(model=embed_model)

            return BaseResponse(data=embeddings.embed_documents(texts),embedding=embeddings)
        elif EMBEDDING_SERVER:
            # vllm启动的embedding
            embeddings = load_local_embeddings(model=embed_model)
            return BaseResponse(data=embeddings.encode(texts)[0],embedding=embeddings)
        else:
            # 这里先临时这样写，后面会改
            # 本地绝对路径
            print('here00000000000000000000')

            encode_kwargs = {'normalize_embeddings': True}
            embeddings = HuggingFaceEmbeddings(model_name=embed_model,encode_kwargs=encode_kwargs)

            return BaseResponse(data=embeddings.embed_documents(texts),embedding=embeddings)
        
    except Exception as e:
        logger.error(e)
        return BaseResponse(code=500, msg=f"文本向量化过程中出现错误：{e}")

def embed_texts_endpoint(
    texts: List[str] = Body(..., description="要嵌入的文本列表", examples=[["hello", "world"]]),
    embed_model: str = Body(EMBEDDING_MODEL, description=f"使用的嵌入模型，除了本地部署的Embedding模型，也支持在线API({online_embed_models})提供的嵌入服务。"),
    to_query: bool = Body(False, description="向量是否用于查询。有些模型如Minimax对存储/查询的向量进行了区分优化。"),
) -> BaseResponse:
    '''
    对文本进行向量化，返回 BaseResponse(data=List[List[float]])
    '''
    return embed_texts(texts=texts, embed_model=embed_model, to_query=to_query)


def embed_documents(
    docs: List[Document],
    embed_model: str = EMBEDDING_MODEL,
    to_query: bool = False,
) -> Dict:
    """
    将 List[Document] 向量化，转化为 VectorStore.add_embeddings 可以接受的参数
    """
    temp_texts = [
        (' '.join(x.metadata['keyword']) if 'keyword' in x.metadata else '') + " "+# 关键词增强
        (' '.join(x.metadata['tables']) if 'tables' in x.metadata else '') +"\n"+ 
            #  (' '.join(x.metadata['images']) if 'images' in x.metadata else '') + # 图表增强
        (x.metadata['titles'] if 'titles' in x.metadata else '') +"\n"+  # 标题增强
        x.page_content for x in docs]
    
    texts = [x.page_content for x in docs]
    metadatas = [x.metadata for x in docs]
    
        
    embeddings = embed_texts(texts=temp_texts, embed_model=embed_model, to_query=to_query).data 
    embedding_model = embed_texts(texts=temp_texts, embed_model=embed_model, to_query=to_query).embedding
    # for x in texts:
    #     print("<<<<<",x)
    if embeddings is not None:
        return {
            "texts": texts,
            "embeddings": embeddings,
            "metadatas": metadatas,
            "embedding_model":embedding_model
        }


