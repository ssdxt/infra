import operator
from abc import ABC, abstractmethod

import os

import numpy as np
from langchain.embeddings.base import Embeddings
from langchain.docstore.document import Document

from server.db.repository.knowledge_base_repository import (
    kb_add, delete_kb_from_db, kb_list, kb_exists,
    load_kb_from_db, get_kb_detail,load_kb_from_db_id,
)
from server.db.repository.knowledge_file_repository import (
    update_file_to_db,add_file_to_db, delete_file_from_db, delete_files_from_db, file_exists_in_db,
    count_files_from_db, list_files_from_db, get_file_detail, delete_file_from_db,
    list_docs_from_db,
)

from configs import (kbs_config, VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD,
                     EMBEDDING_MODEL, KB_INFO)
from server.knowledge_base.utils import (
    get_kb_path, get_doc_path, KnowledgeFile,
    list_kbs_from_folder, list_files_from_folder,
)

from typing import List, Union, Dict, Optional

from server.embeddings_api import embed_texts
from server.embeddings_api import embed_documents

import fitz  # PyMuPDF
import json
import re
import os

def is_regex(s):
    special_chars = re.compile(r'[\.\*\+\?\|\(\)\[\]\{\}]')
    return bool(special_chars.search(s))

def potential_title(s):
    if len(s) == 0:
        return False
    index_of_newline = s.find('\n')
    if index_of_newline == -1:
        return re.sub(r'\s+', '', s)
    return re.sub(r'\s+', '', s[:index_of_newline])
    

def get_sub_paragraph(prefix, titles_before, paragraph, patterns, index, max_length=0): # 根据patterns中的匹配项递归拆分
    paragraph = paragraph.strip()
    if not paragraph:
        return []
    if paragraph.find(prefix) == -1 and index > 0: # 必须从第一级标题开始加，否则会统一加上index=0的那部分文本
        title = potential_title(paragraph)
        paragraph = titles_before + f"{prefix}"*index + paragraph
        titles_before = titles_before + f"{prefix}"*index + title
    can_rec = True if index < len(patterns) - 1 else False
    replace_pattern = '\n' if is_regex(patterns[index]) else patterns[index]
    sub_paragraph_list = []
    current_sub_paragraph = ""
    for sub_paragraph in re.split(patterns[index], paragraph):

        if len(current_sub_paragraph) + len(sub_paragraph) + 1 <= max_length: # 用不用maxlength
            if current_sub_paragraph:
                current_sub_paragraph += replace_pattern
            current_sub_paragraph += sub_paragraph
        else:
            if can_rec:
                sub_paragraph_list.extend(get_sub_paragraph(prefix, titles_before, current_sub_paragraph, patterns, index+1, max_length))
            # else:
            #     sub_paragraph_list.append(current_sub_paragraph) # 用maxlength后需要把不能分割的加进去
            current_sub_paragraph = sub_paragraph
    if current_sub_paragraph:
        if can_rec:
            sub_paragraph_list.extend(get_sub_paragraph(prefix, titles_before, current_sub_paragraph, patterns, index+1, max_length))
        else:
            sub_paragraph_list.append(current_sub_paragraph)
    return sub_paragraph_list

