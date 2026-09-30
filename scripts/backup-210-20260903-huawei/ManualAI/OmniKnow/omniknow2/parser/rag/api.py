import os
from pathlib import Path
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from loguru import logger
from typing import Optional, Literal
from parser.utils import get_file_extension, get_parser, is_img_search_enabled
from parser import MineruParser
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from vector_db import MilvusClient
from schema import ParseRequest, ParseResponse,SearchRequest,SearchResponse,UploadRequest,UploadResponse,ConvertRequest,ConvertResponse,ImgUploadRequest,MemoryUploadRequest,MemoryDeleteRequest,DocDeleteRequest,ImageModel, CollectionDeleteRequest

app = FastAPI(title="文档解析 API", description="统一的文档解析接口，支持多种格式")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


OFFICE_FORMATS = {".doc", ".docx", ".ppt", ".pptx"}
TEXT_FORMATS = {".txt", ".md"}
milvus_client = MilvusClient()


def _validate_file_path(file_path: str) -> None:
    """校验文件路径存在且为文件，否则抛出 HTTPException"""
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=400, detail=f"路径不是文件: {file_path}")

def csv_to_xlsx(file_path: str, xlsx_path: str):
    csv = pd.read_csv(file_path, encoding='utf-8')
    csv.to_excel(xlsx_path, sheet_name='data')


def xls_to_xlsx(xls_path: str, xlsx_path: str) -> None:
    sheets = pd.read_excel(xls_path, sheet_name=None, header=None)
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False, header=False)


@app.post("/parse_document", response_model=ParseResponse)
async def parse_document(request: ParseRequest) -> ParseResponse:
    """
    解析文档的统一接口
    
    Args:
        request: 包含 file_id, file_path, knowledge_id 的请求对象
    
    Returns:
        ParseResponse: 包含解析结果的响应对象
    """
    try:
        _validate_file_path(request.file_path)
        logger.info(f"文件路径为: {request.file_path}")
        
        # 获取对应的解析器
        if request.file_path.lower().endswith((".csv", ".xls", ".xlsx")):
            request.method = "normal"
           
        parser = get_parser(request.file_path, request.method)
        
        # 使用关键字参数调用 parse 方法，避免参数顺序问题
        # 所有解析器都支持关键字参数，因此可以统一调用
        chunks,doc_summary = await parser.parse(
            file_id=request.file_id,
            file_path=request.file_path,
            summary=request.summary,
            chunk_source=request.chunk_source,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            delimiters=request.delimiters,
            output_dir=request.output_dir,            
            method=request.method,
            #backend=request.backend,
            table=request.table,
            # include_parent_titles=request.include_parent_titles,
            start_page_id=request.start_page-1,
            end_page_id=request.end_page,
            title_correction=request.title_correction,  # 标题修正，速度慢
        )   
                
        logger.info(f"成功解析文件: {request.file_path}, 生成 {len(chunks)} 个块")
        
        return ParseResponse(
            success=True,
            message=f"解析成功，生成 {len(chunks)} 个块",
            doc_summary=doc_summary, # str
            data=chunks,  # list[chunk]
        )
        
    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        logger.error(f"解析文件失败: {request.file_path}, 错误: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"解析文件时发生错误: {str(e)}"
        )


