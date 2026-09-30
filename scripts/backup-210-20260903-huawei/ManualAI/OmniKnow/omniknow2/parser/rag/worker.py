import asyncio
import httpx
import traceback

from loguru import logger
from redis.asyncio import Redis
import os
from typing import List, Tuple
from pathlib import Path

from parser.utils import get_file_extension, get_parser
from parser import MineruParser
from vector_db import MilvusClient
from public import RedisClint, TaskStatus
from celery_app import app
from schema import ChunkModel, ImageModel


OFFICE_FORMATS = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
TEXT_FORMATS = {".txt", ".md"}


@app.task(
    name="tasks.document.parse_document",
    bind=True,
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def process_document(self, task_id: str):
    """
    Celery 不直接支持将 coroutine 返回为任务结果。提供一个同步 wrapper，
    使用 asyncio.run 执行内部的异步实现 `_process_document_async`。
    """
    return asyncio.run(_process_document_async(self, task_id))


async def _process_document_async(self, task_id: str):
    """
    解析文档的统一接口
    """
    task = None
    try:
        logger.info(f"任务处理: {task_id}")
        redis = RedisClint()

        task = await redis.get_task(task_id)
        if not task:
            logger.error(f"任务未找到: {task_id}")
            await redis.set_task_status(
                task_id=task_id,
                status=TaskStatus.failed,
                message="任务未找到"
            )
            await callback_task_fail(task_id, reason="任务未找到")
            return

        await redis.set_task_status(task_id, TaskStatus.running, "任务开始执行")
        logger.info(f"\n开始解析任务: {task_id}\n"
                    f"     任务详情: {task}")

        # 检查文件是否存在
        if not os.path.exists(task.file_path):
            logger.error(f"文件不存在: {task.file_path}")
            await redis.set_task_status(
                task_id=task.id,
                status=TaskStatus.failed,
                message="文件不存在"
            )
            await callback_task_fail(task_id, reason="文件不存在")
            return

        # 检查是否为文件（而非目录）
        if not os.path.isfile(task.file_path):
            logger.error(f"路径不是文件: {task.file_path}")
            await redis.set_task_status(
                task_id=task.id,
                status=TaskStatus.failed,
                message="提供的路径不是文件"
            )
            await callback_task_fail(task_id, reason="提供的路径不是文件")
            return

        # 转换文件
        source_file_path = task.file_path
        file_ext = get_file_extension(source_file_path)
        if task.method == "normal" or file_ext == ".pdf":
            processed_file_path = None
        elif task.method == "smart":
            processed_file_path = await convert_document(task, redis)
        else:
            logger.error(f"不支持的解析方法: {task.method}")
            await redis.set_task_status(
                task_id=task.id,
                status=TaskStatus.failed,
                message=f"不支持的解析方法: {task.method}"
            )
            await callback_task_fail(task_id, reason=f"不支持的解析方法: {task.method}")
            return
        task.file_path = str(processed_file_path) if processed_file_path else source_file_path

        # 解析文件
        chunks, doc_summary = await parse_document(task, redis)
        result_chunks = [chunk.model_dump() for chunk in chunks]
        task.chunk_count = len(chunks)
        # summary = chunks[-1].content if task.title_correction else ""
        task.img_collection_name = "images2"
        task.summary_collection_name = "chapter_summary"
        # 转换并上传到向量数据库
        milvus = MilvusClient()

        logger.info(f"正在删除向量库 {task.collection_name} 中 {task.file_id}的数据")
        await milvus.delete_doc_by_id(collection_name=task.collection_name,file_id=task.file_id)
        
        # await upload_milvus(task, chunks, doc_summary, redis)

        result = {
            "length": len(result_chunks),
            "source_file_path": source_file_path,
            "processed_file_path": processed_file_path,
            "chunks": result_chunks,
            "summary": doc_summary.content if doc_summary else ""
        }
        task.result = result
        await redis.return_task_result(
            task_id=task.id,
            result=result
        )

        await callback_task_complete(task.id)

    except Exception as e:
        traceback.print_exc()
        logger.error(f"解析任务: {task_id} 执行失败\n"
                     f"任务信息: {task if task else '获取任务信息失败'}\n"
                     f"错误: {str(e)}")
        redis = RedisClint()
        await redis.set_task_status(
            task_id=task_id,
            status=TaskStatus.failed,
            message=f"任务执行失败: {str(e)}"
        )
        # 通知服务端同步更新 DB 文档状态为「解析失败」
        await callback_task_fail(task_id, reason=f"任务执行失败: {str(e)[:200]}")


async def parse_document(task, redis) -> List[ChunkModel]:
    logger.info(f"开始解析文件: {task.file_path}")

    parser = get_parser(task.file_path, task.method)

    chunks,doc_summary = await parser.parse(
        file_id=task.file_id,
        file_path=task.file_path,
        output_dir=Path(task.file_path).parent.joinpath("images"),
        summary=task.summary,
        chunk_size=task.max_chunk_size,
        chunk_overlap=task.chunk_overlap,
        delimiters=task.delimiters,
        method=task.method,
        backend=task.backend,
        table=task.table,
        start_page=task.start_page,
        end_page=task.end_page,
        title_correction=task.title_correction,  
    )

    logger.info(f"任务 {task.id}: 解析成功, 生成 {len(chunks)} 个块")
    await redis.set_task_status(
        task_id=task.id,
        status=TaskStatus.parsed,
        message="文件解析成功"
    )
    return chunks,doc_summary


async def convert_document(task, redis):
    """
    文档格式转换的统一接口
        doc、docx、 ppt、pptx、xls、xlsx、txt、md --> pdf
        png、jpeg、jpg、bmp、tiff、tif、gif、webp --> png
    """
    file_path = Path(task.file_path)
    output_dir = Path(file_path.parent.joinpath("processed"))

    ext = file_path.suffix.lower()
    logger.info("文件格式为:--{}--".format(ext))

    if ext in OFFICE_FORMATS:
        logger.warning(
            f"Warning: Office document detected ({ext}). "
            f"MinerU 2.0 requires conversion to PDF first."
        )
        convert_path = MineruParser.convert_office_to_pdf(file_path, str(output_dir))
    elif ext in TEXT_FORMATS:
        convert_path = MineruParser.convert_text_to_pdf(file_path, str(output_dir))
    elif ext in [".png", ".jpeg", ".jpg", ".bmp", ".tiff", ".tif", ".gif", ".webp"]:
        parser = get_parser(str(file_path))
        logger.info(parser)
        convert_path = await parser.convert_image(
            image_path=file_path,
            output_dir=output_dir
        )
    else:
        logger.error(f"不支持的文件格式: {ext}")
        raise Exception(f"不支持的文件格式: {ext}")

    logger.info(f"任务 {task.id}: 文件转换成功: {convert_path}")
    await redis.set_task_status(
        task_id=task.id,
        status=TaskStatus.converted,
        message="文件格式转换成功"
    )
    return convert_path


async def upload_milvus(task, chunks, doc_summary,redis):
    """向量数据库写入"""
    milvus = MilvusClient()
    
    logger.info(f"正在删除向量库 {task.collection_name} 中 {task.file_id}的数据")
    await milvus.delete_doc_by_id(collection_name=task.collection_name,file_id=task.file_id)
    # await milvus.document_insert(collection_name=task.collection_name, chunks=chunks)
    # img_chunks = []
    # for data in chunks:
    #     if data.bbox_type!="image":
    #         continue
    #     img_chunk = {
    #         "chunk_id":data.chunk_id,
    #         "kb_id":task.collection_name,
    #         "img_path":data.media_path
    #     }
    #     img_chunks.append(ImageModel(**img_chunk))
    # logger.info("图片chunk个数为：",len(img_chunks))
    # await milvus.img_insert(collection_name=task.img_collection_name, chunks=img_chunks)

    # if doc_summary:
    #     await milvus.summary_insert(collection_name=task.summary_collection_name, chunk=doc_summary)
    logger.info(f"任务 {task.id} 解析成功，插入到{task.collection_name}知识库中，生成 {len(chunks)} 个块")
    # 标记向量写入完成；最终 completed 状态由服务端 callback 确认后统一设置
    await redis.set_task_status(
        task_id=task.id,
        status=TaskStatus.vectorized,
        message="文件解析并上传向量数据库成功"
    )
    return True


def _get_callback_headers() -> dict:
    """构造回调请求头，若配置了 CALLBACK_SECRET 则附加鉴权 Token"""
    headers = {}
    secret = os.getenv("CALLBACK_SECRET")
    if secret:
        headers["X-Callback-Token"] = secret
    return headers


async def callback_task_complete(task_id: str, max_retry: int = 3):
    """
    通知服务端任务成功完成，触发 DB 状态同步。
    失败时按指数退避重试，超过最大次数后记录日志。
    """
    callback_host = os.getenv("CALLBACK_HOST")
    callback_url = f"{callback_host}/tasks/{task_id}/complete"
    headers = _get_callback_headers()
    index = 0
    while True:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url=callback_url, headers=headers)
                if res.status_code == 200 or res.status_code == 202:
                    logger.info(f"任务完成回调成功: {task_id}")
                    return
                else:
                    logger.error(
                        f"任务完成回调失败: {task_id}, "
                        f"状态码: {res.status_code}, 响应: {res.text}"
                    )
                    raise Exception(f"状态码: {res.status_code}")
        except Exception as e:
            traceback.print_exc()
            logger.error(f"任务完成回调异常: {task_id}, 错误: {str(e)}")
            index += 1
            if index >= max_retry:
                logger.error(f"任务完成回调达到最大重试次数: {task_id}")
                return
            await asyncio.sleep(2 ** index)


async def callback_task_fail(task_id: str, reason: str = "", max_retry: int = 3):
    """
    通知服务端任务失败，触发 DB 文档状态同步为「解析失败」。
    失败时按指数退避重试，超过最大次数后记录日志。
    """
    callback_host = os.getenv("CALLBACK_HOST")
    callback_url = f"{callback_host}/tasks/{task_id}/fail"
    headers = _get_callback_headers()
    params = {"reason": reason} if reason else {}
    index = 0
    while True:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url=callback_url, headers=headers, params=params)
                if res.status_code == 200:
                    logger.info(f"任务失败回调成功: {task_id}")
                    return
                else:
                    logger.error(
                        f"任务失败回调失败: {task_id}, "
                        f"状态码: {res.status_code}, 响应: {res.text}"
                    )
                    raise Exception(f"状态码: {res.status_code}")
        except Exception as e:
            logger.error(f"任务失败回调异常: {task_id}, 错误: {str(e)}")
            index += 1
            if index >= max_retry:
                logger.error(f"任务失败回调达到最大重试次数: {task_id}")
                return
            await asyncio.sleep(2 ** index)
