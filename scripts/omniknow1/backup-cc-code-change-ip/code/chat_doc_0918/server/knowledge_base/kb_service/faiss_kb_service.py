import os
import shutil
import numpy as np
from configs import SCORE_THRESHOLD
from server.knowledge_base.kb_service.base import KBService, SupportedVSType, EmbeddingsFunAdapter
from server.knowledge_base.kb_cache.faiss_cache import kb_faiss_pool, ThreadSafeFaiss
from server.knowledge_base.utils import KnowledgeFile, get_kb_path, get_vs_path
from server.utils import torch_gc
from langchain.docstore.document import Document
from typing import List, Dict, Optional
from server.knowledge_base.utils import get_bm_path
from server.knowledge_base.kb_service.bm25 import BM25Retriever
import jieba
from pathlib import Path

class FaissKBService(KBService):
    vs_path: str
    kb_path: str
    vector_name: str = None
 
    def vs_type(self) -> str:
        return SupportedVSType.FAISS

    def get_vs_path(self):
        return get_vs_path(self.kb_name, self.vector_name)

    def get_kb_path(self):
        return get_kb_path(self.kb_name)

    def load_vector_store(self) -> ThreadSafeFaiss:
        return kb_faiss_pool.load_vector_store(kb_name=self.kb_name,
                                               vector_name=self.vector_name,
                                               embed_model=self.embed_model)

    def save_vector_store(self):
        self.load_vector_store().save(self.vs_path)

    def get_doc_by_id(self, id: str) -> Optional[Document]:
        with self.load_vector_store().acquire() as vs:
            # print("vs.docstore._dict",vs.docstore._dict)
            doc = vs.docstore._dict.get(id)

            #将id信息放到doc数据中
            if doc is not None:
                doc.metadata["vs_id"]=id
                # if doc.metadata.get("g_query") is None:
                #     doc.metadata["g_query"] = ""
                # if doc.metadata.get("answer") is None:
                #     doc.metadata["answer"] = []
                
            return doc
    #更新一条记录
    def update_doc_by_id(self, id: str,block:dict) -> Optional[int]:
        # print("update_doc_by_id",id)
        with self.load_vector_store().acquire() as vs:
            # print("vs.docstore._dict",vs.docstore._dict)
            #更新 metadata信息
            doc = vs.docstore._dict.get(id)
            
            #将id信息放到doc数据中
            if doc is not None:
                #需要重新更新向量
                if doc.page_content != block["page_content"] or doc.metadata["titles"] !=block["metadata"]["titles"]:
                    #删除节点
                    vs.delete([id])
                    # del vs.docstore._dict[id]
                    _docs = [Document(page_content=block["page_content"], metadata=block["metadata"])]
                    data = self._docs_to_embeddings(_docs)
                    ids = vs.add_embeddings(text_embeddings=zip(data["texts"], data["embeddings"]),
                                        metadatas=data["metadatas"],ids=[id])
                    # print("id",id)
                    # print("ids",ids)
                    # print("vs.docstore._dict[id]",vs.docstore._dict[id])
                vs.docstore._dict[id].metadata=block["metadata"]
            vs.save_local(self.vs_path)
            return doc
    
    #从数据库中重新创建embedding
    def update_doc_by_id_embedding(self, id: str,block:dict) -> Optional[int]:
        # print("update_doc_by_id",id)
        with self.load_vector_store().acquire() as vs:
            # print("vs.docstore._dict",vs.docstore._dict)
            #更新 metadata信息
            # doc = vs.docstore._dict.get(id)
            
            _docs = [Document(page_content=block["page_content"], metadata=block["metadata"])]
            data = self._docs_to_embeddings(_docs)
            ids = vs.add_embeddings(text_embeddings=zip(data["texts"], data["embeddings"]),
                                metadatas=data["metadatas"],ids=[id])
            # print("id",id)
            # print("ids",ids)
            # print("vs.docstore._dict[id]",vs.docstore._dict[id])
            vs.docstore._dict[id].metadata=block["metadata"]
            vs.save_local(self.vs_path)

            bm_path = get_bm_path(self.kb_name)
            if os.path.exists(bm_path):
                bm25_retriever = BM25Retriever.load_pth(bm_path,preprocess_func=jieba.lcut_for_search)
                bm25_retriever.delete_document_by_id(id)
                new_docs = [Document(page_content=block["page_content"], metadata=block["metadata"], id=id)]
                bm25_retriever.add_documents(new_docs)
                bm25_retriever.save_pth(name=bm_path)
                
            
            
    #根据Id删除信息
    def delete_doc_by_id(self, id: str) -> Optional[int]:
        with self.load_vector_store().acquire() as vs:
            if id in vs.docstore._dict:
                # 删除id
                del vs.docstore._dict[id]
            
            bm_path = get_bm_path(self.kb_name)
            if os.path.exists(bm_path):
                bm25_retriever = BM25Retriever.load_pth(bm_path,preprocess_func=jieba.lcut_for_search)
                bm25_retriever.delete_document_by_id(id)
                bm25_retriever.save_pth(name=bm_path)

            return id

    
    def do_delete_vs_by_source(self, source: str) -> Optional[int]:
        with self.load_vector_store().acquire() as vs:
            # 查找所有 metadata 中包含 source 的文档 ID
            ids_to_delete = [k for k, v in vs.docstore._dict.items() if v.metadata.get("source") == source]
            
            if ids_to_delete:
                # 删除这些文档的向量
                vs.delete(ids_to_delete)
                vs.save_local(self.vs_path)
                print(f"Deleted documents with source: {source}")
            else:
                print(f"No documents found with source: {source}")

    def do_delete_vs_by_feedback_id(self, feedback_id: str) -> Optional[int]:
        with self.load_vector_store().acquire() as vs:
            # 查找所有 metadata 中包含 source 的文档 ID
            ids_to_delete = [k for k, v in vs.docstore._dict.items() if v.metadata.get("feedback_source_id") == feedback_id]
            
            if ids_to_delete:
                # 删除这些文档的向量
                vs.delete(ids_to_delete)
                vs.save_local(self.vs_path)
                print(f"Deleted documents with feedback_source_id: {feedback_id}")
            else:
                print(f"No documents found with feedback_source_id: {feedback_id}")

     # 删除chunk
    def delete_chunk_by_id(self, _id: str) -> Optional[int]:
        with self.load_vector_store().acquire() as vs:
            if _id in vs.docstore._dict:
                ids = [k for k, v in vs.docstore._dict.items() if k == _id]

                _reversed_index = {v: k for k, v in vs.index_to_docstore_id.items()}

                index_to_delete = [_reversed_index[i] for i in ids]

                # 删除idx
                vs.index.remove_ids(np.array(index_to_delete, dtype=np.int64))
                for idx in index_to_delete:
                    # 删除index_to_docstore_id
                    vs.index_to_docstore_id.pop(idx) #dict index --uuid
                for _id in ids:
                    # 删除docstore
                    vs.docstore._dict.pop(_id)

                #重排
                index_to_docstore_id_items = sorted(vs.index_to_docstore_id.items())#0123  013  012
                for i in range(len(index_to_docstore_id_items)):
                    index_to_docstore_id_items[i] = (i, index_to_docstore_id_items[i][1])
                vs.index_to_docstore_id.clear()
                vs.index_to_docstore_id.update(index_to_docstore_id_items)
                # print("id(index_to_docstore_id)",id(vs.index_to_docstore_id))           

                # print('/////////////',list(vs.index_to_docstore_id.items())[:3])
                # print('*****************',list(vs.docstore._dict)[:3])
                
                vs.save_local(self.vs_path)
            bm_path = get_bm_path(self.kb_name)
            if os.path.exists(bm_path):
                bm25_retriever = BM25Retriever.load_pth(bm_path,preprocess_func=jieba.lcut_for_search)
                bm25_retriever.delete_document_by_id(_id)
                bm25_retriever.save_pth(name=bm_path)
            return _id
    
    
    def do_init(self):
        self.vector_name = self.vector_name or self.embed_model
        self.kb_path = self.get_kb_path()
        self.vs_path = self.get_vs_path()

    def do_create_kb(self):
        if not os.path.exists(self.vs_path):
            os.makedirs(self.vs_path)
        self.load_vector_store()

    def do_drop_kb(self):
        self.clear_vs()
        try:
            shutil.rmtree(self.kb_path)
        except Exception:
            ...

    def do_search(self,
                  query: str,
                  top_k: int,
                  score_threshold: float = SCORE_THRESHOLD,
                  ) -> List[Document]:
        embed_func = EmbeddingsFunAdapter(self.embed_model)
        embeddings = embed_func.embed_query(query)
        with self.load_vector_store().acquire() as vs:
           
            docs = vs.similarity_search_with_score_by_vector(embeddings, k=top_k, score_threshold=score_threshold)
            
        return docs


    def do_bm_search(self,
                  query: str,
                  top_k: int,
                  kb_name: str,
                  ) -> List[Document]:
        
        bm_path = get_bm_path(kb_name)
        # print(bm_path)
        if not os.path.exists(bm_path):
            with self.load_vector_store().acquire() as vs:

                items = list(vs.docstore._dict.items())
                ids = [k for k, v in items]
                context = [v for k, v in items]

                bm25_retriever = BM25Retriever.from_documents(
                    context,
                    # docs,
                    document_ids=ids,
                    preprocess_func=jieba.lcut_for_search,
                )
                bm25_retriever.save_pth(name=bm_path)
        else:
            # 混合检索
            bm25_retriever = BM25Retriever.load_pth(bm_path,preprocess_func=jieba.lcut_for_search)
        bm25_retriever.k = top_k
        docs_bm25 = bm25_retriever.invoke(query)

        
        return docs_bm25
    
    
    def do_add_doc(self,
                   docs: List[Document],
                   **kwargs,
                   ) -> List[Dict]:
        from server.knowledge_base.utils import get_bm_path

        data = self._docs_to_embeddings(docs) # 将向量化单独出来可以减少向量库的锁定时间
        with self.load_vector_store().acquire() as vs:
            ids = vs.add_embeddings(text_embeddings=zip(data["texts"], data["embeddings"]),
                                    metadatas=data["metadatas"])
            
            if not kwargs.get("not_refresh_vs_cache"):
                vs.save_local(self.vs_path)
        
            # first_doc = docs[0][0]
            # source_path = first_doc.metadata['source']
            # path_parts = source_path.split('/')
            # kb_name = path_parts[1]
            bm_path = get_bm_path(self.kb_name)
            
            # print('================ids==================',ids)
            if not os.path.exists(bm_path):
                with self.load_vector_store().acquire() as vs:

                    items = list(vs.docstore._dict.items())
                    ids = [k for k, v in items]
                    context = [v for k, v in items]

                    bm25_retriever = BM25Retriever.from_documents(
                        context,
                        # docs,
                        document_ids=ids,
                        preprocess_func=jieba.lcut_for_search,
                    )
                    bm25_retriever.save_pth(name=bm_path)

            else:
                bm25_retriever = BM25Retriever.load_pth(bm_path,preprocess_func=jieba.lcut_for_search)

                new_docs = [
                    Document(
                        page_content=doc.page_content,
                        metadata={**doc.metadata, "id": id},
                        id=id
                    )
                    for id, doc in zip(ids, docs)
                ]
                
                bm25_retriever.add_documents(new_docs)
                bm25_retriever.save_pth(name=bm_path)

        doc_infos = [{"id": id, "metadata": doc.metadata} for id, doc in zip(ids, docs)]
        torch_gc()
        return doc_infos

    def do_add_qa(self,
                   docs: List[Document],
                   **kwargs
                   ):
        data = self._docs_to_embeddings(docs)
        
        with self.load_vector_store().acquire() as vs:
            vs.add_embeddings(text_embeddings=zip(data["texts"], data["embeddings"]),
                                    metadatas=data["metadatas"])
            vs.save_local(self.vs_path)
        torch_gc()
        return True
    
    def do_delete_doc(self,
                      kb_file: KnowledgeFile,
                      **kwargs):
        with self.load_vector_store().acquire() as vs:
            from pathlib import Path
            # MD BY LB,获取kb_file.filepath的相对路径
            kb_file_rel_filepath = os.path.relpath(kb_file.filepath)
            
            # ids = [k for k, v in vs.docstore._dict.items() if v.metadata.get("source") == kb_file_rel_filepath]
            ids = [k for k, v in vs.docstore._dict.items() if v.metadata.get("source").endswith(kb_file_rel_filepath)]
            if len(ids) > 0:
                vs.delete(ids)
            if not kwargs.get("not_refresh_vs_cache"):
                vs.save_local(self.vs_path)
            
            
            bm_path = get_bm_path(self.kb_name)
            if os.path.exists(bm_path):
                bm25_retriever = BM25Retriever.load_pth(bm_path,preprocess_func=jieba.lcut_for_search)
                # print("ids===================================",ids)
                for id in ids:
                    bm25_retriever.delete_document_by_id(id)
                # print("00000000000000000000000000000000000")
                bm25_retriever.save_pth(name=bm_path)
                # print("111111111111111111111111111")

        return ids

    def do_clear_vs(self):
        with kb_faiss_pool.atomic:
            kb_faiss_pool.pop((self.kb_name, self.vector_name))
        try:
            shutil.rmtree(self.vs_path)
        except Exception:
            ...
        os.makedirs(self.vs_path, exist_ok=True)

        bm_path = get_bm_path(self.kb_name)
        if os.path.exists(bm_path):
            try:
                os.remove(bm_path)
            except Exception:
                ...

    def exist_doc(self, file_name: str):
        if super().exist_doc(file_name):
            return "in_db"

        content_path = os.path.join(self.kb_path, "content")
        if os.path.isfile(os.path.join(content_path, file_name)):
            return "in_folder"
        else:
            return False


if __name__ == '__main__':
    faissService = FaissKBService("test")
    faissService.add_doc(KnowledgeFile("README.md", "test"))
    faissService.delete_doc(KnowledgeFile("README.md", "test"))
    faissService.do_drop_kb()
    print(faissService.search_docs("如何启动api服务"))