def extract_text_from_pdf(file_path, use_chunk=False):
    max_length = 0
    # Load the PDF file
    pdf_document = fitz.open(file_path)
    
    # Create a dictionary to hold the extracted text
    # extracted_text = {}
    extracted_text = ""
    # Loop through each page in the PDF
    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)
        # Extract text from the current page
        page_text = page.get_text()
        # Store the extracted text in the dictionary, using the page number as the key
        # extracted_text[page_number] = remove_special_chars(page_text)
        extracted_text += remove_special_chars(page_number, page_text)
    
    # chapter_que = collections.deque(['1. 1. 1'])
    # pattern = r'\d+\.\s*\d+\.\s*\d+'
    pattern = r'(?:\b\d+\.\s*\d+\.\s*\d+|\b第[一二三四五六七八九十]{1,2}[节章]|\b[一二三四五六七八九十]{1,2}、|\b\d+[、.]\d*\
                     |\b\（[一二三四五六七八九十]{1,2}\）)'
    # chapters = re.split(re.compile(pattern), extracted_text)[1:]
    # patterns = [r'\n{2,}', '。\n', '\n']
    patterns = [r'\b第[一二三四五六七八九十]{1,2}[章]', r'\b第[一二三四五六七八九十]{1,2}[节]', r'\b[一二三四五六七八九十]{1,2}、', r'\b\([一二三四五六七八九十]{1,2}\)', r'\n{2,}']
    chapters = [extracted_text]
    chapters = [sub_chapter for chapter in chapters for sub_chapter in get_sub_paragraph('#', '', chapter.strip(), patterns, 0)]

    chapters = [post_split_process(chapter) for chapter in chapters]
    chapter_min_len = 50
    chapters = [chapter for chapter in chapters if len(chapter) > chapter_min_len and chapter.find("**") != -1]

    if use_chunk:
        i = 0
        while i < len(chapters) - 1:  # Subtract 1 to avoid an IndexError on the last item
            if len(chapters[i]) < 1000:
                chapters[i] += chapters[i + 1]  # Combine the string with the next string
                del chapters[i + 1]  # Remove the next string from the list
            else:
                i += 1  # Move on to the next index
    total_len = 0
    for i, sub_chapter in enumerate(chapters):
        total_len += len(sub_chapter)
        if len(sub_chapter) > max_length:
            max_length = len(sub_chapter)
    print(f"max: {max_length}, avg: {total_len/(i+1)}")


    
    # Close the PDF file
    pdf_document.close()
    
    return chapters


def remove_special_chars(page_number, text):
    # Define the special characters you want to remove
    special_chars = special_chars = '…■.-'
    # Use re.sub to replace the special characters with an empty string
    text = re.sub(f"[{re.escape(special_chars)}]", "", text)
    # text = re.sub(r'\s+', '\n', text)
    # text = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', '', text)
    # text = re.sub(r'\n+', '\n', text)
    # text = f"\npage number {page_number}\n" + text
    return text

def post_split_process(text: str, title_split='**'):
    text = text.replace('\n', title_split, 1)
    title_pos = text.find(title_split)
    if title_pos != -1:
        text = re.sub(r'\s+', '', text[:title_pos]) + text[title_pos:]
    text = re.sub(r'\s+', ' ', text)
    return text


def normalize(embeddings: List[List[float]]) -> np.ndarray:
    '''
    sklearn.preprocessing.normalize 的替代（使用 L2），避免安装 scipy, scikit-learn
    '''
    norm = np.linalg.norm(embeddings, axis=1)
    norm = np.reshape(norm, (norm.shape[0], 1))
    norm = np.tile(norm, (1, len(embeddings[0])))
    return np.divide(embeddings, norm)


class SupportedVSType:
    FAISS = 'faiss'
    MILVUS = 'milvus'
    DEFAULT = 'default'
    ZILLIZ = 'zilliz'
    PG = 'pg'
    ES = 'es'


