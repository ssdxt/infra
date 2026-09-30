
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from image.model import Image


class ImgRepository:
    def __init__(self, db: AsyncSession):
        self.session = db

    async def create_image(
        self,
        space_id: UUID,
        path: str,
    ) -> Image:
        image = Image(
            space_id=space_id,
            path=path,
            status=1,
        )
        self.session.add(image)
        await self.session.flush()
        return image

    async def get_image(self, space_id: UUID, image_id: UUID) -> Image | None:
        result = await self.session.execute(
            select(Image).where(
                Image.space_id == space_id,
                Image.uuid == image_id,
                Image.status == 1,
            )
        )
        return result.scalar_one_or_none()