@app.post("/convert_document", response_model=ConvertResponse)
async def convert_document(request: ConvertRequest) -> ConvertResponse:
    """
    文档格式转换的统一接口
        doc、docx、 ppt、pptx、xls、xlsx、txt、md --> pdf
        png、jpeg、jpg、bmp、tiff、tif、gif、webp --> png
    
    Args:
        request: 包含 file_path, output_path 的请求对象
    
    Returns:
        ParseResponse: 包含解析结果的响应对象
    """
    try:
        _validate_file_path(request.file_path)
        file_path = Path(request.file_path)
        output_dir = Path(request.output_dir)

        # Get file extension
        ext = file_path.suffix.lower()
        logger.info("文件格式为:--{}--".format(ext))        
        
        if ext in OFFICE_FORMATS:            
            logger.warning(
                f"Warning: Office document detected ({ext}). "
                f"MinerU 2.0 requires conversion to PDF first."
            )
            convert_path = MineruParser.convert_office_to_pdf(file_path, output_dir)
        elif ext in TEXT_FORMATS:
            convert_path =  MineruParser.convert_text_to_pdf(file_path, output_dir)
            
        elif ext in [".png", ".jpeg", ".jpg", ".bmp", ".tiff", ".tif", ".gif", ".webp"]:
            parser = get_parser(file_path)
            logger.info(parser)
            convert_path = await parser.convert_image(
                image_path=file_path,
                output_dir=output_dir
            )
        elif ext in [".csv", ".xls", ".xlsx"]:
            convert_path = file_path.with_suffix(".xlsx")
            if ext == ".csv":
                try:
                    csv_to_xlsx(file_path, convert_path)
                except Exception as e:
                    logger.error(f"CSV to XLSX conversion failed for {file_path}: {str(e)}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"CSV to XLSX conversion failed: {str(e)}"
                    )
                
            elif ext == ".xls":
                try:
                    xls_to_xlsx(file_path, file_path.with_suffix(".xlsx"))
                except Exception as e:
                    logger.error(f"XLS to XLSX conversion failed for {file_path}: {str(e)}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"XLS to XLSX conversion failed: {str(e)}"
                    )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式转换: {ext}"
            )
        
        
        return ConvertResponse(
            success=True,
            message=f"转换成功, 转换后的文件地址为: {str(convert_path)}",
            file_path=str(convert_path)
        )
        
    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        logger.error(f"解析文件失败: {request.file_path}, 错误: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"解析文件时发生错误: {str(e)}"
        )



@app.post("/document_insert", response_model=UploadResponse)
async def document_insert(request: UploadRequest) -> UploadResponse:
    """
    解析文档的统一接口
    
    Args:
        request: 包含 file_id, file_path, knowledge_id 的请求对象
    
    Returns:
        ParseResponse: 包含解析结果的响应对象
    """
    try:
        chunks = request.chunks
        collection_name = request.collection_name
        img_collection_name = request.img_collection_name
        sum_collection_name = request.sum_collection_name
        # print(sum_collection_name)
        content = request.doc_summary
        file_id = chunks[0].file_id if chunks else "unknown_file_id"
        
        # 检查文件是否存在        
        img_chunks = []
        for data in chunks:
            if data.bbox_type!="image":
                continue
            img_chunk = {
                "chunk_id":data.chunk_id,
                "kb_id":collection_name,
                "media_path":data.media_path,
                "source_media_path":data.others["source_media_path"],
                "img_id":data.others["img_id"],
            }
            img_chunks.append(ImageModel(**img_chunk))
            
        logger.info(f"图片chunk个数为：{len(img_chunks)}")
        if not is_img_search_enabled():
            logger.info("IMG_SEARCH=False，跳过图片向量化与图片库插入。")
        elif img_chunks:
            try:
                await milvus_client.img_insert(
                    collection_name=img_collection_name,
                    chunks=img_chunks
                )
            except Exception as e:
                logger.exception("图片插入异常: ", str(e))
                raise HTTPException(
                    status_code=500,
                    detail=f"图片插入异常: {str(e)}"
                )

            logger.info("--------图片插入完成--------")
        else:
            logger.info("未发现图片chunk，跳过图片库插入。")
        try:
            await milvus_client.document_insert(collection_name=collection_name, chunks=chunks)
        except Exception as e:
            logger.exception("文档插入异常: ", str(e))
            raise HTTPException(
                status_code=500,
                detail=f"文档插入异常: {str(e)}"
            )
        logger.info("--------------文档插入完成--------------")
        
        try:
            await milvus_client.summary_insert(content=content, file_id=file_id, doc_collection_name=collection_name, collection_name=sum_collection_name)
        except Exception as e:
            logger.exception("summary插入异常: ", str(e))
            raise HTTPException(
                status_code=500,
                detail=f"summary插入异常: {str(e)}"
            )
        logger.info("--------------摘要插入完成--------------")
            
        return UploadResponse(
            success=True,
            message=f"解析成功，插入到{request.collection_name}知识库中，生成 {len(request.chunks)} 个块",
        )
        
    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        logger.error(f"上传文件失败: {request.file_path}, 错误: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"上传文件时发生错误: {str(e)}"
        )