class KBService(ABC):

    def __init__(self,
                 knowledge_base_name: str,
                 embed_model: str = EMBEDDING_MODEL,
                 ):
        self.kb_name = knowledge_base_name
        self.kb_info = KB_INFO.get(knowledge_base_name, f"关于{knowledge_base_name}的知识库")
        self.embed_model = embed_model
        self.kb_path = get_kb_path(self.kb_name)
        self.doc_path = get_doc_path(self.kb_name)
        #创建者email
        self.create_user_email =None
        #知识库所属部门
        self.dep_id=None
        self.do_init()

    def __repr__(self) -> str:
        return f"{self.kb_name} @ {self.embed_model}"

    def save_vector_store(self):
        '''
        保存向量库:FAISS保存到磁盘，milvus保存到数据库。PGVector暂未支持
        '''
        pass

    def create_kb(self,kb_type=None):
        """
        创建知识库
        """
        if not os.path.exists(self.doc_path):
            os.makedirs(self.doc_path)
        self.do_create_kb()  
        # session,kb_name,kb_info,create_user_email,dep_id
        status = kb_add(kb_name=self.kb_name,kb_type=kb_type,kb_info=self.kb_info,create_user_email=self.create_user_email,dep_id=self.dep_id,embedding_name=self.embed_model)
        return status
    
    def update_kb(self):
        """
        创建知识库
        """
        # session,kb_name,kb_info,create_user_email,dep_id
        status = kb_add(kb_name=self.kb_name,kb_type=None,kb_info=self.kb_info,create_user_email=None,dep_id=self.dep_id,embedding_name=self.embed_model)
        return status

    def clear_vs(self):
        """
        删除向量库中所有内容
        """
        self.do_clear_vs()
        status = delete_files_from_db(self.kb_name)
        return status

    def drop_kb(self):
        """
        删除知识库
        """
        self.do_drop_kb()
        status = delete_kb_from_db(self.kb_name)
        return status

    def _docs_to_embeddings(self, docs: List[Document]) -> Dict:
        '''
        将 List[Document] 转化为 VectorStore.add_embeddings 可以接受的参数
        '''
        return embed_documents(docs=docs, embed_model=self.embed_model, to_query=False)

    def add_doc(self, kb_file: KnowledgeFile, docs: List[Document] = [], **kwargs):
        """
        向知识库添加文件
        如果指定了docs，则不再将文本向量化，并将数据库对应条目标为custom_docs=True
        """
        if docs:
            custom_docs = True
            for doc in docs:
                doc.metadata.setdefault("source", kb_file.filepath)
        else:
            docs = kb_file.file2text()
            # chapters = extract_text_from_pdf(kb_file.filepath)
            # docs = [Document(text) for text in chapters]
            # for doc in docs:
            #     doc.metadata.setdefault("source", kb_file.filepath)
            custom_docs = False

        if docs:
            self.do_delete_doc(kb_file, **kwargs)
            doc_infos = self.do_add_doc(docs, **kwargs)
            # print(doc_infos)
            status = update_file_to_db(kb_file,
                                    custom_docs=custom_docs,
                                    docs_count=len(docs),
                                    doc_infos=doc_infos)
        else:
            status = False
        return status

    def add_qa(self,docs: List[Document],**kwargs):
        if docs:
            qa_status = self.do_add_qa(docs, **kwargs)

        return qa_status
    
    def delete_doc(self, kb_file: KnowledgeFile, delete_content: bool = False, **kwargs):
        """
        从知识库删除文件
        """
        self.do_delete_doc(kb_file, **kwargs)
        status = delete_file_from_db(kb_file)

        if kb_file.filepath.lower().endswith('.pdf'):
            base_filepath = kb_file.filepath.rsplit('.', 1)[0]
            doc_filepath = base_filepath + '.doc'
            docx_filepath = base_filepath + '.docx'
            
            if os.path.exists(doc_filepath):
                os.remove(doc_filepath)
            elif os.path.exists(docx_filepath):
                os.remove(docx_filepath)

        if delete_content and os.path.exists(kb_file.filepath):
            os.remove(kb_file.filepath)
        return status

    def update_info(self, kb_info: str):
        """
        更新知识库介绍
        """
        self.kb_info = kb_info
        status = kb_add(self.kb_name, self.kb_info, self.vs_type(), self.embed_model)
        return status

    def update_doc(self, kb_file: KnowledgeFile, docs: List[Document] = [], **kwargs):
        """
        使用content中的文件更新向量库
        如果指定了docs，则使用自定义docs，并将数据库对应条目标为custom_docs=True
        """
        if os.path.exists(kb_file.filepath):
            self.do_delete_doc(kb_file, **kwargs)
            return self.add_doc(kb_file, docs=docs, **kwargs)

    def exist_doc(self, file_name: str):
        return file_exists_in_db(KnowledgeFile(knowledge_base_name=self.kb_name,
                                               filename=file_name))

    def list_files(self, file_name=None, parse_status=None, page_start=None, page_end=None):
        return list_files_from_db(self.kb_name,file_name=file_name,parse_status=parse_status,page_start=page_start,page_end=page_end)

    def count_files(self):
        return count_files_from_db(self.kb_name)

    def search_docs(self,
                    query: str,
                    top_k: int = VECTOR_SEARCH_TOP_K,
                    score_threshold: float = SCORE_THRESHOLD,
                    ):
        docs = self.do_search(query, top_k, score_threshold)
        return docs

    def get_doc_by_id(self, id: str) -> Optional[Document]:
        return None
    
    def update_doc_by_id(self, id: str) -> Optional[Document]:
        return None

    def list_docs(self, file_name: str = None, metadata: Dict = {}) -> List[Document]:
        '''
        通过file_name或metadata检索Document
        '''
        doc_infos = list_docs_from_db(kb_name=self.kb_name, file_name=file_name, metadata=metadata)
        
        # docs = [ for x in doc_infos]
        docs=[]
        for x in doc_infos:
            xx = self.get_doc_by_id(x["id"])
            if xx:
                docs.append(xx)
        return docs

    @abstractmethod
    def do_create_kb(self):
        """
        创建知识库子类实自己逻辑
        """
        pass

    @staticmethod
    def list_kbs_type():
        return list(kbs_config.keys())

    @classmethod
    def list_kbs(cls):
        return kb_list(None)

    def exists(self, kb_name: str = None):
        kb_name = kb_name or self.kb_name
        return kb_exists(kb_name)

    @abstractmethod
    def vs_type(self) -> str:
        pass

    @abstractmethod
    def do_init(self):
        pass

    @abstractmethod
    def do_drop_kb(self):
        """
        删除知识库子类实自己逻辑
        """
        pass

    @abstractmethod
    def do_search(self,
                  query: str,
                  top_k: int,
                  score_threshold: float,
                  ) -> List[Document]:
        """
        搜索知识库子类实自己逻辑
        """
        pass

    @abstractmethod
    def do_add_doc(self,
                   docs: List[Document],
                   ) -> List[Dict]:
        """
        向知识库添加文档子类实自己逻辑
        """
        pass

    @abstractmethod
    def do_add_qa(self,
                   docs: List[Document],
                   ) -> List[Dict]:
        """
        向知识库添加问答对子类实自己逻辑
        """
        pass
    
    @abstractmethod
    def do_delete_doc(self,
                      kb_file: KnowledgeFile):
        """
        从知识库删除文档子类实自己逻辑
        """
        pass

    @abstractmethod
    def do_clear_vs(self):
        """
        从知识库删除全部向量子类实自己逻辑
        """
        pass

    @abstractmethod
    def update_doc_by_id_embedding(self,
                                   id: str,
                                   block:dict):
        """
        更新向量库
        """
        pass
    
    @abstractmethod
    def do_delete_vs_by_source(self,
                      source: str):
        """
        通过source从向量库删除
        """
        pass

    @abstractmethod
    def do_delete_vs_by_feedback_id(self,
                      feedback_id: int):
        """
        通过feedback_id从向量库删除
        """
        pass

