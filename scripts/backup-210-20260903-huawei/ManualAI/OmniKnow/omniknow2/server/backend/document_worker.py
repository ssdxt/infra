"""
文档解析 Celery Worker（HTTP 版）

与 parser/rag 模块完全解耦，通过 HTTP 调用 parser API (api.py) 完成：
  - 文档格式转换  POST /convert_document
  - 文档解析      POST /parse_document
  - 向量删除      POST /doc_delete_by_id
  - 向量写入      POST /document_insert
  - 摘要写入      POST /summary_insert

任务数据通过 Redis Hash (task:{task_id}) 传递，与 dispatcher.py 保持兼容。
"""

import asyncio
import os
import time
from httpx import HTTPStatusError
from pathlib import Path
from typing import Any

import httpx
import redis as sync_redis
from loguru import logger

from ext.celery_app import celery_app
from ext.redis_client import RedisClient
from core.config import settings
from schemas.task import Task, TaskStatus, SkipConvertExt
from embed.client import EmbedClient


PARSER_URL = settings.parser.api_url  # e.g. http://127.0.0.1:8008

OFFICE_FORMATS = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
TEXT_FORMATS = {".txt", ".md"}
IMAGE_FORMATS = {".png", ".jpeg", ".jpg", ".bmp", ".tiff", ".tif", ".gif", ".webp"}
VIDEO_FORMATS = {".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv"}

# 文档类型常量
DOC_TYPE_DOCUMENT = "document"
DOC_TYPE_VIDEO = "video"


def detect_resource_type(file_path: str) -> str:
    """根据文件扩展名识别文档类型，新增类型在此扩展即可。"""
    ext = Path(file_path).suffix.lower()
    if ext in VIDEO_FORMATS:
        return DOC_TYPE_VIDEO
    return DOC_TYPE_DOCUMENT

# ──────────────────────────────────────────────
# 分布式信号量（基于 Redis Sorted Set）
# ──────────────────────────────────────────────
SEMAPHORE_KEY = "backend:semaphore:parse_tasks"
SEMAPHORE_TIMEOUT = 7200  # 单个任务最长持有信号量时间（秒），防止死锁


def _get_sync_redis() -> sync_redis.Redis:
    """获取同步 Redis 连接（用于 Celery 同步入口）"""
    return sync_redis.Redis(
        host=settings.redis.host,
        port=settings.redis.port,
        password=settings.redis.password,
        db=settings.redis.task_db,
        decode_responses=True,
    )


def _try_acquire_semaphore(r: sync_redis.Redis, task_id: str, max_concurrent: int) -> bool:
    """尝试获取分布式信号量槽位，返回是否成功"""
    now = time.time()
    # 清理超时的槽位（防止死锁）
    r.zremrangebyscore(SEMAPHORE_KEY, 0, now - SEMAPHORE_TIMEOUT)
    current = r.zcard(SEMAPHORE_KEY)
    if current >= max_concurrent:
        return False
    r.zadd(SEMAPHORE_KEY, {task_id: now})
    return True


def _release_semaphore(r: sync_redis.Redis, task_id: str):
    """释放信号量槽位"""
    r.zrem(SEMAPHORE_KEY, task_id)


# ──────────────────────────────────────────────
# Celery Task 入口
# ──────────────────────────────────────────────

@celery_app.task(
    name="backend.document_worker.parse_document",
    bind=True,
    autoretry_for=(TimeoutError, ConnectionError),
    max_retries=None,
)
def process_document(self, task_id: str):
    """
    通过 Redis 分布式信号量控制并发：获取不到槽位时 retry 回队列，
    不阻塞 worker 进程。
    """
    max_concurrent = settings.parser.max_concurrent_tasks
    logger.info(f"尝试获取信号量槽位，当前并发限制: {max_concurrent}")
    r = _get_sync_redis()
    try:
        if not _try_acquire_semaphore(r, task_id, max_concurrent):
            current = r.zcard(SEMAPHORE_KEY)
            logger.info(
                f"并发已满 ({current}/{max_concurrent})，"
                f"任务 {task_id} 将在 10s 后重试"
            )
            raise self.retry(countdown=10, max_retries=None)
    finally:
        r.close()

    try:
        return asyncio.run(_process_document_async(self, task_id))
    finally:
        r2 = _get_sync_redis()
        try:
            _release_semaphore(r2, task_id)
            logger.debug(f"任务 {task_id} 已释放信号量槽位")
        finally:
            r2.close()


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

