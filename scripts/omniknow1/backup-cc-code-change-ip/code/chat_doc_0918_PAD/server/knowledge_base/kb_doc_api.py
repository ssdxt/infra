import os
import urllib
from fastapi import File, Form, Body, Query, UploadFile
from configs import (DEFAULT_VS_TYPE, EMBEDDING_MODEL,
                     VECTOR_SEARCH_TOP_K, SCORE_THRESHOLD,
                     CHUNK_SIZE, OVERLAP_SIZE, ZH_TITLE_ENHANCE,
                     logger, log_verbose,RERANK_MODEL_SERVER)
from server.utils import BaseResponse, ListResponse, ListDictResponse,run_in_thread_pool
from server.knowledge_base.utils import (validate_kb_name, list_files_from_folder, get_file_path,get_doc_thumbnail_path,
                                         files2docs_in_thread, get_vsdb_path,KnowledgeFile)
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Json
import json
from server.knowledge_base.kb_service.base import KBServiceFactory
from server.db.repository.knowledge_file_repository import get_file_detail,configs_update_to_db,get_docs_detail
from typing import List,Optional,Dict,Any
from langchain.docstore.document import Document

from server.knowledge_base.update_embedding import update_vdb
from server.knowledge_base.word2pdf import doc2pdf
from pathlib import Path
import shutil
from urllib.parse import urlencode
from pydantic import BaseModel
import multiprocessing
from server.chat.utils import History,source_type_from_url
from server.http_api.user_api import token_check
from fastapi import Depends
import numpy
import numpy as np
from server.embeddings_api import embed_texts
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from embeddings.xinference.rerank_model import VllmRerank

rerank = VllmRerank(key=RERANK_MODEL_SERVER["api_key"], model_name=RERANK_MODEL_SERVER["model_name"], base_url=RERANK_MODEL_SERVER["base_url"])


class DocumentWithScore(Document):
    score: float = None

def embedding_distance(feature_1, feature_2):
    dist = np.linalg.norm(feature_1 - feature_2)
    return dist

def l2_score(query_list,context_list):

    query_embedding = embed_texts(query_list).data[0]
    context_embedding = embed_texts(context_list).data[0]

    # # 向量的值
    feature_1 = np.array(query_embedding)
    feature_2 = np.array(context_embedding)


    dis = embedding_distance(feature_1, feature_2)
    return round(dis,4)


"""
def search_feedback_docs(
        query: str = Body(..., description="用户输入", examples=["你好"]),
        kb_name: str = Body(..., description="知识库名称", examples=["samples"]),
        feedback_source_id: str = Body(..., description="反馈源ID"),
        top_k: int = Body(VECTOR_SEARCH_TOP_K, description="匹配向量数"),
        score_threshold: float = Body(SCORE_THRESHOLD,
                                      description="知识库匹配相关度阈值，取值范围在0-1之间，"
                                                  "SCORE越小，相关度越高，"
                                                  "取到1相当于不筛选，建议设置在0.5左右",
                                      ge=0),
        include_self: bool = Body(False, description="是否包含自身反馈记录")
) -> BaseResponse:
    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=200, msg="获取成功", data=[])
    
    docs = kb.search_docs(query, top_k * 2, score_threshold)  # 获取更多结果用于筛选
    
    # 筛选包含 feedback_source_id 的文档
    feedback_docs = []
    for doc_score_pair in docs:
        doc = doc_score_pair[0]
        score = doc_score_pair[1]
        
        if "feedback_source_id" in doc.metadata:
            if not include_self and doc.metadata["feedback_source_id"] == feedback_source_id:
                continue
            feedback_docs.append((doc, score))
    
    feedback_docs = feedback_docs[:top_k]
    
    data = [DocumentWithScore(**x[0].dict(), score=x[1]) for x in feedback_docs]
    
    for d in data:
        metadata = d.metadata
        if "feedback_source_id" in metadata:
            metadata["is_feedback_doc"] = True
            continue
    
    return BaseResponse(code=200, msg="反馈文档检索成功", data=data)
"""
def search_feedback_docs(
        query: str = Body(..., description="用户输入", examples=["你好"]),
        kb_name: str = Body(..., description="知识库名称", examples=["samples"]),
        feedback_source_id: str = Body(..., description="反馈源ID"),
        top_k: int = Body(VECTOR_SEARCH_TOP_K, description="匹配向量数"),
        score_threshold: float = Body(SCORE_THRESHOLD,
                                      description="知识库匹配相关度阈值，取值范围在0-1之间，"
                                                  "SCORE越小，相关度越高，"
                                                  "取到1相当于不筛选，建议设置在0.5左右",
                                      ge=0),
        include_self: bool = Body(False, description="是否包含自身反馈记录")
) -> BaseResponse:
    """专门检索feedback"""
    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=200, msg="获取成功", data=[])

    docs = kb.search_docs(query, top_k * 2, score_threshold)  # 获取更多结果用于筛选

    # 统一规范化返回：支持 List[Document] 或 List[(Document, score)]
    if docs and isinstance(docs[0], Document):
        doc_score_pairs = [(doc, 0.0) for doc in docs]
    else:
        doc_score_pairs = docs or []

    # 筛选包含 feedback_source_id 的文档
    feedback_docs = []
    for doc, score in doc_score_pairs:
        if "feedback_source_id" in doc.metadata:
            if not include_self and doc.metadata["feedback_source_id"] == feedback_source_id:
                continue
            feedback_docs.append((doc, score))

    feedback_docs = feedback_docs[:top_k]

    data = [DocumentWithScore(**doc.dict(), score=float(score)) for doc, score in feedback_docs]

    for d in data:
        metadata = d.metadata
        if "feedback_source_id" in metadata:
            metadata["is_feedback_doc"] = True
            continue

    return BaseResponse(code=200, msg="反馈文档检索成功", data=data)


def search_docs(
        query: str = Body(..., description="用户输入", examples=["你好"]),
        kb_name: str = Body(..., description="知识库名称", examples=["samples"]),
        top_k: int = Body(VECTOR_SEARCH_TOP_K, description="匹配向量数"),
        score_threshold: float = Body(SCORE_THRESHOLD,
                                      description="知识库匹配相关度阈值，取值范围在0-1之间，"
                                                  "SCORE越小，相关度越高，"
                                                  "取到1相当于不筛选，建议设置在0.5左右",
                                      ge=0),
        hybird_search: bool = Body(True, description="混合检索")
) -> BaseResponse:
    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=200, msg="获取成功",data=[])
    docs = kb.search_docs(query, top_k, score_threshold)
    print('docs=====================================',docs)

    if docs and hybird_search:
        bm_docs = kb.do_bm_search(query, top_k, kb_name)
        # print('bm==============================',bm_docs)
        # bm_docs = [(i,0.00) for i in bm_docs]
        bm_docs = [(i, l2_score([query],[i.page_content])) for i in bm_docs]

        docs.extend(bm_docs)
        print("888888----------bm--------8888",docs)
    
    data = [DocumentWithScore(**x[0].dict(), score=x[1]) for x in docs]


    # print('data before==============================',data)
    for d in data:
        metadata = d.metadata
        if "feedback_source_id" in metadata:
            continue
        if "source" in metadata:
            source = metadata["source"]
            source_type = metadata.get("source_type",None)
            # print("metadata",metadata)
            if source_type =="html":
                # metadata["url"] = metadata.get("url",None)
                pass
            else:
                
                _doc_filename=str(os.path.basename(source))
                _doc_url_request_parameters = urlencode({"knowledge_base_name": kb_name, "file_name":_doc_filename})
                _doc_url = f"knowledge_base/download_doc?" + _doc_url_request_parameters
                
                if source_type is None:
                    source_type = source_type_from_url(_doc_url)
                    metadata["source_type"] = source_type
                
                metadata["url"] = str(_doc_url)
                metadata["filename"] = str(_doc_filename)
                    
            _image_urls = []
            if "images_path" in metadata:
                for _image_local_path in metadata["images_path"]:
                    if len(_image_local_path):
                        _image_filename = os.path.basename(_image_local_path)
                        _image_url_request_parameters = urlencode({"filepath": _image_local_path, "filename":_image_filename})
                        _image_url = f"knowledge_base/download_img?" + _image_url_request_parameters
                    else:
                        _image_url =""
                    _image_urls.append(_image_url)
            metadata["images_url"]=_image_urls
    

    # print('data after==============================',data)

    # 去重
    temp = []
    
    docs = []
    for i in data:
        if i.page_content not in temp:
            temp.append(i.page_content)
            docs.append(i)


    # print('================ search_ new_docs =====================',docs)
    # docs = new_docs
    contexts = []
    for doc in docs:
        c = ""
        if 'keyword' in doc.metadata:
            c += " ".join(doc.metadata["keyword"])+"\n"
        if 'titles' in doc.metadata:
            c += doc.metadata["titles"]+"\n"
        c += doc.page_content+"\n\n"
        
        contexts.append(c)
        
    
    scores = rerank.similarity(query, contexts)

    # print('gagagagag_scores',scores)
    # print('gagagagag_docs',docs)
    docs = [doc for _, doc in sorted(zip(scores[0], docs), key=lambda x: x[0], reverse=True)]
    # print(docs)
    docs = docs[:top_k]
    # print(11111)
    # print(docs)


    # temp = []
    # docs = []
    # for i in data:
    #     if i.page_content not in temp:
    #         temp.append(i.page_content)
    #         docs.append(i)
        
    # pairs = []
    # # docs = data
    
    # for doc in docs:
    #     c = ""
    #     if 'keyword' in doc.metadata:
    #         c += " ".join(doc.metadata["keyword"])+"\n"
    #     if 'titles' in doc.metadata:
    #         c += doc.metadata["titles"]+"\n"
    #     c += doc.page_content+"\n\n"

    #     pairs.append([query,c])

    
    # # pairs = [list(t) for t in set(tuple(sublist) for sublist in pairs)]
    # if pairs and pairs[0]:
    #     with torch.no_grad():
    #         inputs = reranker_tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=512).to(reranker_model.device)
    #         scores = reranker_model(**inputs, return_dict=True).logits.view(-1, ).float()
    #         scores = scores.cpu().numpy()
            
    #         idxs = numpy.argsort(scores)
    #         idxs = idxs[::-1]
    #         # print('--------------------------------',scores,idxs)
    #         doc_temp = []
    #         for _idx in idxs:
    #             doc_temp.append(docs[_idx])
    #             if len(doc_temp)>=top_k:
    #                 break
    #         docs = doc_temp

    return BaseResponse(code=200, msg="获取成功",data=docs)