class KBServiceFactory:

    @staticmethod
    def get_service(kb_name: str,
                    vector_store_type: Union[str, SupportedVSType],
                    embed_model: str = EMBEDDING_MODEL,
                    ) -> KBService:
        if isinstance(vector_store_type, str):
            vector_store_type = getattr(SupportedVSType, vector_store_type.upper())
        if SupportedVSType.FAISS == vector_store_type:
            from server.knowledge_base.kb_service.faiss_kb_service import FaissKBService
            return FaissKBService(kb_name, embed_model=embed_model)
        elif SupportedVSType.PG == vector_store_type:
            from server.knowledge_base.kb_service.pg_kb_service import PGKBService
            return PGKBService(kb_name, embed_model=embed_model)
        elif SupportedVSType.MILVUS == vector_store_type:
            from server.knowledge_base.kb_service.milvus_kb_service import MilvusKBService
            return MilvusKBService(kb_name,embed_model=embed_model)
        elif SupportedVSType.ZILLIZ == vector_store_type:
            from server.knowledge_base.kb_service.zilliz_kb_service import ZillizKBService
            return ZillizKBService(kb_name, embed_model=embed_model)
        elif SupportedVSType.DEFAULT == vector_store_type:
            return MilvusKBService(kb_name,
                                   embed_model=embed_model)  # other milvus parameters are set in model_config.kbs_config
        elif SupportedVSType.ES == vector_store_type:
            from server.knowledge_base.kb_service.es_kb_service import ESKBService
            return ESKBService(kb_name, embed_model=embed_model)
        elif SupportedVSType.DEFAULT == vector_store_type:  # kb_exists of default kbservice is False, to make validation easier.
            from server.knowledge_base.kb_service.default_kb_service import DefaultKBService
            return DefaultKBService(kb_name)

    @staticmethod
    def get_service_by_name(kb_name: str) -> KBService:
        _, vs_type, embed_model = load_kb_from_db(kb_name)
        if _ is None:  # kb not in db, just return None
            return None
        return KBServiceFactory.get_service(kb_name, vs_type, embed_model)

    @staticmethod
    def get_service_by_id(kb_id: list) -> KBService:
        kb_name, vs_type, embed_model = load_kb_from_db_id(kb_id)
        if kb_name is None:  # kb not in db, just return None
            return None
        return KBServiceFactory.get_service(kb_name, vs_type, embed_model)

    @staticmethod
    def get_default():
        return KBServiceFactory.get_service("default", SupportedVSType.DEFAULT)