async def _process_document_async(self, task_id: str):
    """解析文档的统一接口"""
    task = None
    try:
        logger.info(f"任务处理: {task_id}")
        redis = RedisClient()

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

        if not os.path.isfile(task.file_path):
            logger.error(f"路径不是文件: {task.file_path}")
            await redis.set_task_status(
                task_id=task.id,
                status=TaskStatus.failed,
                message="提供的路径不是文件"
            )
            await callback_task_fail(task_id, reason="提供的路径不是文件")
            return

        # 按文档类型分发到对应 handler
        doc_type = detect_resource_type(task.file_path)
        logger.info(f"资源类型识别: {doc_type}")
        handler = DOC_HANDLERS.get(doc_type)
        if handler is None:
            logger.error(f"不支持的文档类型: {doc_type}")
            await redis.set_task_status(
                task_id=task.id,
                status=TaskStatus.failed,
                message=f"不支持的文档类型: {doc_type}"
            )
            await callback_task_fail(task_id, reason=f"不支持的文档类型: {doc_type}")
            return

        logger.info(f"任务 {task.id}: 文档类型={doc_type}, 使用 handler={handler.__class__.__name__}")
        try:
            parse_result = await handler.process(task, redis)
        except UnsupportedMethodError as e:
            logger.error(f"任务 {task.id}: {e}")
            await redis.set_task_status(
                task_id=task.id,
                status=TaskStatus.failed,
                message=str(e)
            )
            await callback_task_fail(task_id, reason=str(e))
            return
        # 统一回写：handler 返回什么就存什么；result 形状由各 handler 与对应 finalizer 自洽
        result = {
            **parse_result,
            "doc_type": doc_type,
            "source_file_path": parse_result.get("source_file_path", task.file_path),
        }
        task.result = result
        task.img_collection_name = "images2"
        task.summary_collection_name = "chapter_summary"
        await redis.return_task_result(
            task_id=task.id,
            result=result,
        )
        await callback_task_complete(task.id)
        return

    except Exception as e:
        logger.error(f"解析任务: {task_id} 执行失败\n"
                     # f"任务信息: {task if task else '获取任务信息失败'}\n"
                     f"错误: {str(e)}")
        redis = RedisClient()
        await redis.set_task_status(
            task_id=task_id,
            status=TaskStatus.failed,
            message=f"任务执行失败: {str(e)}"
        )
        await callback_task_fail(task_id, reason=f"任务执行失败: {str(e)[:200]}")


# ──────────────────────────────────────────────
# Handler 注册表（按文档类型分发）
# ──────────────────────────────────────────────

class UnsupportedMethodError(Exception):
    """解析方法不受当前 handler 支持。"""


class DocHandler:
    """
    文档类型 handler 基类。

    子类 `process()` 返回 free-form dict（每种 doc_type 形状可不同）。
    返回内容会与 `doc_type` 字段合并后整体写入 Redis 任务结果，
    供回调端对应 finalizer 消费 —— handler 与 finalizer 成对约定字段契约。

    通用约定：建议在返回中包含 `source_file_path`，便于 worker / 回调端
    统一做本地清理；其余字段由各类型自由扩展。
    """

    async def process(self, task: Task, redis: RedisClient) -> dict[str, Any]:
        raise NotImplementedError


DOC_HANDLERS: dict[str, DocHandler] = {}