def search_docs_by_id(
        query: str = Body(..., description="用户输入", examples=["你好"]),
        kb_id: int = Body(..., description="知识库id", examples=["samples"]),
        top_k: int = Body(VECTOR_SEARCH_TOP_K, description="匹配向量数"),
        score_threshold: float = Body(SCORE_THRESHOLD,
                                      description="知识库匹配相关度阈值，取值范围在0-1之间，"
                                                  "SCORE越小，相关度越高，"
                                                  "取到1相当于不筛选，建议设置在0.5左右",
                                      ge=0, le=2),
) -> BaseResponse:
        
    kb = KBServiceFactory.get_service_by_id(kb_id)
    if kb is None:
        return BaseResponse(code=200, msg="获取成功",data=[])
    docs = kb.search_docs(query, top_k, score_threshold)
    data = [DocumentWithScore(**x[0].dict(), score=x[1]) for x in docs]

    for d in data:
        metadata = d.metadata
        if metadata:
            source = metadata["source"]
            if source:
                if str(source).startswith("http"):
                    metadata["url"] = str(source)
                else:
                    _doc_filename=str(os.path.basename(source))
                    _doc_url_request_parameters = urlencode({"knowledge_base_id": kb_id, "file_name":_doc_filename})
                    _doc_url = f"knowledge_base/download_doc?" + _doc_url_request_parameters
                    metadata["url"] = str(_doc_url)
                    metadata["filename"] = str(_doc_filename)
                
            _image_urls = []
            for _image_local_path in metadata["images_path"]:
                if len(_image_local_path):
                    _image_filename = os.path.basename(_image_local_path)
                    _image_url_request_parameters = urlencode({"filepath": _image_local_path, "filename":_image_filename})
                    _image_url = f"knowledge_base/download_img?" + _image_url_request_parameters
                else:
                    _image_url =""
                _image_urls.append(_image_url)
            metadata["images_url"]=_image_urls
        
    return BaseResponse(code=200, msg="获取成功",data=data)

class ListParams(BaseModel):
        kb_name:str
        file_name:str = None
        parse_status:str = None
        page_no:int = None
        page_size:int = None

def list_files(
        params:ListParams
) -> BaseResponse:
    if not validate_kb_name(params.kb_name):
        return BaseResponse(code=403, msg="Don't attack me")

    knowledge_base_name = urllib.parse.unquote(params.kb_name)
    
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if params.page_no and params.page_size:
        page_start = (params.page_no - 1) * params.page_size
        page_end = page_start + params.page_size
    else:
        page_start = None
        page_end = None
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {knowledge_base_name}")
    
    result = kb.list_files(file_name=params.file_name,parse_status=params.parse_status,page_start=page_start,page_end=page_end)
    files = result.get("data", {}).get("files", [])
    total_count = result.get("data", {}).get("count", 0)

    return BaseResponse(code=200,msg="获取成功",data={"count": total_count,"files": files})

def list_files_self(
        params:ListParams
) -> BaseResponse:
    if not validate_kb_name(params.kb_name):
        return BaseResponse(code=400, msg="Don't attack me")

    knowledge_base_name = urllib.parse.unquote(params.kb_name)
    
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    page_start = (params.page_no - 1) * params.page_size
    page_end = page_start + params.page_size
    if kb is None:
        return BaseResponse(code=400, msg=f"未找到知识库 {knowledge_base_name}")
    else:
        all_doc_names = kb.list_files(file_name=params.file_name,parse_status=params.parse_status,page_start=page_start,page_end=page_end)

        return BaseResponse(code=200, msg="获取成功",data={"files":all_doc_names})

class DetailParams(BaseModel):
        kb_name:str
        file_name:str

def detail_file(params:DetailParams):
    db_obj = get_file_detail(kb_name=params.kb_name,file_name=params.file_name)
    return {"code":0,"msg":"成功","data":db_obj}

def _save_files_in_thread(files: List[UploadFile],
                          knowledge_base_name: str,
                          override: bool):
    """
    通过多线程将上传的文件保存到对应知识库目录内。
    生成器返回保存结果：{"code":200, "msg": "xxx", "data": {"knowledge_base_name":"xxx", "file_name": "xxx"}}
    """

    def save_file(file: UploadFile, knowledge_base_name: str, override: bool) -> dict:
        '''
        保存单个文件。
        '''
        try:
            filename = file.filename
            file_search_name = filename
            file_path = get_file_path(knowledge_base_name=knowledge_base_name, doc_name=file_search_name)
            data = {"knowledge_base_name": knowledge_base_name, "file_name": filename}
            file_content = file.file.read()  # 读取上传文件的内容
            if (os.path.isfile(file_path)
                    and not override
                    and os.path.getsize(file_path) == len(file_content)
            ):
                # TODO: filesize 不同后的处理
                file_status = f"文件 {filename} 已存在。"
                logger.warn(file_status)
                return dict(code=404, msg=file_status, data=data)

            with open(file_path, "wb") as f:
                f.write(file_content)
            return dict(code=200, msg=f"成功上传文件 {filename}", data=data)
        except Exception as e:
            msg = f"{filename} 文件上传失败，报错信息为: {e}"
            logger.error(f'{e.__class__.__name__}: {msg}',
                         exc_info=e if log_verbose else None)
            return dict(code=500, msg=msg, data=data)

    params = [{"file": file, "knowledge_base_name": knowledge_base_name, "override": override} for file in files]
    for result in run_in_thread_pool(save_file, params=params):
        yield result
        
        
def _save_thumbnail_in_thread(files: List[UploadFile],
                          knowledge_base_name: str,
                          doc_files: List[UploadFile],
                          override: bool):
    """
    通过多线程将缩略图上传。
    生成器返回保存结果：{"code":200, "msg": "xxx", "data": {"knowledge_base_name":"xxx", "file_name": "xxx"}}
    """

    def save_file(file: UploadFile, knowledge_base_name: str,doc_file_name:str, override: bool) -> dict:
        '''
        保存单个文件。
        '''
        try:
            if file is None:
                return dict(code=200, msg=f"文件不存在", data={})
            filename = file.filename
            file_path = get_doc_thumbnail_path(knowledge_base_name=knowledge_base_name, doc_name=doc_file_name)
            parent_dir = os.path.dirname(file_path)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir)
            data = {"knowledge_base_name": knowledge_base_name, "filename":filename}
            file_content = file.file.read()  # 读取上传文件的内容
            if (os.path.isfile(file_path)
                    and not override
                    and os.path.getsize(file_path) == len(file_content)
            ):
                # TODO: filesize 不同后的处理
                file_status = f"文件 {filename} 已存在。"
                logger.warn(file_status)
                return dict(code=404, msg=file_status, data=data)

            with open(file_path, "wb") as f:
                f.write(file_content)
            return dict(code=200, msg=f"成功上传文件 {filename}", data=data)
        except Exception as e:
            msg = f"{filename} 文件上传失败，报错信息为: {e}"
            logger.error(f'{e.__class__.__name__}: {msg}',
                         exc_info=e if log_verbose else None)
            return dict(code=500, msg=msg, data={})

    params = [{"file": file, "knowledge_base_name": knowledge_base_name,"doc_file_name":doc_files[idx].filename, "override": override} for idx,file in enumerate(files)]
    for result in run_in_thread_pool(save_file, params=params):
        yield result

