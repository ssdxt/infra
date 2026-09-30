from langchain.vectorstores import FAISS
from langchain.embeddings.huggingface import HuggingFaceEmbeddings  # Or your preferred embedding model
from tqdm import tqdm
from langchain.vectorstores import FAISS
from typing import List, Dict
import faiss
def load_faiss_index(index_path: str, embeddings) -> FAISS:
    return FAISS.load_local(index_path, embeddings)

def create_enhanced_text(doc) -> str:
    metadata = doc.metadata
    enhanced_text = (
        (' '.join(metadata.get('keyword', []))) + " " +
        (' '.join(metadata.get('tables', []))) + "\n" +
        (metadata.get('titles', '')) + "\n" +
        doc.page_content
    )
    return enhanced_text

def process_batch(batch, new_embeddings) -> tuple:
    enhanced_texts = [create_enhanced_text(doc) for doc in batch]
    original_texts = [doc.page_content for doc in batch]
    metadatas = [doc.metadata for doc in batch]
    new_vectors = new_embeddings.embed_documents(enhanced_texts)
    return original_texts, new_vectors, metadatas

def update_vectors_in_faiss(old_index_path: str, new_index_path: str, 
                            old_embeddings, new_embeddings,
                            batch_size: int = 1000):
    # 加载旧的索引
    old_faiss = load_faiss_index(old_index_path, old_embeddings)
    print(f"旧的向量库中共有 {len(old_faiss.docstore._dict)} 条数据")
    # 获取所有的文档
    docs = list(old_faiss.docstore._dict.values())
    ids = list(old_faiss.docstore._dict.keys())

    total_docs = len(docs)

    # 创建新的 FAISS 实例
    new_faiss = None

    # 使用批处理更新向量
    for i in tqdm(range(0, total_docs, batch_size)):
        batch = docs[i:i+batch_size]
        batch_id = ids[i:i+batch_size]
        
        original_texts, new_vectors, metadatas = process_batch(batch, new_embeddings)

        if new_faiss is None:
            # 为第一批创建新的 FAISS 实例
            new_faiss = FAISS.from_embeddings(
                text_embeddings=list(zip(original_texts, new_vectors)),
                embedding=new_embeddings,
                metadatas=metadatas,
                ids=batch_id
            )
        else:
            # 将后续批次添加到现有索引
            new_faiss.add_embeddings(
                text_embeddings=list(zip(original_texts, new_vectors)),
                metadatas=metadatas,
                ids=batch_id
            )

        # 定期保存索引
        if (i + batch_size) % (batch_size * 10) == 0:
            new_faiss.save_local(f"{new_index_path}_temp_{i+batch_size}")

    print(f"新保存的向量库中共有 {len(new_faiss.docstore._dict)} 条数据")
    # 最终保存完整索引
    new_faiss.save_local(new_index_path)

    return new_faiss

def update_vdb(old_index_path,new_index_path,old_embedding_model,new_embedding_model):

    old_embeddings = HuggingFaceEmbeddings(model_name=old_embedding_model,encode_kwargs = {'normalize_embeddings': True})
    new_embeddings = HuggingFaceEmbeddings(model_name=new_embedding_model,encode_kwargs = {'normalize_embeddings': True})

    update_vectors_in_faiss(old_index_path, new_index_path, old_embeddings, new_embeddings)
    print("FAISS 更新完成")

def test_search(query, top_k, threshold, vs_path, embed_model):

    encode_kwargs = {'normalize_embeddings': True}
    new_embeddings = HuggingFaceEmbeddings(model_name=embed_model,encode_kwargs=encode_kwargs)
    # new_vs = FAISS.load_local(vs_path, new_embeddings,allow_dangerous_deserialization=True)
    new_vs = FAISS.load_local(vs_path, new_embeddings)
    print(list(new_vs.index_to_docstore_id.items())[:3])
    # results = new_vs.similarity_search(query, k=3)
    embeddings = new_embeddings.embed_query(query)
    results = new_vs.similarity_search_with_score_by_vector(embeddings, k=top_k, score_threshold=threshold)
    return results

def test_ids(vs_path, embed_model):
    encode_kwargs = {'normalize_embeddings': True}
    new_embeddings = HuggingFaceEmbeddings(model_name=embed_model,encode_kwargs=encode_kwargs)
    # new_vs = FAISS.load_local(vs_path, new_embeddings,allow_dangerous_deserialization=True)
    new_vs = FAISS.load_local(vs_path, new_embeddings)
    
    # print(list(new_vs.docstore._dict)[:3])
    temp = {}

    # for k, v in new_vs.docstore._dict.items():
    #     # print(k, v)
    #     # break
    #     if v.page_content not in temp:
    #         temp[v.page_content] = [(k,v)]
    #     else:
    #         temp[v.page_content].append(list((k,v)))
    
    # print(list(temp.items())[:3])
    return list(new_vs.docstore._dict.items())[5:10]


