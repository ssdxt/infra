from uuid import UUID, uuid4

from botocore.exceptions import EndpointConnectionError
from fastapi import UploadFile

from core.acl.acl import ACL
from core.config import settings
from core.dependencies import RequestContext
from exceptions.errors.resource import (
    FileTypeNotSupportedError,
    ImageUploadError,
    SpaceAccessError,
)
from image.error import ImageNotExistedError
from image.repository import ImgRepository
from image.schema import ALLOWED_EXTENSIONS, ImgFatherType
from repository.space import SpaceRepository
from storage import get_storage
from storage.paths import space_image_key
from utils.log import logger


class ImgService:
    def __init__(self, ctx: RequestContext):
        self.session = ctx.db
        self.user = ctx.user
        self.storage = get_storage()
        self.acl = ACL(ctx.db)
        self.space_repo = SpaceRepository(ctx.db)
        self.img_repo = ImgRepository(ctx.db)

    async def _check_space_access(self, space_id: UUID, min_role: str) -> None:
        await self.space_repo.get(space_id)
        has_access = await self.acl.check_space_role(
            user_id=self.user.uuid,
            space_id=space_id,
            min_role=min_role,
        )
        if not has_access:
            raise SpaceAccessError

    @staticmethod
    def _resolve_extension(image: UploadFile) -> str:
        filename = image.filename or ""
        if "." in filename:
            ext = filename.rsplit(".", 1)[-1].lower()
            if ext in ALLOWED_EXTENSIONS:
                return ext

        content_type = (image.content_type or "").lower()
        content_type_map = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/gif": "gif",
            "image/bmp": "bmp",
            "image/webp": "webp",
        }
        if content_type in content_type_map:
            return content_type_map[content_type]

        raise FileTypeNotSupportedError(file_type=filename or content_type or "unknown")

    async def upload_images(
        self,
        space_id: UUID,
        image: UploadFile,
        expire: int,
    ) -> dict:
        await self._check_space_access(space_id, min_role="viewer")

        ext = self._resolve_extension(image)
        filename_stem = uuid4().hex[:16]
        storage_key = space_image_key(space_id, filename_stem, ext)
        relative_path = storage_key.removeprefix(f"{space_id}/")

        try:
            # 确保事务一致性
            storage_result = await self.storage.save_space_image(
                space_id=space_id,
                file=image,
                filename_stem=filename_stem,
                ext=ext,
                ttl=expire,
            )
            img = await self.img_repo.create_image(space_id, relative_path)
            url = storage_result["url"] if settings.env.safe else storage_result["path"]
            expire = storage_result["expires_in"] if settings.env.safe else 0
            return {
                "uuid": str(img.uuid),
                "url": url,
                "expires_in": expire
            }
        except EndpointConnectionError:
            logger.error(f"图片上传失败，无法连接到存储服务: space_id={space_id}")
            raise ImageUploadError

    async def upload_logo(
        self,
        space_id: UUID,
        image: UploadFile,
        ) -> dict:
        await self._check_space_access(space_id, min_role="member")

        ext = self._resolve_extension(image)
        filename_stem = uuid4().hex[:16]
        storage_key = space_image_key(space_id, filename_stem, ext)
        relative_path = storage_key.removeprefix(f"{space_id}/")

        try:
            # 确保事务一致性
            storage_result = await self.storage.save_space_image(
                space_id=space_id,
                file=image,
                filename_stem=filename_stem,
                ext=ext,
                ttl=24 * 3600 * 7 ,  # logo默认过期时间设置为7天
            )
            img = await self.img_repo.create_image(space_id, relative_path)
            url = storage_result["url"] if settings.env.safe else storage_result["path"]
            expire = storage_result["expires_in"] if settings.env.safe else 0
            return {
                "uuid": str(img.uuid),
                "url": url,
                "expires_in": expire
            }
        except EndpointConnectionError:
            logger.error(f"图片上传失败，无法连接到存储服务: space_id={space_id}")
            raise ImageUploadError
        # try:
        #     image_record = await self.img_repo.create_image(
        #         space_id=space_id,
        #         father_type=ImgFatherType.kbase.value,
        #         father_id=space_id,
        #         path=relative_path,
        #     )
        #     await self.session.commit()
        #     await self.session.refresh(image_record)
        # except Exception:
        #     await self.session.rollback()
        #     raise
        #
        # return {
        #     "image_id": str(image_record.uuid),
        #     "url": storage_result["url"],
        #     "expires_in": storage_result["expires_in"],
        #     "path": relative_path,
        # }

    async def get_image_url(
        self,
        space_id: UUID,
        image_id: UUID,
        expire: int = 3600,
    ) -> dict:
        await self._check_space_access(space_id, min_role="viewer")

        image_record = await self.img_repo.get_image(space_id, image_id)
        if not image_record:
            raise ImageNotExistedError(image_id)

        url = await self.storage.presign(space_id, image_record.path, ttl=expire)
        return {
            "image_id": str(image_record.uuid),
            "url": url,
            "expires_in": expire,
            "path": image_record.path,
        }