from pdf2image import convert_from_path
import cv2

def _save_page1_in_thread(files: List[UploadFile],
                        knowledge_base_name: str,
                        override: bool):
    """
    多线程提取文件首页并保存。
    """

    def save_file(file: UploadFile, knowledge_base_name: str, override: bool) -> dict:
        '''
        提取文件首页作为缩略图并保存。
        '''
        try:
            filename = file.filename
            # 原始上传文件路径（可能是 doc/docx 或 pdf）
            orig_file_path = get_file_path(knowledge_base_name=knowledge_base_name, doc_name=filename)

            if not os.path.exists(orig_file_path):
                return dict(code=404, msg=f"文件 {filename} 不存在", data={})

            # 规范化：如果是 doc/docx，则指向转换后的 pdf 文件；并按 pdf 文件名生成缩略图
            lower_ext = os.path.splitext(filename)[1].lower()
            if lower_ext in [".doc", ".docx"]:
                pdf_filename = filename.rsplit(".", 1)[0] + ".pdf"
                file_path = get_file_path(knowledge_base_name=knowledge_base_name, doc_name=pdf_filename)
                target_thumb_name = pdf_filename
            elif lower_ext == ".pdf":
                file_path = orig_file_path
                target_thumb_name = filename
            else:
                return dict(code=500, msg=f"文件 {filename} 格式不支持提取缩略图", data={})

            if not os.path.exists(file_path):
                return dict(code=404, msg=f"转换后的文件不存在：{os.path.basename(file_path)}", data={})

            thumbnail_path = get_doc_thumbnail_path(knowledge_base_name=knowledge_base_name, doc_name=target_thumb_name)

            # 提取第一页
            pages = convert_from_path(file_path, dpi=200, first_page=1, last_page=1)
            if pages:
                first_page_image = pages[0]
                # 如果目标路径目录不存在，则创建
                parent_dir = os.path.dirname(thumbnail_path)
                if not os.path.exists(parent_dir):
                    os.makedirs(parent_dir)

                # 如果已经存在缩略图并且不允许覆盖
                if os.path.isfile(thumbnail_path) and not override:
                    file_status = f"缩略图 {os.path.basename(thumbnail_path)} 已存在。"
                    return dict(code=404, msg=file_status, data={})

                # 保存缩略图
                first_page_image.save(thumbnail_path, 'JPEG')
                return dict(
                    code=200,
                    msg=f"成功提取 {os.path.basename(file_path)} 的首页并保存为缩略图",
                    data={"knowledge_base_name": knowledge_base_name, "file_name": os.path.basename(file_path)}
                )
            else:
                return dict(code=500, msg=f"无法提取 {os.path.basename(file_path)} 的首页", data={})
        except Exception as e:
            msg = f"{filename} 文件处理失败，报错信息为: {e}"
            return dict(code=500, msg=msg, data={})

    # 逐个文件处理，调用多线程保存首页缩略图
    params = [{"file": file, "knowledge_base_name": knowledge_base_name, "override": override} for file in files]
    for result in run_in_thread_pool(save_file, params=params):
        yield result

# 似乎没有单独增加一个文件上传API接口的必要
# def upload_files(files: List[UploadFile] = File(..., description="上传文件，支持多文件"),
#                 knowledge_base_name: str = Form(..., description="知识库名称", examples=["samples"]),
#                 override: bool = Form(False, description="覆盖已有文件")):
#     '''
#     API接口：上传文件。流式返回保存结果：{"code":200, "msg": "xxx", "data": {"knowledge_base_name":"xxx", "file_name": "xxx"}}
#     '''
#     def generate(files, knowledge_base_name, override):
#         for result in _save_files_in_thread(files, knowledge_base_name=knowledge_base_name, override=override):
#             yield json.dumps(result, ensure_ascii=False)

#     return StreamingResponse(generate(files, knowledge_base_name=knowledge_base_name, override=override), media_type="text/event-stream")


# TODO: 等langchain.document_loaders支持内存文件的时候再开通
# def files2docs(files: List[UploadFile] = File(..., description="上传文件，支持多文件"),
#                 knowledge_base_name: str = Form(..., description="知识库名称", examples=["samples"]),
#                 override: bool = Form(False, description="覆盖已有文件"),
#                 save: bool = Form(True, description="是否将文件保存到知识库目录")):
#     def save_files(files, knowledge_base_name, override):
#         for result in _save_files_in_thread(files, knowledge_base_name=knowledge_base_name, override=override):
#             yield json.dumps(result, ensure_ascii=False)

#     def files_to_docs(files):
#         for result in files2docs_in_thread(files):
#             yield json.dumps(result, ensure_ascii=False)

from fastapi import Form, File, UploadFile, HTTPException
from typing import List
import requests
from io import BytesIO
from starlette.datastructures import Headers

def upload_docs_by_path(
                    file_url: str = Form(..., description="文件路径"),
                    kb_name: str = Form(..., description="知识库名称", examples=["samples"]),
                    override: bool = Form(False, description="覆盖已有文件"),
                    use_page1_as_thumbnail: bool = Form(True, description="提取文件首页作为封面"),
                    docs: Json = Form({}, description="自定义的docs，需要转为json字符串",
                                    examples=[{"test.txt": [Document(page_content="custom doc")]}]),
                    thumbnail_files: Optional[List[UploadFile]] = File([None], description="上传的缩略图，支持多文件"),
                    user_dict= Depends(token_check)):

    try:
        response = requests.get(file_url)
        response.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"文件下载失败: {str(e)}")

    file_content = BytesIO(response.content)

    temp_file = UploadFile(
        file=file_content,
        filename=file_url.split("/")[-1],
        headers=Headers({"content-type": response.headers.get("content-type")}),
    )

    response = upload_docs(
        files=[temp_file],
        kb_name=kb_name,
        override=override,
        docs=docs,
        use_page1_as_thumbnail=use_page1_as_thumbnail,
        thumbnail_files=thumbnail_files
    )

    return response

from server.db.repository.knowledge_file_repository import add_file_to_db
from server.knowledge_base.pptx2pdf import pptx2pdf

def upload_docs(
        files: List[UploadFile] = File(..., description="上传文件，支持多文件"),
        kb_name: str = Form(..., description="知识库名称", examples=["samples"]),
        override: bool = Form(False, description="覆盖已有文件"),
        docs: Json = Form({}, description="自定义的docs，需要转为json字符串",
                          examples=[{"test.txt": [Document(page_content="custom doc")]}]),
        use_page1_as_thumbnail: bool = Form(True, description="提取文件首页作为封面"),
        thumbnail_files: Optional[List[UploadFile]] = File([None], description="上传的缩略图，支持多文件"),
        user_dict= Depends(token_check)
) -> BaseResponse:
    """
    API接口:上传文件
    
    """
    if not validate_kb_name(kb_name):
        return BaseResponse(code=403, msg="Don't attack me")

    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {kb_name}")

    failed_files = {}
    file_names = list(docs.keys())

    # 先将上传的文件保存到磁盘
    for result in _save_files_in_thread(files, knowledge_base_name=kb_name, override=override):
        filename = result["data"]["file_name"]
        if result["code"] != 200:
            failed_files[filename] = result["msg"]

        if filename not in file_names:
            file_names.append(filename)
            
    for index, filename in enumerate(file_names):
        if filename[-5:] == ".docx" or filename[-4:] == ".doc":
            file_path = get_file_path(knowledge_base_name=kb_name, doc_name=filename)
            try:
                doc2pdf(file_path)
            
                # 原始文件先不删除，留着cache判断用
                # os.remove(file_path)
                if filename[-5:] == ".docx": 
                    filename = filename[:-5] + ".pdf"
                else:
                    filename = filename[:-4] + ".pdf"
                file_names[index] = filename

            except Exception as e:
                failed_files[filename] = f"文档转换失败: {str(e)}"
                file_names[index] = None
                continue
    
    file_names = [name for name in file_names if name is not None]
        # if filename[-5:] == ".pptx":
        #     file_path = get_file_path(knowledge_base_name=kb_name, doc_name=filename)
        #     pptx2pdf(file_path)
        #     filename = filename[:-5] + ".pdf"

    if use_page1_as_thumbnail:
        for result in _save_page1_in_thread(files, knowledge_base_name=kb_name, override=override):
            pass
    # 否则使用上传的缩略图
    elif thumbnail_files and len(thumbnail_files) > 0:
        for result in _save_thumbnail_in_thread(thumbnail_files, knowledge_base_name=kb_name, doc_files=files, override=override):
            pass
    for filename in file_names:
        try:
            kb_file = KnowledgeFile(filename=filename,knowledge_base_name=kb_name)
            add_file_to_db(kb_file)
        except ValueError as e:
            failed_files[filename] = f"添加到数据库失败: {str(e)}"
            continue
        except Exception as e:
            failed_files[filename] = f"处理文件时出错: {str(e)}"
            continue
    return BaseResponse(code=200, msg="文件上传完成", data={"failed_files": failed_files})