def delete_doc_by_id(vs_path,embed_model):
    index = faiss.read_index(f"{vs_path}/index.faiss")

    # 获取索引中的向量数量
    num_vectors = index.ntotal

    # 获取向量维度
    dim = index.d

    print(f"索引类名: {type(index)}")
    print(f"向量维度: {dim}")
    print(f"索引中的向量数量: {num_vectors}")

    encode_kwargs = {'normalize_embeddings': True}
    new_embeddings = HuggingFaceEmbeddings(model_name=embed_model,encode_kwargs=encode_kwargs)
    # new_vs = FAISS.load_local(vs_path, new_embeddings,allow_dangerous_deserialization=True)
    new_vs = FAISS.load_local(vs_path, new_embeddings)

    temp = "国家核应急平台总体框架及关键技术研究.pdf"

    ids = [k for k, v in new_vs.docstore._dict.items() if temp in v.metadata.get("source")]

    if len(ids) > 0:
        new_vs.delete(ids)

    new_vs.save_local("./hjj_new")
    
    # print("docstore长度: ",len(list(new_vs.docstore._dict.items())))

    # print("index_to_docstore_id长度: ",len(list(new_vs.index_to_docstore_id.items())))
    


def test_faiss_num(vs_path,embed_model):
    index = faiss.read_index(f"{vs_path}/index.faiss")

    # 获取索引中的向量数量
    num_vectors = index.ntotal

    # 获取向量维度
    dim = index.d

    print(f"索引类名: {type(index)}")
    print(f"向量维度: {dim}")
    print(f"索引中的向量数量: {num_vectors}")

    encode_kwargs = {'normalize_embeddings': True}
    new_embeddings = HuggingFaceEmbeddings(model_name=embed_model,encode_kwargs=encode_kwargs)
    # new_vs = FAISS.load_local(vs_path, new_embeddings,allow_dangerous_deserialization=True)
    new_vs = FAISS.load_local(vs_path, new_embeddings)
    
    print("docstore长度: ",len(list(new_vs.docstore._dict.items())))

    print("index_to_docstore_id长度: ",len(list(new_vs.index_to_docstore_id.items())))
    

if __name__ == "__main__":
    
    # old_vdb = "./hjj/bge-large-zh"
    # old_vdb = "./hjj_new"
    
    old_vdb = "/home/cc007/cc/gcy/kg_rag/latest_version/my_kg/temp_faiss_index_100w"
    # new_vdb = "/mnt/ddata/chat_doc/knowledge_base/gcy_test/vector_store/bge-large-zh"
    old_embedding_model = "/mnt/ddata/models/bge-large-zh-v1.5"
    # old_vdb = "/mnt/ddata/dct/chat_doc20240902/knowledge_base/核电网站/vector_store/bge-large-zh"
    # old_vdb = "/mnt/ddata/dct/chat_doc20240902/knowledge_base/核电网站/vector_store/bge-large-zh"
    
    # new_embedding_model = "/mnt/ddata/models/m3e-base"

    # 更新向量库（新建）
    # update_vdb(old_vdb, new_vdb, old_embedding_model, old_embedding_model)

    # 测试搜索
    # query = "工作台夹紧器"
    # query = "中华人民共和国济南二机床集团有限公司请将本使用说明书放在压力机旁边，以便操作人员随时查阅济南二机床集团有限公司售后服务电话电话"
    # ids = "3b0f5c89-de46-40ba-9a6f-bbc7d8c4415f"
    # print(test_search(query, top_k=3, threshold=1.5, vs_path=old_vdb, embed_model=old_embedding_model))
    # print(test_search(query, top_k=3, threshold=0.8, vs_path=new_vdb, embed_model=new_embedding_model))

    # # 测试ids变没变
    # print(test_ids(vs_path=new_vdb, embed_model=new_embedding_model))
    # test_faiss_num(vs_path=old_vdb, embed_model=old_embedding_model)
    # delete_doc_by_id(vs_path=old_vdb, embed_model=old_embedding_model)
    

    print(test_ids(vs_path=old_vdb, embed_model=old_embedding_model))





# import faiss

# # 加载Faiss索引文件
# index = faiss.read_index("/mnt/ddata/gcy/chat_doc/server/knowledge_base/new_jh_yy2222/index.faiss")

# # 获取索引中的向量数量
# num_vectors = index.ntotal

# # 获取向量维度
# dim = index.d

# print(f"索引类名: {type(index)}")
# print(f"索引中的向量数量: {num_vectors}")
# print(f"向量维度: {dim}")

# # 输出前 2 个向量
# for i in range(min(num_vectors, 2)):
#     vector = index.reconstruct(i)
#     print(f"Vector {i}: {vector}")

