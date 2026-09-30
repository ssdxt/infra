from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from chunks.repository import ChunkRepository
from core.dependencies import RequestContext
from exceptions.errors.resource import ChunkIndexNotExistedError
from storage import get_storage
from utils.log import logger


class ChunkService:
    def __init__(self, session: AsyncSession):
        self.chunk_repository = ChunkRepository(session)

    async def get_chunks(self, resource_id: UUID):
        return await self.chunk_repository.get_chunks_by_resource(resource_id)

    async def get_chunks_count(self, resource_id: UUID):
        return await self.chunk_repository.get_chunks_count_by_resource(resource_id)

    async def clear_chunks(self, space_id, kbase_id, resource_id: UUID):
        logger.info(f"正在清理资源 {resource_id} 原chunks")
        return await self.chunk_repository.clear_chunks_by_resource(space_id, kbase_id, resource_id)

    async def insert_chunks(self, space_id: UUID, kbase_id: UUID, resource_id: UUID, chunks: list):
        return await self.chunk_repository.insert_chunks_by_resource(space_id, kbase_id, resource_id, chunks)

    async def get_chunk_detail_by_index(self, space_id: UUID, kbase_id: UUID, resource_id: UUID, chunk_index: int):
        chunk = await self.chunk_repository.get_chunk_detail_by_index(space_id, kbase_id, resource_id, chunk_index)
        if not chunk:
            logger.warning(f"未找到资源 {resource_id} 的第 {chunk_index} 个chunk")
            raise ChunkIndexNotExistedError(chunk_index)

        if chunk.media_path and chunk.media_path.startswith(str(space_id)):
            object_path = chunk.media_path.split("/", maxsplit=1)[-1]
            chunk.media_path = await get_storage().presign(space_id, object_path, ttl=3600)

        return {
            "uuid": chunk.uuid,
            "doc_id": chunk.doc_id,
            "chunk_id": chunk.chunk_id,
            "content": chunk.content,
            "summary": chunk.summary,
            "others": chunk.others,
            "title": chunk.title,
            "chunk_index": chunk.index,
            "page_idx": chunk.page_idx,
            "bbox_type": chunk.bbox_type,
            "bbox": chunk.bbox,
            "media_path": chunk.media_path,
            "created_at": chunk.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": chunk.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