from server.db.repository.knowledge_file_repository import delete_tc_by_kbfile,delete_tc_by_vs

def delete_docs(
        kb_name: str = Body(..., examples=["samples"]),
        file_names: List[str] = Body(..., examples=[["file_name.md", "test.txt"]]),
        delete_content: bool = Body(True),
        not_refresh_vs_cache: bool = Body(False, description="暂不保存向量库（用于FAISS）"),
) -> BaseResponse:
    if not validate_kb_name(kb_name):
        return BaseResponse(code=403, msg="Don't attack me")

    knowledge_base_name = urllib.parse.unquote(kb_name)
    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {knowledge_base_name}")

    failed_files = {}
    for file_name in file_names:
        if not kb.exist_doc(file_name):
            failed_files[file_name] = f"未找到文件 {file_name}"

        try:
            delete_tc_by_kbfile(kb_name,file_name)
            kb_file = KnowledgeFile(filename=file_name,
                                    knowledge_base_name=knowledge_base_name)
            
            # MOD BY LIUBIN 删除图片文件夹 
            filename = str(os.path.basename(kb_file.filepath))
            last_dot_index = filename.rfind(".")
            filename = filename[:last_dot_index]
            
            image_save_dir = str(Path(kb_file.filepath).parent.parent)+"/image/"+filename
            if os.path.exists(image_save_dir):
                shutil.rmtree(image_save_dir)
                            
            kb.delete_doc(kb_file, delete_content, not_refresh_vs_cache=not_refresh_vs_cache)
                       
        except Exception as e:
            msg = f"{file_name} 文件删除失败，错误信息：{e}"
            logger.error(f'{e.__class__.__name__}: {msg}',
                         exc_info=e if log_verbose else None)
            failed_files[file_name] = msg

    if not not_refresh_vs_cache:
        kb.save_vector_store()

    return BaseResponse(code=200, msg=f"文件删除完成", data={"failed_files": failed_files})


def update_info(
        kb_name: str = Body(..., description="知识库名称", examples=["samples"]),
        kb_info: str = Body(..., description="知识库介绍", examples=["这是一个知识库"]),
):
    if not validate_kb_name(kb_name):
        return BaseResponse(code=403, msg="Don't attack me")

    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {kb_name}")
    kb.update_info(kb_info)

    return BaseResponse(code=200, msg=f"知识库介绍修改完成", data={"kb_info": kb_info})

from server.db.repository.knowledge_file_repository import update_parse_status,update_parsed_file_to_db,get_parsed_docs_from_db,parse_content,add_parsed_file_to_db
from server.db.repository.knowledge_base_repository import kb_update

def parse_docs(
        kb_name: str = Body(..., description="知识库名称", examples=["samples"]),
        file_names: List[str] = Body(..., description="文件名称，支持多文件", examples=[["file_name1", "text.txt"]]),
        chunk_size: int = Body(CHUNK_SIZE, description="知识库中单段文本最大长度"),
        chunk_overlap: int = Body(OVERLAP_SIZE, description="知识库中相邻文本重合长度"),
        zh_title_enhance: bool = Body(ZH_TITLE_ENHANCE, description="是否开启中文标题加强"),
        override_custom_docs: bool = Body(False, description="是否覆盖之前自定义的docs"),
        docs: Json = Body({}, description="自定义的docs，需要转为json字符串",
                          examples=[{"test.txt": [Document(page_content="custom doc")]}])
) -> BaseResponse:
    """
    更新知识库文档 - 支持批量处理
    """
    # 预处理文件名：将Word文档转换为PDF格式
    for i in range(len(file_names)):
        if file_names[i].lower().endswith(('.doc', '.docx')):
            file_names[i] = file_names[i].rsplit('.', 1)[0] + '.pdf'

    if not validate_kb_name(kb_name):
        return BaseResponse(code=403, msg="知识库名称无效")

    # 获取知识库服务
    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {kb_name}")

    failed_files = {}
    kb_files = []
    processed_files = []  # 记录成功处理的文件
    audio_video_files = []  # 记录音频视频文件

    # 为所有文件设置解析状态
    for file_name in file_names:
        update_parse_status(kb_name, file_name, "解析中")

    # 第一阶段：处理音频和视频文件
    for file_name in file_names:
        file_detail = get_file_detail(kb_name=kb_name, file_name=file_name)
        file_ext = file_detail.get("file_ext")

        if file_ext in [".wav", ".mp4" ,".mp3"]:
            audio_video_files.append(file_name)
            file_path = get_file_path(kb_name, file_name)
            relative_path = os.path.relpath(file_path)
            
            if not os.path.exists(file_path):
                failed_files[file_name] = "文档不存在"
                update_parse_status(kb_name, file_name, "失败")
                continue
            
            # if file_ext == ".wav":
            #     url = "https://0.0.0.0:8362/wav_asr_vad"
            # elif file_ext == ".mp4":
            url = "http://0.0.0.0:8362/wav_asr_vad"

            try:
                with open(file_path, "rb") as file:
                    files = {"file": (file_name, file, "application/octet-stream")}
                    response = requests.post(url, files=files, verify=False)
                    datas = response.json()
                    chunks = parse_content(datas, 2000, relative_path)

                    documents = []
                    for chunk in chunks:
                        page_content = chunk.get("page_content")
                        meta_data = chunk.get("meta_data")

                        document = Document(
                            page_content=page_content,
                            metadata={
                                "source": meta_data.get("source"),
                                "start": meta_data.get("start"),
                                "end": meta_data.get("end"),
                                "titles": "音频"
                            }
                        )
                        documents.append(document)
                    
                    add_parsed_file_to_db(kb_name, file_name, documents)
                    
                    # 立即对该文件进行向量化处理，并保存向量库
                    try:
                        vectorize_docs(kb_name=kb_name, file_names=[file_name], docs={}, not_refresh_vs_cache=False)
                        processed_files.append(file_name)
                    except Exception as e:
                        logger.error(f"音频/视频文件向量化处理失败: {e}")
                        failed_files[file_name] = f"向量化失败: {str(e)}"
                        update_parse_status(kb_name, file_name, "失败")
                    
            except Exception as e:
                failed_files[file_name] = f"文件处理失败: {str(e)}"
                update_parse_status(kb_name, file_name, "失败")
                continue

    # 第二阶段：处理普通文档文件
    for file_name in file_names:
        if file_name in audio_video_files:
            continue  # 跳过已处理的音频视频文件
            
        file_detail = get_file_detail(kb_name=kb_name, file_name=file_name)
        
        # 如果该文件之前使用了自定义docs，则根据参数决定略过或覆盖
        if file_detail.get("custom_docs") and not override_custom_docs:
            continue
            
        if file_name not in docs:
            try:
                kb_files.append(KnowledgeFile(filename=file_name, knowledge_base_name=kb_name))
            except Exception as e:
                msg = f"加载文档 {file_name} 时出错：{e}"
                logger.error(f'{e.__class__.__name__}: {msg}',
                             exc_info=e if log_verbose else None)
                failed_files[file_name] = msg
                update_parse_status(kb_name, file_name, "失败")

    # 第三阶段：批量处理普通文档
    if kb_files:
        for status, result in files2docs_in_thread(kb_files,
                                                   chunk_size=chunk_size,
                                                   chunk_overlap=chunk_overlap, 
                                                   zh_title_enhance=zh_title_enhance):

            if status:
                kb_name_result, file_name, new_docs = result
                kb_file = KnowledgeFile(filename=file_name, knowledge_base_name=kb_name)
                kb_file.splited_docs = new_docs
                
                if len(kb_file.splited_docs) == 0:
                    failed_files[file_name] = "文档解析信息为空"
                    update_parse_status(kb_name, file_name, "失败")
                    continue
                    
                try:
                    update_parsed_file_to_db(kb_file)
                    
                    # 立即对该文件进行向量化处理，并保存向量库
                    try:
                        vectorize_docs(kb_name=kb_name, file_names=[file_name], docs={}, not_refresh_vs_cache=False)
                        processed_files.append(file_name)
                    except Exception as e:
                        logger.error(f"文档向量化处理失败: {e}")
                        failed_files[file_name] = f"向量化失败: {str(e)}"
                        update_parse_status(kb_name, file_name, "失败")
                        
                except Exception as e:
                    failed_files[file_name] = f"更新数据库时出错：{e}"
                    update_parse_status(kb_name, file_name, "失败")
            else:
                kb_name_result, file_name, error = result
                failed_files[file_name] = error
                update_parse_status(kb_name, file_name, "失败")

    # 处理自定义docs
    for file_name, v in docs.items():
        try:
            v = [x if isinstance(x, Document) else Document(**x) for x in v]
            # 立即对自定义docs进行向量化处理，并保存向量库
            try:
                vectorize_docs(kb_name=kb_name, file_names=[], docs={file_name: v}, not_refresh_vs_cache=False)
                processed_files.append(file_name)
            except Exception as e:
                logger.error(f"自定义docs向量化处理失败: {e}")
                failed_files[file_name] = f"向量化失败: {str(e)}"
                update_parse_status(kb_name, file_name, "失败")
        except Exception as e:
            msg = f"处理自定义docs {file_name} 时出错：{e}"
            logger.error(f'{e.__class__.__name__}: {msg}',
                        exc_info=e if log_verbose else None)
            failed_files[file_name] = msg
            update_parse_status(kb_name, file_name, "失败")

    # 返回处理结果
    if failed_files:
        if processed_files:
            return BaseResponse(
                code=200, 
                msg=f"部分文档解析完成，成功: {len(processed_files)}个，失败: {len(failed_files)}个", 
                data={"failed_files": failed_files, "processed_files": processed_files}
            )
        else:
            return BaseResponse(
                code=500, 
                msg="所有文档解析失败", 
                data={"failed_files": failed_files}
            )
    else:
        return BaseResponse(
            code=200, 
            msg=f"所有文档解析完成，共处理 {len(processed_files)} 个文件", 
            data={"processed_files": processed_files}
        )