@app.post("/keyword_search", response_model=SearchResponse)
async def keyword_document(request: SearchRequest) -> SearchResponse:
    """
    关键词搜索接口
    
    Args:
        request: 包含 query, collection_name, top_k 的请求对象
    
    Returns:
        SearchResponse: 包含搜索结果的响应对象
    """
    try:
        documents = []
        for collection in request.collection_name:
            results = await milvus_client.keyword_search(query=request.query, 
                                                        collection_name=collection, 
                                                        top_k=request.top_k,
                                                        # threshold=request.threshold
                                                        )
            documents.extend(results)
            
        # res = [d for d in documents if d.score >= request.threshold]
        documents.sort(key=lambda x: x.score, reverse=True)

        return SearchResponse(
            success=True,
            message="搜索成功",
            chunks=documents[:request.top_k],
        )
        
    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"检索文件时发生错误: {str(e)}"
        )


@app.post("/hybrid_search", response_model=SearchResponse)
async def hybrid_document(request: SearchRequest) -> SearchResponse:
    """
    混合搜索接口（语义搜索 + 关键词搜索）
    
    Args:
        request: 包含 query, collection_name, top_k 的请求对象
    
    Returns:
        SearchResponse: 包含搜索结果的响应对象
    """
    try:
        # 将 collection_name 转换为列表格式以支持多集合搜索
        collection_names = request.collection_name if isinstance(request.collection_name, list) else [request.collection_name]
        # results = await milvus_client.doc_search(query=request.query, 
        results = milvus_client.doc_search(query=request.query, 
                                                    collection_names=collection_names, 
                                                    top_k=request.top_k,
                                                    threshold=request.threshold,
                                                    rerank_model=request.rerank_model,
                                                    dense_type=request.dense_type,
                                                    sparse_type=request.sparse_type,
                                                    dense_weight=request.dense_weight,
                                                    sparse_weight=request.sparse_weight,
                                                    reranker_type=request.reranker_type,
                                                    )
        
        return SearchResponse(
            success=True,
            message="搜索成功",
            chunks=results,
        )
        
    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"检索文件时发生错误: {str(e)}"
        )


@app.post("/img_insert", response_model=UploadResponse)
async def img_insert_milvus(request: ImgUploadRequest) -> UploadResponse:
    """
    图片插入kb的接口
    
    Args:
        request: 包含 chunks、collection_name 的请求对象
    
    Returns:
        ParseResponse: 包含解析结果的响应对象
    """
    try:
        if not is_img_search_enabled():
            logger.info("IMG_SEARCH=False，跳过 /img_insert 请求。")
            return UploadResponse(
                success=True,
                message="IMG_SEARCH=False，已跳过图片向量化与图片库插入",
            )

        await milvus_client.img_insert(collection_name=request.img_collection_name, chunks=request.chunks)
                
        return UploadResponse(
            success=True,
            message=f"解析成功，插入图片到{request.collection_name}知识库中，生成 {len(request.chunks)} 个块",
        )
        
    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        logger.error(f"图片上传失败, 错误: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"上传文件时发生错误: {str(e)}"
        )


