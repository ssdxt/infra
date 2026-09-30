from io import BytesIO
import requests
from PIL import Image
import os
import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from uuid import uuid4
from datetime import datetime, timedelta
import subprocess
from src.subagents.rag.milvus_client import MilvusDB
from tqdm import tqdm
import aiohttp
import aiofiles
import asyncio
import warnings

# 忽略所有警告
warnings.filterwarnings("ignore")
milvus_client = MilvusDB()

def download_image(url,save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    headers = {
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
        # "user-agent": UserAgent().random,
    }
    try:
        with requests.get(url, headers=headers, timeout=10,verify=False) as r:
            r.raise_for_status()  # 检查状态码
            # 将响应内容转换为图像
            # img_data = b''.join(r.iter_content())  # 读取所有内容
            # img =  Image.open(BytesIO(img_data)) # 使用 BytesIO 打开图像
            # img.verify()  # 验证图像完整性
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                # print('下载成功')
    except Exception as e:
        print(e,url)
        

# def download_image(url: str, save_path: str):
#     '''
#     校验图片是否损坏
#     '''
#     os.makedirs(os.path.dirname(save_path), exist_ok=True)
#     headers = {
#         "sec-fetch-dest": "empty",
#         "sec-fetch-mode": "cors",
#         "sec-fetch-site": "same-origin",
#         "user-agent":UserAgent().random,
#     }
#     try:
#         with requests.get(url, headers=headers, stream=True, timeout=10) as r:
#             r.raise_for_status()  # 检查状态码
#             # 将响应内容转换为图像
#             # img_data = b''.join(r.iter_content())  # 读取所有内容
#             # img = Image.open(BytesIO(img_data))  # 使用 BytesIO 打开图像
#             # img.verify()  # 验证图像完整性
#             with open(save_path, "wb") as f:
#                 for chunk in r.iter_content(chunk_size=8192):
#                     if chunk:
#                         f.write(chunk)
#     except Exception as e:
#         print("下载失败===========",e)



def is_image_ok(path: str) -> bool:
    try:
        with Image.open(path) as img:
            img.verify()   # 验证文件完整性
        return True
    except Exception:
        return False


# def download_image(url: str, save_path: str):
#     """
#     下载图片到本地
#     :param url: 图片 URL
#     :param save_path: 保存的本地路径（含文件名）
#     """
#     # 创建目录
#     os.makedirs(os.path.dirname(save_path), exist_ok=True)

#     headers = {
#         "sec-fetch-dest": "empty",
#         "sec-fetch-mode": "cors",
#         "sec-fetch-site": "same-origin",
#         "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
#     }

#     try:
#         with requests.get(url, headers=headers, stream=True, timeout=10) as r:
#             r.raise_for_status()   # 检查状态码

#             with open(save_path, "wb") as f:
#                 for chunk in r.iter_content(chunk_size=8192):
#                     if chunk:
#                         f.write(chunk)

#         # print(f"下载成功: {save_path}")
#         # return save_path
#     except Exception as e:
#         print(f"下载失败: {e}")



async def download_image_async(url: str, save_path: str):
    """
    异步下载图片到本地
    :param url: 图片 URL
    :param save_path: 保存的本地路径（含文件名）
    """
    # 创建目录
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "priority": "u=0, i",
        "sec-ch-ua": "\\Microsoft",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\\Windows",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
    }

    timeout = aiohttp.ClientTimeout(total=10)

    try:
        async with aiohttp.ClientSession(
            headers=headers,
            timeout=timeout
        ) as session:
            async with session.get(url) as resp:
                resp.raise_for_status()

                async with aiofiles.open(save_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        await f.write(chunk)

        # print(f"下载成功: {save_path}")

    except Exception as e:
        print(f"下载失败: {e}")
        
        
        

def basic_check(path: str, min_size_mb=1):
    if not os.path.exists(path):
        return False, "文件不存在"
    size = os.path.getsize(path)
    if size < min_size_mb * 1024 * 1024:
        return False, f"文件过小：{size} bytes"
    return True


def check_video_header(path: str):
    with open(path, "rb") as f:
        header = f.read(16)

    # 常见视频文件头
    if header.startswith(b"\x00\x00\x00") or b"ftyp" in header:
        return True
    if header.startswith(b"\x1A\x45\xDF\xA3"):
        return True
    return False


def check_video_ffprobe(path: str):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height",
        "-of", "default=noprint_wrappers=1",
        path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError as e:
        return False


def check_video(save_path: str):

    ok = basic_check(save_path)
    if not ok:
        return False

    ok = check_video_header(save_path)
    if not ok:
        return False

    ok = check_video_ffprobe(save_path)
    if not ok:
        return False

    return True



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
    media_path: str = Field(default="", description="图片路径、视频路径、图纸路径")
    chunk_source: str = Field(default="html", description="chunk的来源：document | image | video | audio | drawing | html")
    bbox: List[Any] = Field(default_factory=list, description="边界框坐标")
    page_idx: List[Any] = Field(default_factory=list, description="页码索引")
    others: Dict[str, Any] = Field(
        default_factory=dict,
        description="其他扩展字段"
    )

class ImageModel(BaseModel):
    """文档解析块返回类型"""
    chunk_id: str = Field(..., description="ID")
    kb_id: str = Field(..., description="知识库ID")
    img_path: str = Field(default="", description="图片路径")

    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式（兼容原有代码）
        使用 model_dump() 方法，包含所有字段和额外字段
        """
        return self.model_dump(include=None, exclude_none=False)


def save_chunks_to_jsonl(chunks: List[ChunkModel], save_path: str):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    with open(save_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n")


def load_chunks_from_jsonl(path: str) -> List[ChunkModel]:
    chunks = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                chunks.append(ChunkModel(**data))
            except Exception as e:
                print(f"[WARN] 第 {line_no} 行解析失败: {e}")
    return chunks

def load_img_chunks_from_jsonl(path: str) -> List[ImageModel]:
    chunks = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if data["bbox_type"]!="image":
                    continue
                data["kb_id"] = "tesla_manual_oss"
                data["img_path"] = data["media_path"]
                img_chunk = {
                    "chunk_id":data["chunk_id"],
                    "kb_id":data["kb_id"],
                    "img_path":data["media_path"]
                }
                chunks.append(ImageModel(**img_chunk))
            except Exception as e:
                print(f"[WARN] 第 {line_no} 行解析失败: {e}")
    return chunks


async def get_chunk(root_dir: str, media_output_path:str): 
    chunks = []
    update_time = str(datetime.utcnow() + timedelta(hours=8))
    
    for file in tqdm(os.listdir(root_dir)):
        json_path = os.path.join(root_dir, file)
        # json_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/outputs/source/驾驶位气囊线束总成 （（拆卸和更换））.json"
        if json_path.endswith(".json"):
            file_id = str(uuid4().hex)
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                if len(data["text"])<50:
                    continue
                chunk_id = str(uuid4().hex)
                
                chunks.append(ChunkModel(
                    chunk_id=chunk_id,
                    content=data["text"].replace("Torque Calculator\n", "").replace("请参阅\n", "请参阅").replace("请参阅\n", "请参阅"),
                    title=data["title"],
                    file_id=file_id,
                    file_path=data["url"],
                    update_time=update_time,
                    bbox_type="text",
                    media_path=""
                ))
                
                img_list = data["img"]
                unique_list = list(set(img_list))

                for img_url in unique_list:
                    # print('============',img_url)
                    save_path = os.path.join(media_output_path, f"{data["title"]}", f"{os.path.basename(img_url).split(".")[0]}.jpg")
                    try:
                        download_image(img_url, save_path)
                        # await download_image_async(img_url, save_path)
                        
                        if not is_image_ok(save_path):
                            continue
                            
                        chunk_id = str(uuid4().hex)
                        chunks.append(ChunkModel(
                            chunk_id=chunk_id,
                            content="",
                            title=data["title"],
                            file_id=file_id,
                            file_path=data["url"],
                            update_time=update_time,
                            bbox_type="image",
                            media_path=save_path
                        ))
                    except Exception as e:
                        print("图片下载或校验失败",e,img_url)
                        # continue
                
                for img_url in data["video"]:
                    save_path = os.path.join(media_output_path, f"{data["title"]}", f"{os.path.basename(img_url).split(".")[0]}.mp4")
                    try:
                        download_image(img_url, save_path)
                        # await download_image_async(img_url, save_path)

                        if not check_video(save_path):
                            continue
                            
                        chunk_id = str(uuid4().hex)
                        chunks.append(ChunkModel(
                            chunk_id=chunk_id,
                            content="",
                            title=data["title"],
                            file_id=file_id,
                            file_path=data["url"],
                            update_time=update_time,
                            bbox_type="video",
                            media_path=save_path
                        ))
                    except Exception as e:
                        print("视频下载或校验失败",e,img_url)
                        # continue
    return chunks


async def main():
    root_dir = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/outputs/source"
    media_output_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/outputs/media"
    save_chunks_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/chunks_html_final_oss.jsonl"
    collection_name = "tesla_manual_oss"
    # chunks = await get_chunk(root_dir, media_output_path=media_output_path)
    # save_chunks_to_jsonl(chunks,save_chunks_path)
    chunks = load_chunks_from_jsonl(save_chunks_path)
    
    print(f"共计 {len(chunks)} 个 chunks 准备入库")
    
    await MilvusDB.insert(collection_name=collection_name, chunks=chunks, summary=False)
    
    print("insert success")



async def image_insert():
    # save_chunks_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/chunks_html_final_oss.jsonl"
    # collection_name = "images"
        
    # chunks = load_img_chunks_from_jsonl(save_chunks_path)
    # await milvus_client.img_insert(collection_name=collection_name, chunks=chunks)
    
    img = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/outputs/media/3 代前控制器总成 （（拆卸和更换））/GUID-500EDC94-A579-425D-9B3D-956DB34F650A-online-en-US.jpg"
    res = milvus_client.img_search(img,'images')
    # res = await milvus_client.img_search(img,'images')
    # chunk_id = res[0]["chunk_id"]
    # collection_name = res[0]["kb_id"]
    # print(milvus_client.list_chunk_by_id(chunk_id,collection_name))
    print(res)
    

async def local_url():

    save_chunks_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/chunks_final.jsonl"
    save_new_chunks_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/chunks_html_final.jsonl"
    collection_name = "tesla_manual"
    
    html_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/outputs/html_process"
    
    chunks = load_chunks_from_jsonl(save_chunks_path)
    
    for chunk in chunks:
        title = chunk.title
        title = title.replace(" ","").replace("((","(").replace("))",")").replace("（（","(").replace("，","-").replace("））",")").replace("（","(").replace("）",")")
        title = title.replace("(","-").replace(")","")
        
        local_html_path = os.path.join(html_path, title+".html")
        chunk.title = title
        chunk.file_path = local_html_path.replace(" ","")
        
        # print(chunk)
        # break
        
    
    save_chunks_to_jsonl(chunks,save_new_chunks_path)



from pathlib import Path

async def check_exist():
    save_chunks_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/chunks_html_final.jsonl"
    chunks = load_chunks_from_jsonl(save_chunks_path)
    
    for chunk in chunks:
        path = Path(chunk.file_path)

        if path.exists():
            continue
        else:
            print("不存在---"+chunk.file_path+"---")

#     print(f"共计 {len(chunks)} 个 chunks 准备入库")

async def rename_url():
    from pathlib import Path
    # root_dir = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/outputs/html_process"
    root_dir = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/outputs/html_process"
    
    for file in os.listdir(root_dir):
        if file.endswith(".html"):
            p = Path(os.path.join(root_dir, file))
            # print(p)
            title = file.replace(" ","").replace("((","(").replace("))",")").replace("（（","(").replace("，","-").replace("））",")").replace("（","(").replace("）",")")
            title = title.replace("(","-").replace(")","")
            # print(title)
            p.rename(os.path.join(root_dir, title).strip())
    
    print("rename finished!")


if __name__ == "__main__":
    asyncio.run(main())
    # asyncio.run(rename_url())
    # asyncio.run(local_url())
    # asyncio.run(check_exist())
    asyncio.run(image_insert())
    
    
    
    
    
    # print(os.path.basename("/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/1234.jpg").split(".")[0])
    
    
    # download_image("https://service.tesla.cn/docs/Model3/ServiceManual/2024/zh-cn/img/torque.png","/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/1234.jpg")