def register_handler(doc_type: str):
    """将 handler 注册到指定文档类型，新增类型只需添加一个 @register_handler。"""
    def deco(cls: type[DocHandler]):
        DOC_HANDLERS[doc_type] = cls()
        return cls
    return deco


@register_handler(DOC_TYPE_DOCUMENT)
class DocumentHandler(DocHandler):
    """普通文档：可选格式转换 → 文本切片解析。"""

    async def process(self, task: Task, redis: RedisClient) -> dict[str, Any]:
        source_file_path = task.file_path
        file_ext = Path(source_file_path).suffix.lower()

        if task.method == "normal" or file_ext in SkipConvertExt:
            processed_file_path = None
        elif task.method == "smart":
            processed_file_path = await convert_document(task, redis)
        else:
            raise UnsupportedMethodError(f"不支持的解析方法: {task.method}")

        parse_file_path = str(processed_file_path) if processed_file_path else source_file_path
        data = await parse_document(task, parse_file_path, redis)
        chunks = data.get("data", [])
        return {
            "chunks": chunks,
            "length": len(chunks),
            "summary": data.get("doc_summary", ""),
            "source_file_path": source_file_path,
            "processed_file_path": processed_file_path,
        }


@register_handler(DOC_TYPE_VIDEO)
class VideoHandler(DocHandler):
    """
    视频：调用视频解析接口，结果直接透传给 finalize_parse_video_task。

    返回字段（与 video finalizer 对齐）：
      - embeddings:       parser 原始响应（保留全部字段供后处理消费）
      - source_file_path: 源视频本地路径，用于回调后清理
    """

    async def process(self, task: Task, redis: RedisClient) -> dict[str, Any]:
        data = await parse_video(task, redis)
        return {
            "embeddings": data,
            "source_file_path": task.file_path,
        }


# ──────────────────────────────────────────────
# 文档转换 → POST /convert_document
# ──────────────────────────────────────────────

async def convert_document(task: Task, redis: RedisClient) -> str:
    """通过 parser API 进行文档格式转换，返回转换后文件路径"""
    try:
        file_path = Path(task.file_path)
        output_dir = str(file_path.parent / "processed")

        async with httpx.AsyncClient(timeout=1800) as client:
            resp = await client.post(f"{PARSER_URL}/convert_document", json={
                "file_path": str(file_path),
                "output_dir": output_dir,
            })
            resp.raise_for_status()
            data = resp.json()

        convert_path = data["file_path"]
        logger.info(f"任务 {task.id}: 文件转换成功: {convert_path}")
        await redis.set_task_status(
            task_id=task.id,
            status=TaskStatus.converted,
            message="文件格式转换成功"
        )
        return convert_path
    except HTTPStatusError as e:
        if e.response.status_code == 400:
            logger.error(f"任务 {task.id}: 不支持的文件格式或转换参数错误: {e.response.json()}")
        if e.response.status_code == 404:
            logger.error(f"任务 {task.id}: 文件路径不存在，请重新上传文件: {task.file_path}")
        elif e.response.status_code == 500:
            logger.error(f"任务 {task.id}: 文件转换失败，服务器内部错误: {e.response.json()}")
        else:
            logger.error(f"任务 {task.id}: 文件转换失败，HTTP 错误: {str(e)}")
        raise Exception("文件转换失败")


# ──────────────────────────────────────────────
# 文档解析 → POST /parse_document
# ──────────────────────────────────────────────