def vectorize_docs(
        kb_name: str = Body(..., description="知识库名称", examples=["samples"]),
        file_names: List[str] = Body(..., description="文件名称，支持多文件", examples=[["file_name1", "text.txt"]]),
        docs: Json = Body({}, description="自定义的docs，需要转为json字符串",
                          examples=[{"test.txt": [Document(page_content="custom doc")]}]),
        not_refresh_vs_cache: bool = Body(False, description="暂不保存向量库（用于FAISS）")
) -> BaseResponse:
    """
    将解析后的文档进行向量化，并将结果存储到数据库
    """
    if not validate_kb_name(kb_name):
        return BaseResponse(code=403, msg="知识库名称无效")

    # 获取知识库服务
    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {kb_name}")

    failed_files = {}
    success_count = 0

    try:
        kb_update(kb_name=kb_name, activate="更新")

        # 处理普通文件的向量化
        for file_name in file_names:
            try:
                documents = get_parsed_docs_from_db(kb_name, file_name)
                
                # 检查文件是否已成功解析
                if not documents:
                    failed_files[file_name] = "文件未找到解析记录，可能解析失败或文件不存在"
                    update_parse_status(kb_name, file_name, "失败")
                    continue
                
                kb_file = KnowledgeFile(filename=file_name, knowledge_base_name=kb_name)
                kb_file.splited_docs = documents  
                
                # 向量化解析后的文档
                kb.update_doc(kb_file, not_refresh_vs_cache=not_refresh_vs_cache)
                success_count += 1
                update_parse_status(kb_name, file_name, "成功")

            except Exception as e:
                msg = f"为 {file_name} 进行向量化时出错：{e}"
                logger.error(f'{e.__class__.__name__}: {msg}',
                            exc_info=e if log_verbose else None)
                failed_files[file_name] = msg
                update_parse_status(kb_name, file_name, "失败")

        # 将自定义的docs进行向量化
        for file_name, v in docs.items():
            try:
                v = [x if isinstance(x, Document) else Document(**x) for x in v]
                kb_file = KnowledgeFile(filename=file_name, knowledge_base_name=kb_name)
                kb.update_doc(kb_file, docs=v, not_refresh_vs_cache=not_refresh_vs_cache)
                success_count += 1
                update_parse_status(kb_name, file_name, "成功")
            except Exception as e:
                msg = f"为 {file_name} 添加自定义docs时出错：{e}"
                logger.error(f'{e.__class__.__name__}: {msg}',
                            exc_info=e if log_verbose else None)
                failed_files[file_name] = msg
                update_parse_status(kb_name, file_name, "失败")
                
        # 保存向量存储（如果未禁用且有成功的文件）
        if not not_refresh_vs_cache and success_count > 0:
            kb.save_vector_store()

    except Exception as e:
        kb_update(kb_name=kb_name, activate="正常")
        msg = f"处理过程中发生错误：{e}"
        logger.error(f'{e.__class__.__name__}: {msg}', exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg, data={"failed_files": failed_files})

    finally:
        kb_update(kb_name=kb_name, activate="正常")

    # 根据处理结果返回相应的状态码和消息
    if failed_files and success_count == 0:
        return BaseResponse(code=400, msg="所有文件向量化失败", data={"failed_files": failed_files, "success_count": success_count})
    elif failed_files:
        return BaseResponse(code=200, msg=f"部分文件向量化成功，{success_count}个成功，{len(failed_files)}个失败", 
                          data={"failed_files": failed_files, "success_count": success_count})
    else:
        return BaseResponse(code=200, msg=f"文档向量化完成，共处理{success_count}个文件", 
                          data={"failed_files": failed_files, "success_count": success_count})
     

import base64
import re

#获取上传文件的配置信息
def get_update_docs_configs(
        kb_name: str = Body(..., description="知识库名称", examples=["samples"]),
        file_name: str = Body(..., description="文件名称", examples=["file_name"]),
) -> BaseResponse:
    """
    从数据库中获取文件的配置
    """
    if file_name.lower().endswith(('.doc', '.docx')):
        file_name = file_name.rsplit('.', 1)[0] + '.pdf'

    if not validate_kb_name(kb_name):
        return BaseResponse(code=400, msg="知识库名称无效")

    file_detail = get_file_detail(kb_name=kb_name, file_name=file_name)
    
    if not file_detail:
        return BaseResponse(code=400, msg=f" 在知识库{kb_name}中没有{file_name}文件")

    # 提取文件的解析配置
    file_parse_configs = file_detail.get("file_parse_configs")

    if not file_parse_configs:
        return BaseResponse(code=400, msg=f"文件{file_name}没有解析配置信息")
    
    #解码后格式
    separators_encoded = file_parse_configs.get("separators")
    if separators_encoded:
        try:
            decoded_separators = base64.b64decode(separators_encoded).decode('utf-8')

            try:
                separators_list = eval(decoded_separators)
            except Exception as e:
                return BaseResponse(code=500, msg=f"Error parsing configuration: {str(e)}")
        except Exception as e:
            return BaseResponse(code=500, msg=f"Error decoding 'separators': {str(e)}")
    else:
        return BaseResponse(code=400, msg="No 'separators' found in file_parse_configs")

    formatted_separators = []
    explanations = [
        "一级标题",
        "二级标题",
        "三级标题",
        "四级标题",
        "五级标题",
        "六级标题",
        "七级标题"
    ]

    for i, config_group in enumerate(separators_list):
        formatted_group = {
            "name": explanations[i],
            "list": []
        }
        for regex in config_group:
            if "第" in regex and "章" in regex:
                label = "第一章"
            elif "第" in regex and "节" in regex:
                label = "第一节"
            elif "附" in regex and "录" in regex:
                label = "附录"
            elif "参" in regex and "考" in regex and "文" in regex and "献" in regex:
                label = "参考文献"
            elif "附" in regex and "表" in regex:
                label = "附表"
            elif "\\d+(\\.\\d+){1}\\s" in regex:
                label = "1.1"
            elif "\\d+(\\.\\d+){2}\\s" in regex:
                label = "1.1.1"
            elif "\\d+(\\.\\d+){3}\\s" in regex:
                label = "1.1.1.1"
            elif "\\d+(\\.\\d+){4}\\s" in regex:
                label = "1.1.1.1.1"
            elif "\\d+\\s" in regex:
                label = "1"
            else:
                label = "Unknown"

            formatted_group["list"].append({
                "label": label,
                "value": regex
            })
        formatted_separators.append(formatted_group)

    file_parse_configs["separators"] = formatted_separators

    if file_parse_configs["image_save"] == 1:
        file_parse_configs["image_save"] = True
    elif file_parse_configs["image_save"] == 0:
        file_parse_configs["image_save"] = False

    if file_parse_configs["generate_query"] == 1:
        file_parse_configs["generate_query"] = True
    elif file_parse_configs["generate_query"] == 0:
        file_parse_configs["generate_query"] = False
        
    return BaseResponse(code=200, msg="文件解析配置提取成功", data={"file_parse_configs": file_parse_configs})