@app.post("/memory_insert", response_model=UploadResponse)
async def memory_insert(request: MemoryUploadRequest) -> UploadResponse:
    """
    图片插入kb的接口
    
    Args:
        request: 包含 messages、collection_name、user_id、thread_id 的请求对象
    
    Returns:
        ParseResponse: 包含解析结果的响应对象
    """
    try:
        # 检查文件是否存在        
        await milvus_client.memory_insert(collection_name=request.collection_name, 
                                          messages=request.messages, 
                                          user_id=request.user_id, 
                                          thread_id=request.thread_id,
                                          update_time=request.update_time)
                
        return UploadResponse(
            success=True,
            message=f"成功，插入memory到{request.collection_name}知识库中",
        )
        
    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        logger.error(f"memory上传失败, 错误: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"上传文件时发生错误: {str(e)}"
        )


@app.post("/memory_delete_by_id", response_model=UploadResponse)
async def memory_delete_by_id(request: MemoryDeleteRequest) -> UploadResponse:
    """
    按 user_id + thread_id 删除 memory 的接口

    Args:
        request: 包含 collection_name、user_id、thread_id 的请求对象

    Returns:
        UploadResponse: 删除结果
    """
    try:
        # 检查文件是否存在        
        await milvus_client.delete_memory_by_id(collection_name=request.collection_name, user_id=request.user_id, thread_id=request.thread_id)
                
        return UploadResponse(
            success=True,
            message=f"删除成功",
        )
        
    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        logger.error(f"memory删除失败, 错误: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"删除时发生错误: {str(e)}"
        )



@app.post("/delete_collection", response_model=UploadResponse)
async def delete_collection(request: CollectionDeleteRequest) -> UploadResponse:
    """
    删除整个知识库的接口

    Args:
        request: 包含 collection_name 的请求对象

    Returns:
        UploadResponse: 删除结果
    """
    try:
        # 检查文件是否存在        
        milvus_client.delete_collection(collection_name=request.collection_name)
                
        return UploadResponse(
            success=True,
            message=f"删除成功",
        )
    
        
    except Exception as e:
        logger.error(f"知识库删除失败, 错误: {str(e)}")
        
        # 系统错误
        raise HTTPException(
            status_code=500,
            detail=f"删除失败: {str(e)}"
        )

@app.post("/delete_doc_by_id", response_model=UploadResponse)
async def delete_doc_by_id(request: DocDeleteRequest) -> UploadResponse:
    """
    按 file_id（及可选 chunk_id）删除文档 chunk 的接口

    Args:
        request: 包含 collection_name、file_id、chunk_id（可选）的请求对象

    Returns:
        UploadResponse: 删除结果
    """
    try:
        # 检查文件是否存在        
        await milvus_client.delete_doc_by_id(collection_name=request.collection_name, file_id=request.file_id, chunk_id=request.chunk_id)
                
        return UploadResponse(
            success=True,
            message=f"删除成功",
        )
    
    except ValueError as e:
        # 业务错误（找不到数据 / collection不存在）
        logger.error(f"文档删除失败, 错误: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"文档删除失败, 错误: {str(e)}")
        
        # 系统错误
        raise HTTPException(
            status_code=500,
            detail=f"删除失败: {str(e)}"
        )
    
@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "message": "服务运行正常"}


@app.get("/supported-formats")
async def get_supported_formats():
    """获取支持的文件格式列表"""
    return {
        "supported_formats": [
            ".pdf",
            ".docx",
            ".json",
            ".jsonl",
            ".md",
            ".markdown",
            ".txt"
        ]
    }


if __name__ == "__main__":
    # import asyncio
    # request = ConvertRequest(
    #     file_path="/mnt/ddata2/cc007/omniknow2/parser/rag/parser/test_case/test.md",
    #     output_dir="/mnt/ddata2/cc007/omniknow2/parser/rag/"
    # )

    # asyncio.run(convert_document(request))
    # asyncio.run(img_insert_milvus(request))
    
    import uvicorn
    #uvicorn.run(app, host="0.0.0.0", port=8008)
    uvicorn.run(app, host="0.0.0.0", port=8010)