async def parse_document(task: Task, file_path: str, redis: RedisClient) -> dict[str, Any]:
    """
    通过 parser API 解析文档，返回 (chunks, doc_summary)。
    """
    logger.info(f"开始解析文件: {file_path}")

    method = task.method
    if method == "normal":
        logger.info(f"使用普通解析方法")
    elif method == "smart":
        logger.info(f"使用智能解析方法")

    output_dir = str(Path(file_path).parent / "images")
    chunk_source = getattr(task, "chunk_source", "document")
    try:
        async with httpx.AsyncClient(timeout=3600) as client:
            resp = await client.post(f"{PARSER_URL}/parse_document", json={
                "file_id": task.file_id,
                "file_path": file_path,
                "summary": task.summary,
                "method": task.method,
                "backend": task.backend,
                "table": task.table,
                "chunk_size": task.max_chunk_size,
                "chunk_overlap": task.chunk_overlap,
                "delimiters": task.delimiters,
                "include_parent_titles": task.parent_titles,
                "start_page": task.start_page,
                "end_page": task.end_page,
                "title_correction": task.title_correction,
                "output_dir": output_dir,
                "chunk_source": chunk_source,
            })
            resp.raise_for_status()
            data = resp.json()
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.error(f"任务 {task.id}: 解析接口未实现或文件路径不正确，请重新上传文件: {task.file_path}")
        elif e.response.status_code == 500:
            logger.error(f"任务 {task.id}: 文件解析失败，服务器内部错误: {str(e)}")
        else:
            logger.error(f"任务 {task.id}: 文件解析失败，HTTP 错误: {str(e)}")
        raise Exception("文件解析失败")
    chunks = data.get("data", [])
    # doc_summary = data.get("doc_summary", None)

    logger.info(f"任务 {task.id}: 解析成功, 生成 {len(chunks)} 个块")
    await redis.set_task_status(
        task_id=task.id,
        status=TaskStatus.parsed,
        message="解析完毕，等待入库"
    )
    return data


# ──────────────────────────────────────────────
# 视频解析 → POST /parse_video
# ──────────────────────────────────────────────

async def parse_video(task: Task, redis: RedisClient):
    """
    通过 Embeding模型获取标题向量

    直接上传Milvus
    """
    file_name = task.file_name
    logger.info(f"开始解析视频: {file_name}")

    embed_client = EmbedClient()
    try:
        data = await embed_client.embed_data(file_name)
        logger.info(f"视频解析成功: {file_name}")
        await redis.set_task_status(
            task_id=task.id,
            status=TaskStatus.parsed,
            message="视频标题向量化成功，等待入库"
        )

        return data
    except Exception as e:
        logger.error(f"视频解析失败: {file_name}, 错误: {str(e)}")
        raise Exception("视频解析失败")




# ──────────────────────────────────────────────
# 回调通知
# ──────────────────────────────────────────────

def _get_callback_headers() -> dict:
    """构造回调请求头，若配置了 callback_secret 则附加鉴权 Token"""
    headers = {}
    secret = settings.parser.callback_secret
    if secret:
        headers["X-Callback-Token"] = secret
    return headers


async def callback_task_complete(task_id: str, max_retry: int = 3):
    """
    通知服务端任务成功完成，触发 DB 状态同步。
    失败时按指数退避重试，超过最大次数后记录日志。
    """
    callback_host = settings.parser.callback_host
    if not callback_host:
        logger.warning(f"未配置 callback_host，跳过完成回调: {task_id}")
        return

    callback_url = f"{callback_host}/tasks/{task_id}/complete"
    headers = _get_callback_headers()
    index = 0
    while True:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url=callback_url, headers=headers)
                if res.status_code in (200, 202):
                    logger.info(f"任务完成回调成功: {task_id}")
                    return
                else:
                    logger.error(
                        f"任务完成回调失败: {task_id}, "
                        f"状态码: {res.status_code}, 响应: {res.text}"
                    )
                    raise Exception(f"状态码: {res.status_code}")
        except Exception as e:
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
    callback_host = settings.parser.callback_host
    if not callback_host:
        logger.warning(f"未配置 callback_host，跳过失败回调: {task_id}")
        return

    callback_url = f"{callback_host}/tasks/{task_id}/fail"
    headers = _get_callback_headers()
    params = {"reason": reason} if reason else {}
    index = 0
    while True:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(url=callback_url, headers=headers, params=params)
                if res.status_code == 200:
                    logger.info(f"任务失败回调: {task_id}")
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