def update_configs_to_db(
        kb_name: str = Body(..., description="知识库名称", examples=["samples"]),
        file_name: str = Body(..., description="文件名称", examples=["file_name"]),
        file_parse_configs:Dict[str, Any]=Body(..., description="文档的setting文件，需要转为json字符串",examples={"page_start":0,"page_end":100,"catalogue_re":[],"image_save":True,"generate_question": False}),        
) -> BaseResponse:
    """
    更新数据库文件配置
    """
    if file_name.lower().endswith(('.doc', '.docx')):
        file_name = file_name.rsplit('.', 1)[0] + '.pdf'

    if not validate_kb_name(kb_name):
        return BaseResponse(code=400, msg="知识库名称无效")
    
    if "separators" in file_parse_configs and isinstance(file_parse_configs["separators"], list):
        # 将 separators 转换为简化的数组格式
        simplified_separators = []
        for separator_group in file_parse_configs["separators"]:
            group_values = [item["value"] for item in separator_group.get("list", [])]
            simplified_separators.append(group_values)
        # 转换为 JSON 并编码为 Base64
        simplified_json = json.dumps(simplified_separators, ensure_ascii=False)
        file_parse_configs["separators"] = base64.b64encode(simplified_json.encode("utf-8")).decode("utf-8")

    configs = configs_update_to_db(kb_name,file_name,file_parse_configs)
    response = BaseResponse(code=configs["code"],msg=configs["msg"],data=configs["data"])
    return response

from fastapi import Query, Request
from fastapi.responses import FileResponse,Response
import os
from datetime import datetime


def download_doc(
        request: Request,
        knowledge_base_name: str = Query(..., description="知识库名称", examples=["samples"]),
        file_name: str = Query(..., description="文件名称", examples=["test.txt"]),
        preview: bool = Query(False, description="是：浏览器内预览；否：下载"),
):
    """
    下载知识库文档
    """
    if not validate_kb_name(knowledge_base_name):
        return BaseResponse(code=403, msg="Don't attack me")

    kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {knowledge_base_name}")

    kb_file = KnowledgeFile(filename=file_name, knowledge_base_name=knowledge_base_name)
    if not os.path.exists(kb_file.filepath):
        return BaseResponse(code=404, msg=f"文件 {file_name} 不存在")

    last_modified = datetime.utcfromtimestamp(os.path.getmtime(kb_file.filepath)).strftime('%a, %d %b %Y %H:%M:%S GMT')
    stat_result = os.stat(kb_file.filepath)
    etag = f'{stat_result.st_mtime}-{stat_result.st_size}'

    if_none_match = request.headers.get("If-None-Match")
    if_modified_since = request.headers.get("If-Modified-Since")

    if if_none_match == etag or if_modified_since == last_modified:
        return Response(
            status_code=304,
            headers={
                "Last-Modified": last_modified,
                "ETag": etag,
            }
        )

    return FileResponse(
        path=kb_file.filepath,
        filename=kb_file.filename,
        media_type="multipart/form-data",
        content_disposition_type="attachment",
        headers={
            "Last-Modified": last_modified,
            "ETag": etag,
        }
    )


# def download_doc(
#         knowledge_base_name: str = Query(..., description="知识库名称", examples=["samples"]),
#         file_name: str = Query(..., description="文件名称", examples=["test.txt"]),
#         preview: bool = Query(False, description="是：浏览器内预览；否：下载"),
# ):
#     """
#     下载知识库文档
#     """
#     if not validate_kb_name(knowledge_base_name):
#         return BaseResponse(code=403, msg="Don't attack me")

#     kb = KBServiceFactory.get_service_by_name(knowledge_base_name)
#     if kb is None:
#         return BaseResponse(code=404, msg=f"未找到知识库 {knowledge_base_name}")

#     if preview:
#         content_disposition_type = "inline"
#     else:
#         content_disposition_type = None

#     try:
#         kb_file = KnowledgeFile(filename=file_name,
#                                 knowledge_base_name=knowledge_base_name)

#         if os.path.exists(kb_file.filepath):
#             return FileResponse(
#                 path=kb_file.filepath,
#                 filename=kb_file.filename,
#                 media_type="multipart/form-data",
#                 content_disposition_type=content_disposition_type
#             )
#     except Exception as e:
#         msg = f"{kb_file.filename} 读取文件失败，错误信息是：{e}"
#         logger.error(f'{e.__class__.__name__}: {msg}',
#                      exc_info=e if log_verbose else None)
#         return BaseResponse(code=500, msg=msg)

#     return BaseResponse(code=500, msg=f"{kb_file.filename} 读取文件失败")


def download_img(
        filepath: str = Query(..., description="文件路径", examples=["samples"]),
        filename: str = Query(..., description="文件名称", examples=["test.txt"]),
        preview: bool = Query(True, description="是：浏览器内预览；否：下载"),
):
    """
    下载知识库文档
    """
    if preview:
        content_disposition_type = "inline"
    else:
        content_disposition_type = None

    try:
        if os.path.exists(filepath):
            return FileResponse(
                path=filepath,
                filename=filename,
                media_type="image/jpeg",
                content_disposition_type=content_disposition_type,
            )
    except Exception as e:
        msg = f"{filename} 读取文件失败，错误信息是：{e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)

    return BaseResponse(code=500, msg=f"{filename} 读取文件失败")



def download_file(
        filepath: str = Query(..., description="文件路径", examples=["samples"]),
        filename: str = Query(..., description="文件名称", examples=["test.txt"]),
        preview: bool = Query(False, description="是：浏览器内预览；否：下载"),
):
    """
    下载知识库文档
    """
    if preview:
        content_disposition_type = "inline"
    else:
        content_disposition_type = None

    try:
        if os.path.exists(filepath):
            return FileResponse(
                path=filepath,
                filename=filename,
                content_disposition_type=content_disposition_type,
            )
    except Exception as e:
        msg = f"{filename} 读取文件失败，错误信息是：{e}"
        logger.error(f'{e.__class__.__name__}: {msg}',
                     exc_info=e if log_verbose else None)
        return BaseResponse(code=500, msg=msg)

    return BaseResponse(code=500, msg=f"{filename} 读取文件失败")


def recreate_vector_store(
        knowledge_base_name: str = Body(..., examples=["samples"]),
        allow_empty_kb: bool = Body(True),
        vs_type: str = Body(DEFAULT_VS_TYPE),
        embed_model: str = Body(EMBEDDING_MODEL),
        chunk_size: int = Body(CHUNK_SIZE, description="知识库中单段文本最大长度"),
        chunk_overlap: int = Body(OVERLAP_SIZE, description="知识库中相邻文本重合长度"),
        zh_title_enhance: bool = Body(ZH_TITLE_ENHANCE, description="是否开启中文标题加强"),
        not_refresh_vs_cache: bool = Body(False, description="暂不保存向量库（用于FAISS）"),
):
    """
    recreate vector store from the content.
    this is usefull when user can copy files to content folder directly instead of upload through network.
    by default, get_service_by_name only return knowledge base in the info.db and having document files in it.
    set allow_empty_kb to True make it applied on empty knowledge base which it not in the info.db or having no documents.
    """

    def output():
        kb = KBServiceFactory.get_service(knowledge_base_name, vs_type, embed_model)
        if not kb.exists() and not allow_empty_kb:
            yield {"code": 404, "msg": f"未找到知识库 ‘{knowledge_base_name}’"}
        else:
            if kb.exists():
                kb.clear_vs()
            kb.create_kb()
            #列出当前向量库的文件
            files = list_files_from_folder(knowledge_base_name)
            kb_files = [(file, knowledge_base_name) for file in files]
            i = 0
            for status, result in files2docs_in_thread(kb_files,
                                                       chunk_size=chunk_size,
                                                       chunk_overlap=chunk_overlap,
                                                       zh_title_enhance=zh_title_enhance):
                if status:
                    kb_name, file_name, docs = result
                    kb_file = KnowledgeFile(filename=file_name, knowledge_base_name=kb_name)
                    kb_file.splited_docs = docs
                    yield json.dumps({
                        "code": 200,
                        "msg": f"({i + 1} / {len(files)}): {file_name}",
                        "total": len(files),
                        "finished": i + 1,
                        "doc": file_name,
                    }, ensure_ascii=False)
                    kb.add_doc(kb_file, not_refresh_vs_cache=True)
                else:
                    kb_name, file_name, error = result
                    msg = f"添加文件‘{file_name}’到知识库‘{knowledge_base_name}’时出错：{error}。已跳过。"
                    logger.error(msg)
                    yield json.dumps({
                        "code": 500,
                        "msg": msg,
                    })
                i += 1
            if not not_refresh_vs_cache:
                kb.save_vector_store()

    return StreamingResponse(output(), media_type="text/event-stream")

