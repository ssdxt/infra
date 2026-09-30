from uuid import UUID

from typing import Sequence

from tqdm import tqdm

from db.models.rag import Chunk
from utils.log import logger

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession


class ChunkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.chunks: Sequence[Chunk] = []

    async def get_chunks_by_resource(self, resource_id) -> Sequence[Chunk]:
        res = await self.session.execute(
            select(Chunk).where(Chunk.doc_id == resource_id)
        )
        self.chunks = res.scalars().all()
        return self.chunks

    async def clear_chunks_by_resource(self, spaec_id: UUID, kbase_id: UUID, resource_id) -> bool:
        await self.session.execute(
            delete(Chunk).where(
                Chunk.space_id == spaec_id,
                Chunk.kbase_id == kbase_id,
                Chunk.doc_id == resource_id)
        )
        self.chunks = []
        await self.session.flush()
        return True

    async def get_chunks_count_by_resource(self, resource_id) -> int:
        res = await self.session.execute(
            select(func.count()).select_from(Chunk).where(Chunk.doc_id == resource_id)
        )
        return res.scalar_one()

    async def get_chunk_detail_by_index(self, space_id: UUID, kbase_id: UUID, resource_id: UUID, chunk_index: int) -> Chunk | None:
        res = await self.session.execute(
            select(Chunk).where(
                Chunk.space_id == space_id,
                Chunk.kbase_id == kbase_id,
                Chunk.doc_id == resource_id,
                Chunk.index == chunk_index
            )
        )
        chunks = res.scalar_one_or_none()
        return chunks

    async def insert_chunks_by_resource(self, space_id: UUID, kbase_id: UUID, resouce_id: UUID, chunks: list):
        """批量写入分块"""
        chunk_objs = [
            Chunk(
                space_id=space_id,
                kbase_id=kbase_id,
                doc_id=resouce_id,
                chunk_id=chunk.get("chunk_id"),
                content=chunk.get("content"),
                bbox_type=chunk.get("bbox_type"),
                index=chunk.get("chunk_index"),
                title=chunk.get("title"),
                summary=chunk.get("summary"),
                media_path=chunk.get("media_path"),
                source=chunk.get("source"),
                bbox=chunk.get("bbox"),
                page_idx=chunk.get("page_idx"),
                others=chunk.get("others"),
            )
            for chunk in tqdm(chunks, desc="构建分块对象", unit="chunk")
        ]
        self.session.add_all(chunk_objs)
        await self.session.flush()