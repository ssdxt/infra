"""
统一的文档解析 FastAPI 接口
支持 PDF、DOCX、JSON、Markdown、TXT 等格式
"""
import json
import os
from pathlib import Path
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from loguru import logger
from typing import Optional, Literal
import uuid
import httpx
import time
import asyncio
# 导入各个解析器
# from parser.pdf_parser import PDFParser
# from parser.docx_parser import DocxParser
# from parser.json_parser import JsonParser
# from parser.markdown_parser import MarkdownParser
# from parser.txt_parser import TxtParser
from parser.mineru_parser import MineruParser
from vector_db import MilvusClient
from rustfs import rust
import asyncio

from schema import ImageModel

class ChunkModel(BaseModel):
    """文档解析块返回类型"""
    chunk_id: str = Field(..., description="ID")
    content: str = Field(..., description="文字内容、图、表的capture")
    file_id: str = Field(..., description="文件ID")
    file_path: str = Field(..., description="文件路径")
    update_time: str = Field(..., description="更新时间")
    bbox_type: str = Field(default="text", description="边界框类型")
    title: str = Field(default="", description="文字的标题、图片表格的caption")
    summary: str = Field(default="", description="摘要")
    img_path: str = Field(default="", description="图片路径")
    bbox: List[Any] = Field(default_factory=list, description="边界框坐标")
    page_idx: List[Any] = Field(default_factory=list, description="页码索引")
    # others: str = Field(default="", description="其他扩展字段")
    others: Dict[str, Any] = Field(
        default_factory=dict,
        description="其他扩展字段"
    )

# app = FastAPI(title="文档解析 API", description="统一的文档解析接口，支持多种格式")

# mineru_parser = MineruParser("mineru", "http://127.0.0.1:8000", "http://127.0.0.1:8406")
mineru_parser = MineruParser()
milvus_client = MilvusClient()


# @app.post("/parse")
async def insert_document():
    print(milvus_client.get_all_collections())
    

    
    # milvus_client.delete_collection(
    #     collection_name="demo_collection"
    # )
    # milvus_client.delete_collection(
    #     collection_name="images2"
    # )
    
    # files = ["/mnt/ddata2/cc007/omniknow2/parser/rag/中国自主先进压水堆技术“华龙一号”(上册)test.pdf","/mnt/ddata2/cc007/omniknow2/parser/rag/data/中国自主先进压水堆技术“华龙一号”(上册).pdf","/mnt/ddata2/cc007/omniknow2/parser/rag/data/中国自主先进压水堆技术“华龙一号”(下册).pdf","/mnt/ddata2/cc007/omniknow2/parser/rag/data/非能动安全先进核电厂ap1000+.pdf"]
    # files = ["/mnt/ddata2/cc007/omniknow2/parser/rag/data/中国自主先进压水堆技术“华龙一号”(上册).pdf","/mnt/ddata2/cc007/omniknow2/parser/rag/data/中国自主先进压水堆技术“华龙一号”(下册).pdf","/mnt/ddata2/cc007/omniknow2/parser/rag/data/非能动安全先进核电厂ap1000+.pdf"]
    # files = ["/mnt/ddata2/cc007/omniknow2/parser/rag/data/中国自主先进压水堆技术“华龙一号”(上册).pdf","/mnt/ddata2/cc007/omniknow2/parser/rag/data/中国自主先进压水堆技术“华龙一号”(下册).pdf"]
    # # files = []
    files = ["/mnt/ddata2/cc007/omniknow2/parser/rag/中国自主先进压水堆技术“华龙一号”(上册).pdf"]
    # files = ["/mnt/ddata2/cc007/omniknow2/parser/rag/中国自主先进压水堆技术“华龙一号”(下册).pdf"]
    # files = ["/mnt/ddata2/cc007/omniknow2/parser/rag/非能动安全先进核电厂ap1000+.pdf"]
    # files = ["/mnt/ddata2/cc007/omniknow2/parser/rag/综合办制度汇编完整版240806.pdf"]
    files = ["/mnt/ddata2/cc007/omniknow2/parser/rag/VIN编制规则.xls"]
    
    title_correction=True
    # files = ["/mnt/ddata2/cc007/omniknow2/parser/rag/父亲2.pdf"]
    # output_dir = "/mnt/ddata2/cc007/omniknow2/parser/rag/"
    for file in files:
        # mineru_parser.convert_office_to_pdf(file,output_dir)
        st = time.time()
        # file = output_dir+"父亲2.pdf"
        file_id = str(uuid.uuid4())
        collection_name = "hediantest"
        img_collection_name = "imagestest"
        print("正在解析...")
        chunks,doc_summary = await mineru_parser.parse(
            file_id=file_id,
            file_path=file,
            summary=False, 
            chunk_source='document',
            # backend="vlm-vllm-async-engine",  # vlm-vllm-async-engine
            backend="hybrid-auto-engine",  
            # backend="pipeline",  
            # include_parent_titles=True,
            start_page_id=0,
            # start_page_id=13,
            end_page_id=99999,
            # return_chapter_summary=True,
            title_correction=title_correction,  # 标题修正，速度慢
            # output_dir=os.path.abspath("./output/mineru_output")
        )
        print('解析总耗时:',time.time()-st)
        print(type(chunks))
        # print(chunks[:3])
        
        # print(chunks)
        # print(summary_list)
        print("解析完成，开始插入...")
        print("chunk个数为：",len(chunks))
        
        st = time.time()        
        img_chunks = []
        for data in chunks:
            if data.bbox_type!="image":
                continue
            img_chunk = {
                "chunk_id":data.chunk_id,
                "kb_id":collection_name,
                "media_path":data.media_path,
                "source_media_path":'/mnt/ddata2/cc007/omniknow2/parser/rag/parser/mineru_output/ap1000/auto/images/0abb6cec0142b3d339bbaaf9ace2ac9d4c5fd6c0530ddf176e99ff095a081190.jpg',
                "img_id":'222222222222222222',
            }
            img_chunks.append(ImageModel(**img_chunk))
            
        print("图片chunk个数为：",len(img_chunks))
        await milvus_client.img_insert(collection_name=img_collection_name, chunks=img_chunks)
        st1 = time.time()
        print("图片插入耗时:",st1-st)
        # print("--------------图片插入完成--------------")
        if title_correction:
            await milvus_client.document_insert(collection_name=collection_name, chunks=chunks)
            print("chunk个数为：",len(chunks))
            st2 = time.time()
            print("文档插入耗时:",st2-st1)
        
        #     print("--------------文档插入完成--------------")
            # st3 = time.time()
        
            # # await milvus_client.summary_insert(chunk=doc_summary)
            # await milvus_client.summary_insert(content=content, file_id=file_id, doc_collection_name=collection_name, collection_name=sum_collection_name)
            
            # st4 = time.time()
            
            # print("摘要插入耗时:",st4-st3)
            
        #     print("--------------摘要插入完成--------------")
        # else:
            # st4 = time.time()
        
            # await milvus_client.document_insert(collection_name=collection_name, chunks=chunks)
            # print("摘要插入耗时:",st4-st3)
            
        #     print("--------------文档插入完成--------------")
            
        # print(f'------------------{file} insert success-------------------')