from server.db.repository.test_case_repository import get_qa_by_vsid,get_qa_by_vsid_batch,test_case_update,test_case_add,test_case_delete

import math
#列出文档的所有片段内容
def list_doc_block(
        kb_name: str = Body(..., description="知识库名称", examples=["samples"]),
        file_name: str = Body(..., description="用户输入", examples=["你好"]),
) -> BaseResponse:
    
    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=500, msg=f"数据库不存在")
    
    file_docs = get_docs_detail(kb_name,file_name)
    if not file_docs:
        return BaseResponse(code=500, msg="文件未解析")
    
    if any(doc.get("doc_id") is not None for doc in file_docs):
        docs = kb.list_docs(file_name)
        docs_len = len(docs)
        batch_size = 50
        for batch in range(math.ceil(docs_len/batch_size)):
            doc_batch = docs[batch*batch_size:batch*batch_size+batch_size if batch*batch_size+batch_size < docs_len else docs_len]
            vs_ids = [doc.metadata.get("vs_id", "") for doc in doc_batch]
            formatted_test_cases = get_qa_by_vsid_batch(vs_ids=vs_ids)
            for idx,doc in enumerate(doc_batch):
                doc.metadata["test_cases"] = []
                doc.metadata["test_cases"] = formatted_test_cases[idx]
                source = doc.metadata.get("source")
                _doc_filename = str(os.path.basename(source))
                _doc_url_request_parameters = urlencode({"knowledge_base_name": kb_name, "file_name": _doc_filename})
                _doc_url = f"knowledge_base/download_doc?" + _doc_url_request_parameters
                doc.metadata["source_url"] = _doc_url

                _image_urls = []
                _equation_urls = []
                if "images_path" in doc.metadata:
                    for _image_local_path in doc.metadata["images_path"]:
                        if len(_image_local_path):
                            _image_filename = os.path.basename(_image_local_path)
                            _image_url_request_parameters = urlencode({"filepath": _image_local_path, "filename":_image_filename})
                            _image_url = f"knowledge_base/download_img?" + _image_url_request_parameters
                            
                            # 检查文件名是否包含equation，如果包含则添加到equation_urls中
                            if "equation" in _image_filename.lower():
                                _equation_urls.append(_image_url)
                            else:
                                _image_urls.append(_image_url)
                        else:
                            _image_url =""
                            _image_urls.append(_image_url)
                doc.metadata["images_url"]=_image_urls
                doc.metadata["equation_url"]=_equation_urls

        return BaseResponse(code=200, msg=f"获取成功",data={"blocks":docs})
    
    docs = [
        {
            "page_content": doc["page_content"],
            "metadata": doc["metadata"],
            "type": "Document"
        }
        for doc in file_docs
    ]

    for doc in docs:
        source = doc["metadata"].get("source")
        _doc_filename = str(os.path.basename(source))
        _doc_url_request_parameters = urlencode({"knowledge_base_name": kb_name, "file_name": _doc_filename})
        _doc_url = f"knowledge_base/download_doc?" + _doc_url_request_parameters
        doc["metadata"]["source_url"] = _doc_url

        _image_urls = []
        _equation_urls = []
        if "images_path" in doc["metadata"]:
            for _image_local_path in doc["metadata"]["images_path"]:
                if len(_image_local_path):
                    _image_filename = os.path.basename(_image_local_path)
                    _image_url_request_parameters = urlencode({"filepath": _image_local_path, "filename":_image_filename})
                    _image_url = f"knowledge_base/download_img?" + _image_url_request_parameters
                    
                    # 检查文件名是否包含equation，如果包含则添加到equation_urls中
                    if "equation" in _image_filename.lower():
                        _equation_urls.append(_image_url)
                    else:
                        _image_urls.append(_image_url)
                else:
                    _image_url =""
                    _image_urls.append(_image_url)
        doc["metadata"]["images_url"]=_image_urls
        doc["metadata"]["equation_url"]=_equation_urls
        
    return BaseResponse(code=200, msg=f"获取成功",data={"blocks":docs}) 


#更新分块文档的内容
def update_doc_block(
        kb_name: str = Body(..., description="知识库名称", examples=["samples"]),
        file_name: str = Body(..., description="用户输入", examples=["你好"]),
        block: Json = Body({}, description="自定义的docs，需要转为json字符串",
                          examples=[{"test.txt": [Document(page_content="custom doc")]}]),
        user_dict= Depends(token_check)
) -> BaseResponse:
    user=user_dict["user"]
    user_email=user["email"]

    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=400, msg="知识库不存在")
    
    kb_file = KnowledgeFile(filename=file_name, knowledge_base_name=kb_name)
    # 将自定义的docs进行向量化
    vs_id = block["metadata"]["vs_id"]
    
    if vs_id == None or len(vs_id) ==0:
        return BaseResponse(code=200, msg=f"'vs_id' 不能为空")
    
    tcs = get_qa_by_vsid(vs_id=vs_id)["data"] if vs_id else []
    existing_tc_ids = {tc["id"] for tc in tcs}
    
    #liubin
    test_cases = block["metadata"]["test_cases"]
    submitted_tc_ids = {test_case.get("test_case_id") for test_case in test_cases}

    if existing_tc_ids != submitted_tc_ids:
        ids_delete = existing_tc_ids - submitted_tc_ids
        for tc_id in ids_delete:
            test_case_delete(id=tc_id)

    for test_case in test_cases:
        test_case_id = test_case.get("test_case_id")
        question = test_case.get("question")
        answer = test_case.get("answer")
        if not test_case_id:
            test_case_add(question=question,answer=answer,vs_id=vs_id,user_email=user_email,test_case_type="参考试题",course_id=None,question_type="问答题")
        else:
            test_case_update(id=test_case_id,question=question,answer=answer,vs_id=vs_id,user_email=user_email,test_case_type=None,course_id=None,question_type="问答题")
    del block["metadata"]["test_cases"]

    db_doc = kb.get_doc_by_id(vs_id)
    
    if db_doc is None:
        return BaseResponse(code=200, msg=f"'vs_id':{vs_id}不存在")
    print("db_doc",db_doc)
    print("block",type(block),block)
    
    kb.update_doc_by_id(vs_id,block)
    from server.db.repository.knowledge_file_repository import update_docs_to_db
    result = update_docs_to_db(kb_name,file_name,[block])
        
    kb.save_vector_store()
    return BaseResponse(code=200, msg=f"更新成功", data=block) 

from server.db.repository.knowledge_file_repository import delete_tc_by_vs

def delete_doc_block(
        kb_name: str = Body(..., description="知识库名称", examples=["samples"]),
        file_name: str = Body(..., description="用户输入", examples=["你好"]),
        block: Json = Body({}, description="自定义的docs，需要转为json字符串",
                          examples=[{"test.txt": [Document(page_content="custom doc")]}])
        # user_dict= Depends(token_check)
) -> BaseResponse:
    # user=user_dict["user"]
    # user_email=user["email"]

    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=400, msg="知识库不存在")
    
    kb_file = KnowledgeFile(filename=file_name, knowledge_base_name=kb_name)
    # 将自定义的docs进行向量化
    vs_id = block["metadata"]["vs_id"]
    
    if vs_id == None or len(vs_id) ==0:
        return BaseResponse(code=200, msg=f"'vs_id' 不能为空")
    
    # 这里的查询是从数据库中做查询
    # tcs = get_qa_by_vsid(vs_id=vs_id)["data"] if vs_id else []
    # print('------get_qa_by_vsid------',tcs)
    # existing_tc_ids = {tc["id"] for tc in tcs}
    
    # 从数据库中删除试题数据
    # if existing_tc_ids:
    #     for tc_id in existing_tc_ids:
    #         test_case_delete(id=tc_id)
    delete_tc_by_vs(vs_id=vs_id)

    kb.delete_chunk_by_id(vs_id)

    from server.db.repository.knowledge_file_repository import delete_docs_from_db
    status = delete_docs_from_db(kb_name,file_name,doc_id=vs_id)
    # print(status)
        
    kb.save_vector_store()
    
    return BaseResponse(code=200, msg=f"删除成功", data=block) 