def get_kb_details() -> List[Dict]:
    kbs_in_folder = list_kbs_from_folder()
    kbs_in_db = KBService.list_kbs()
    result = {}

    for kb in kbs_in_folder:
        result[kb] = {
            "kb_name": kb,
            "vs_type": "",
            "kb_info": "",
            "embed_model": "",
            "file_count": 0,
            "create_time": None,
            "in_folder": True,
            "in_db": False,
        }

    for kb in kbs_in_db:
        kb_detail = get_kb_detail(kb)
        if kb_detail:
            kb_detail["in_db"] = True
            if kb in result:
                result[kb].update(kb_detail)
            else:
                kb_detail["in_folder"] = False
                result[kb] = kb_detail

    data = []
    for i, v in enumerate(result.values()):
        v['No'] = i + 1
        data.append(v)

    return data


def get_kb_file_details(kb_name: str) -> List[Dict]:
    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return []

    files_in_folder = list_files_from_folder(kb_name)
    files_in_db = kb.list_files()
    result = {}

    for doc in files_in_folder:
        result[doc] = {
            "kb_name": kb_name,
            "file_name": doc,
            "file_ext": os.path.splitext(doc)[-1],
            "file_version": 0,
            "document_loader": "",
            "docs_count": 0,
            "text_splitter": "",
            "create_time": None,
            "in_folder": True,
            "in_db": False,
        }
    for doc in files_in_db:
        doc_detail = get_file_detail(kb_name, doc)
        if doc_detail:
            doc_detail["in_db"] = True
            if doc in result:
                result[doc].update(doc_detail)
            else:
                doc_detail["in_folder"] = False
                result[doc] = doc_detail

    data = []
    for i, v in enumerate(result.values()):
        v['No'] = i + 1
        data.append(v)

    return data


class EmbeddingsFunAdapter(Embeddings):
    def __init__(self, embed_model: str = EMBEDDING_MODEL):
        self.embed_model = embed_model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = embed_texts(texts=texts, embed_model=self.embed_model, to_query=False).data
        return normalize(embeddings).tolist()

    def embed_query(self, text: str) -> List[float]:
        embeddings = embed_texts(texts=[text], embed_model=self.embed_model, to_query=True).data
        query_embed = embeddings[0]
        query_embed_2d = np.reshape(query_embed, (1, -1))  # 将一维数组转换为二维数组
        normalized_query_embed = normalize(query_embed_2d)
        return normalized_query_embed[0].tolist()  # 将结果转换为一维数组并返回

    # TODO: 暂不支持异步
    # async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
    #     return normalize(await self.embeddings.aembed_documents(texts))

    # async def aembed_query(self, text: str) -> List[float]:
    #     return normalize(await self.embeddings.aembed_query(text))


def score_threshold_process(score_threshold, k, docs):
    if score_threshold is not None:
        cmp = (
            operator.le
        )
        docs = [
            (doc, similarity)
            for doc, similarity in docs
            if cmp(similarity, score_threshold)
        ]
    return docs[:k]