async def list_collections():
    print(milvus_client.get_all_collections())
    # milvus_client.delete_collection(
    #     collection_name="images2"
    # )
    
    # # z_abb7be2a2609d4685916c61ae2676eea
    
    milvus_client.delete_collection(
        collection_name="sop"
    )
    
    # milvus_client.delete_collection(
    #     collection_name="chapter_summary_test"
    # )
    
    # milvus_client.delete_collection(
    #     collection_name="tesla_manual_oss_v2"
    # )
    
    # milvus_client.delete_collection(
    #     collection_name="test6"
    # )
    
    # milvus_client.delete_collection(
    #     collection_name="test666"
    # )
        
    # milvus_client.delete_collection(
    #     collection_name="test6"
    # )

# @app.post("/parse")
async def search_document():
    """
    解析文档的统一接口
    
    Args:
        request: 包含 file_id, file_path, knowledge_id 的请求对象
    
    Returns:
        ParseResponse: 包含解析结果的响应对象
    """
    # query = "地坛的秋天"
    query = "设备冷却水系统"
    # query = "数字棒位是什么"
    # query = "tesla model3的后排屏幕是怎么拆解的，需要用什么工具"
    # query = "查询特斯拉Model 3前车门饰板的标准拆解步骤与工具要求"
    # query = "查询特斯拉Model 3前车门饰板的标准拆解步骤"
    # collection_name = "ditan"
    # collection_name = "test_telsa"
    # collection_name = "tesla_manual"
    collection_names = ["tesla_manual", "test_telsa"]
    # collection_name = "vehical_repair"
    top_k = 3
    file_id = "123456789"
    knowledge_id = "appppp"
        
    file_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/TeslaModelDismantlingGuideTesla_Model_3_204 -.pdf"
    # 所有解析器都支持关键字参数，因此可以统一调用
    # chunks = await mineru_parser.parse(
    #     file_id=file_id,
    #     file_path=file_path,
    #     chunk_source="document"
    #     # knowledge_id=collection_name
    # )

    # pdf_name = "Tesla_Model_3_204.pdf"
    # for chunk in chunks:
    #     if chunk.media_path:
    #         media_path = chunk.media_path
    #         name = os.path.basename(media_path)
    #         with open(media_path, "rb") as f:
    #             img_bytes = f.read()
    #         await rust.upload_file(bucket_name="public",object_name=f"tesla_manual/Tesla/document/test/{name}",file_data=img_bytes)
    #         chunk.media_path = f"http://183.129.232.94:18372/public/tesla_manual/Tesla/document/test/{name}"
    #     chunk.file_path = f"http://183.129.232.94:18372/public/tesla_manual/Tesla/document/test/{pdf_name}"
       
    #     # break
    # # print(chunks[:2])
    
    # await milvus_client.insert(collection_name=collection_name, chunks=chunks)
    # res = await milvus_client.semantics_search(query=query, collection_name=collection_name, top_k=top_k)
    # res = await milvus_client.kerword_search(query=query, collection_name=collection_name, top_k=top_k)
    import time
    st = time.time()
    # res = await milvus_client.hybrid_search(query=query, collection_name=collection_name, top_k=top_k, threshold=0.2,rerank_model=True)
    # res = await milvus_client.hybrid_search_single_collection(query=query, collection_name=collection_name, top_k=top_k, threshold=0.2,rerank_model=True)
    # res = await milvus_client.hybrid_search(query=query, collection_names=collection_names, top_k=top_k, threshold=0.2,rerank_model=True)
    # expr="media_path!=''"
    # expr = "media_path like '%.png' or media_path like '%.jpg' or media_path like '%.jpeg' or media_path like '%.bmp' or media_path like '%.gif' or media_path like '%.webp'"
    expr = ""
    # get_chunks_by_par_title=True
    # res = milvus_client.doc_search(query="废树脂处理包括哪两项操作", collection_names=['hedian2'], top_k=top_k, threshold=0.2,rerank_model=True,context_chars=500,expr=expr)
    # res = milvus_client.list_curtitle_by_fileid(collection_name='hedian2',file_ids=['309c6e7900f747058adc056e238ed569'])
    # res = milvus_client.img_search(query_img="/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/outputs/media/16 - 电池系统/GUID-13C4CFD4-F197-4D80-86E0-F2FF464E0BE7-online-en-US.jpg")
    # res = milvus_client.doc_search(query="硼酸制备箱", collection_names=['z_abb7be2a2609d4685916c61ae2676eea'], top_k=top_k, threshold=0.2,rerank_model=True,context_chars=500,expr=expr)
    # res = milvus_client.doc_search(query="核电厂的用电设备，按其功能分为哪几类", collection_names=['tesla_manual_oss_v2'], top_k=top_k, threshold=0.2,rerank_model=True,context_chars=500,expr=expr)
    # documents = milvus_client.doc_search(query="具有代表性的“华龙一号”异常运行规程策略内容", collection_names=['hedian2'], top_k=top_k, threshold=0.2,rerank_model=True,context_chars=500, expr=expr)
    # for i in range(10):
    #     documents = milvus_client.doc_search(query="SL-2“华龙一号”堆型抗震设计采用的加速度时程", collection_names=['hedian2'], top_k=top_k, threshold=0.2,rerank_model=True,context_chars=500, expr=expr)
    # res = milvus_client.doc_search(query="燃油箱加油故障处理", collection_names=['z_2989fe9a35646ac07a8faee9e0bf4139'], top_k=top_k, threshold=0.000005,rerank_model=True,context_chars=500, expr=expr)
    res = milvus_client.doc_search(query="如果燃油漏油小于60滴/分钟（180ml/hr或3cc/min），是不是无需维护工作。", collection_names=['z_2989fe9a35646ac07a8faee9e0bf4139'], top_k=top_k, threshold=0.000005,rerank_model=True,context_chars=500, expr=expr)
    # res = milvus_client.list_curtitle_by_fileid(collection_name='z_2989fe9a35646ac07a8faee9e0bf4139',file_ids=['173cbd9f-3749-4536-9161-5d3b8eec36c2'])
    
    # documents = milvus_client.doc_search(query="核电厂由于系统、设备、部件复杂繁多，运行中很可能会出现各种故障或异常工况，这些故障或异常工况在应对不及时等及最坏的情况下", collection_names=['hedian_test100'], top_k=top_k, threshold=0.2,rerank_model=True,context_chars=500, expr=expr,get_chunks_by_par_title=get_chunks_by_par_title)
    # await milvus_client.delete_doc_by_id(collection_name='123',file_id='345')
    print('第一轮搜索：')
    print(res)
    # print()
    # print("第二轮搜索：")
    # for document in documents:
    #     print(milvus_client.list_chunks_by_par_title('hedian2',file_id=document.file_id,par_title=document.cur_title))
    #     print(milvus_client.list_chunks_by_par_title('hedian2',file_id=document.file_id,par_title=document.par_title))
    #     print('----------------------')
    #     print(milvus_client.list_chunks_by_chunk_index('hedian2',file_id=document.file_id,chunk_index=document.chunk_index,return_number=2))

    # res = milvus_client.doc_search(query="丛书主编：叶奇蓁", collection_names=['hedian_test50'], top_k=top_k, threshold=0.2,rerank_model=True)
    # res = milvus_client.doc_search_with_page_context(query="核电厂的用电设备，按其功能分为哪几类", collection_names=['hedian_test'], top_k=top_k, threshold=0.2,rerank_model=True)
    # res = milvus_client.doc_search(query="中控台总成 ((拆卸和更换))", collection_names=['tesla_manual_oss_v2'], top_k=top_k, threshold=0.2,rerank_model=True)
    # milvus_client.delete_collection(
    #     collection_name="tesla_manual_oss_v2"
    # ) 
    # print(milvus_client.get_all_collections())
    
    # print(milvus_client.img_search("/mnt/ddata2/cc007/omniknow2/parser/rag/193D032B-4AF8-4513-AF72-B6822B357869.png",threshold=0,top_k=5))
    # print(milvus_client.img_search("/mnt/ddata2/cc007/omniknow2/parser/rag/IMG_2695.HEIC.JPG",threshold=0,top_k=5))
    # print(milvus_client.img_search("/mnt/ddata2/cc007/omniknow2/parser/rag/IMG_2696.HEIC.JPG",threshold=0,top_k=5))
    
    # res = milvus_client.hybrid_search(query=query, collection_names=collection_names, top_k=top_k, threshold=0.2,rerank_model=True)
    # res = milvus_client.memory_insert(messages="叫爸爸", user_id="123", thread_id="789")
    # res = milvus_client.memory_search(query="爸爸",user_id="123")
    # res = await milvus_client.delete_by_chunk_id(chunk_id=query, collection_name=collection_name)
    # chunk_id: str, collection_name: str
    # res = await milvus_client.list_chunks(collection_name=collection_name, title="0001 - 保养服务", file_id="309c6e7900f747058adc056e238ed569")
    # res = milvus_client._list_collections()
    # res = milvus_client.img_search("/mnt/ddata2/cc007/omniknow2/parser/rag/img_search/9e894b2467f84af8bbe709f6dcf8ee80.jpg",threshold=0)
    # res = milvus_client.sop_search("X179")
    # res = await milvus_client.delete_collection('long_memory')
    # res = milvus_client.delete_collection('long_memory')
    # content_list = [i.content for i in res]
    print(time.time()-st)
    