def clear_vs_by_source(
        kb_name: str = Body(..., description="知识库名称", examples=["samples"]),
        source: str = Body(..., description="用户输入", examples=["你好"])
) -> BaseResponse:
    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=400, msg="知识库不存在")
    
    kb.do_delete_vs_by_source(source)

    kb.save_vector_store()

    return BaseResponse(code=200, msg=f"删除成功", data={}) 


def update_doc_block_embedding(
        kb_name: str = Body(..., description="知识库名称", examples=["samples"]),
        file_name: str = Body(..., description="用户输入", examples=["你好"]),
        block: Json = Body({}, description="自定义的docs，需要转为json字符串",
                          examples=[{"test.txt": [Document(page_content="custom doc")]}]),
        update_embedding: bool = False
) -> BaseResponse:

    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=400, msg="知识库不存在")
    
    kb_file = KnowledgeFile(filename=file_name, knowledge_base_name=kb_name)
    # 将自定义的docs进行向量化
    vs_id = block["metadata"]["vs_id"]

    if vs_id == None or len(vs_id) ==0:
        return BaseResponse(code=200, msg=f"'vs_id' 不能为空")

    # print(vs_id)
    # return 
    # 经过这个函数后，metadata中才有的 vs_id、g_query、answer
    db_doc = kb.get_doc_by_id(vs_id)
    
    if db_doc is None:
        return BaseResponse(code=200, msg=f"'vs_id':{vs_id}不存在")

    # 从数据库中重新创建embedding
    kb.update_doc_by_id_embedding(vs_id, block)

    # from server.db.repository.knowledge_file_repository import update_docs_to_db
    # result = update_docs_to_db(kb_name,file_name,[block])
        
    kb.save_vector_store()

    return BaseResponse(code=200, msg=f"更新成功", data=block) 

from configs.model_config import MODEL_PATH,MODEL_ROOT_PATH
from server.db.repository.knowledge_base_repository import get_kb_detail,kb_update

def update_vectors_db(
        kb_name: str = Body(..., description="知识库名称", examples=["samples"]),
        new_embedding_name: str = Body(..., description="更新用的向量模型")
) -> BaseResponse:
    
    kb_update(kb_name,"更新")
    vs_path = get_vsdb_path(kb_name)

    old_embedding_name = get_kb_detail(kb_name).get("embed_model")

    old_index_path = os.path.join(vs_path, old_embedding_name)
    new_index_path = os.path.join(vs_path, new_embedding_name)

    if not os.path.exists(old_index_path) or not any(os.path.isfile(os.path.join(old_index_path, f)) for f in os.listdir(old_index_path)):
        kb_update(kb_name,"正常")
        return BaseResponse(code=400, msg="未找到旧向量库", data={})
    
    if old_index_path == new_index_path:
        new_index_path = f"{new_index_path}_new"

    old_model_folder = MODEL_PATH["embed_model"].get(old_embedding_name)
    new_model_folder = MODEL_PATH["embed_model"].get(new_embedding_name)

    if not old_model_folder or not new_model_folder:
        kb_update(kb_name,"正常")
        return BaseResponse(code=400, msg="模型不存在", data={})
    
    old_embedding_model = os.path.join(MODEL_ROOT_PATH, old_model_folder)
    new_embedding_model = os.path.join(MODEL_ROOT_PATH, new_model_folder)

    update_vdb(old_index_path,new_index_path,old_embedding_model,new_embedding_model)
    kb_update(kb_name,"正常",new_embedding_name)
    return BaseResponse(code=200, msg=f"向量库更新成功", data={})


def upload_docs_by_chat(
        files: List[UploadFile] = File(..., description="上传文件，支持多文件"),
        kb_name: str = Form(..., description="知识库名称", examples=["samples"]),
        override: bool = Form(False, description="覆盖已有文件"),
        docs: Json = Form({}, description="自定义的docs，需要转为json字符串",
                          examples=[{"test.txt": [Document(page_content="custom doc")]}]),
        use_page1_as_thumbnail: bool = Form(True, description="提取文件首页作为封面"),
        user_dict= Depends(token_check)
) -> BaseResponse:

    if not validate_kb_name(kb_name):
        return BaseResponse(code=403, msg="Don't attack me")

    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:
        return BaseResponse(code=404, msg=f"未找到知识库 {kb_name}")

    failed_files = {}
    file_names = list(docs.keys())

    # 先将上传的文件保存到磁盘
    for result in _save_files_in_thread(files, knowledge_base_name=kb_name, override=override):
        filename = result["data"]["file_name"]
        if result["code"] != 200:
            failed_files[filename] = result["msg"]

        if filename not in file_names:
            file_names.append(filename)
            
    for index, filename in enumerate(file_names):
        if filename[-5:] == ".docx" or filename[-4:] == ".doc":
            file_path = get_file_path(knowledge_base_name=kb_name, doc_name=filename)
            try:
                doc2pdf(file_path)
            except Exception as e:
                return BaseResponse(code=500,msg="文档上传出错，请转换为pdf格式再上传。",data={})
            # 原始文件先不删除，留着cache判断用
            # os.remove(file_path)
            if filename[-5:] == ".docx": 
                filename = filename[:-5] + ".pdf"
            else:
                filename = filename[:-4] + ".pdf"
            file_names[index] = filename
        
        # if filename[-5:] == ".pptx":
        #     file_path = get_file_path(knowledge_base_name=kb_name, doc_name=filename)
        #     pptx2pdf(file_path)
        #     filename = filename[:-5] + ".pdf"

    if use_page1_as_thumbnail:
        for result in _save_page1_in_thread(files, knowledge_base_name=kb_name, override=override):
            pass

    for filename in file_names:
        try:
            kb_file = KnowledgeFile(filename=filename,knowledge_base_name=kb_name)
        except ValueError as e:
            return BaseResponse(code=404, msg=str(e), data={})
        add_file_to_db(kb_file)

    parse_docs(kb_name=kb_name,file_names=file_names,docs=docs)

    return BaseResponse(code=200, msg="文件上传完成", data={})

import uuid

def create_temp_by_chat(
        files: List[UploadFile] = File(..., description="上传文件，支持多文件"),
        chat_session_id: str = Body(None, description="对话框id", examples=["samples"]),
        override: bool = Body(False, description="覆盖已有文件"),
        docs: Json = Body({}, description="自定义的docs，需要转为json字符串",
                          examples=[{"test.txt": [Document(page_content="custom doc")]}]),
        user_dict= Depends(token_check)
) -> BaseResponse:

    if not chat_session_id:
        chat_session_id = uuid.uuid4().hex

    kb_name = chat_session_id
    vector_store_type = "faiss"
    embed_model = EMBEDDING_MODEL

    kb = KBServiceFactory.get_service_by_name(kb_name)
    if kb is None:

        kb = KBServiceFactory.get_service(kb_name, vector_store_type, embed_model)
        create_user_email = user_dict["user"].get("email")
        dep_id = user_dict["user"].get("dep_id")

        kb_type = "临时"
        kb.create_user_email = create_user_email 
        kb.dep_id = dep_id
        kb.create_kb(kb_type=kb_type)

    failed_files = {}
    file_names = list(docs.keys())

    # 先将上传的文件保存到磁盘
    for result in _save_files_in_thread(files, knowledge_base_name=kb_name, override=override):
        filename = result["data"]["file_name"]
        if result["code"] != 200:
            failed_files[filename] = result["msg"]

        if filename not in file_names:
            file_names.append(filename)
            
    for index, filename in enumerate(file_names):
        if filename[-5:] == ".docx" or filename[-4:] == ".doc":
            file_path = get_file_path(knowledge_base_name=kb_name, doc_name=filename)
            try:
                doc2pdf(file_path)
            except Exception as e:
                return BaseResponse(code=500,msg="文档上传出错，请转换为pdf格式再上传。",data={})
            # 原始文件先不删除，留着cache判断用
            # os.remove(file_path)
            if filename[-5:] == ".docx": 
                filename = filename[:-5] + ".pdf"
            else:
                filename = filename[:-4] + ".pdf"
            file_names[index] = filename

    for filename in file_names:
        try:
            kb_file = KnowledgeFile(filename=filename,knowledge_base_name=kb_name)
        except ValueError as e:
            return BaseResponse(code=404, msg=str(e), data={})
        add_file_to_db(kb_file)

    parse_docs(kb_name=kb_name,file_names=file_names,docs=docs)

    return BaseResponse(code=200, msg="文件上传完成", data={"chat_session_id":chat_session_id})