async def upload_oss():
    file_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/重卡维修.jpg"
    name = os.path.basename(file_path)
    oss_path = f"tesla_manual/Tesla/document/test/{name}"
    
    with open(file_path, "rb") as f:
        img_bytes = f.read()
    await rust.upload_file(bucket_name="public",object_name=oss_path,file_data=img_bytes)
    # chunk.media_path = f"http://183.129.232.94:18372/public/tesla_manual/Tesla/document/test/{name}"
    print('success: ',"http://183.129.232.94:18372/public/"+oss_path)
    

async def parse_media(file_path):

    async with httpx.AsyncClient() as client:
        files = {
            "file": ("audio.wav", open(file_path, "rb"), "audio/wav")
        }

        resp = await client.post(url, files=files)
        print(resp.text)
        return resp.text

def load_chunks_from_json(path: str) -> List:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    return data


async def insert_sop():
    json_path = "/data/workspace/gcy/omniknow2/parser/rag/tesla/item_to_page.json"
    chunks = load_chunks_from_json(json_path)

    collection_name = "sop"
    # res = milvus_client.sop_insert(chunks=chunks, collection_name=collection_name)
    
    # if res:
    #     print("SOP插入成功")

    res = milvus_client.sop_search(query = "X1004-23",collection_name=collection_name, top_k=5)
    print(res)


if __name__ == "__main__":
    # uvicorn.run(app, host="0.0.0.0", port=8000)

    # asyncio.run(search_document())
    # asyncio.run(insert_document())
    # asyncio.run(list_collections())
    asyncio.run(insert_sop())
    
    # asyncio.run(upload_oss())
    
