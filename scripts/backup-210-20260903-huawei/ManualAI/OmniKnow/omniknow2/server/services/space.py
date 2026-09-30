from fastapi import UploadFile, HTTPException
from botocore.exceptions import EndpointConnectionError

from core.acl.acl import ACL
from core.acl.schema import ResourceType
from repository import SpaceRepository, UserRepository, KBaseRepository
from audit.repository import AuditRepository
from schemas import SpaceCreateSchema, SpaceCreateReponseSchema, SpaceInviteSchema, SpaceUpdateSchema, Action
from schemas.space import SpaceMemberRoleUpdateRequest
from utils import hash_md5, logger
from exceptions.errors.resource import (
    SpaceNotExistedError, SpaceExistedError, SpaceAccessError,
    SpaceMemberNotFoundError, SpaceOwnerCannotBeRemovedError
)
from exceptions.errors.users import UserNotExistedError
from exceptions.errors.resource import FileTypeNotSupportedError, ImageUploadError
from core.dependencies import RequestContext
from storage import get_storage

from datetime import datetime
from uuid import UUID


class SpaceService:
    def __init__(self, ctx: RequestContext):
        self.db = ctx.db
        self.user = ctx.user
        self.request = ctx.request
        self.space_repo = SpaceRepository(self.db)
        self.user_repository = UserRepository(self.db)
        self.kbase_repository = KBaseRepository(self.db)
        self.acl = ACL(self.db)
        self.activity_log = AuditRepository(self.db)
        self.storage = get_storage()

    async def get_space_list_by_user(self):
        """获取用户的空间列表"""
        user = await self.user_repository.get(self.user.uuid)
        if not user:
            raise UserNotExistedError
        spaces = await self.space_repo.get_spaces_by_user(user.uuid)
        return {
            "spaces": [
                {
                    "uuid": space.uuid,
                    "name": space.name,
                    "logo": space.logo,
                    "description": space.description,
                    "code": space.code,
                    "created_at": space.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for space in spaces
            ]
        }

    async def create_space(self, user_id, space: SpaceCreateSchema):
        """创建空间"""
        if self.user != user_id:
            # 后续完善管理员为其他用户创建空间的功能
            pass
        logger.info(f"用户{self.user.uuid} 为用户 {user_id} 创建空间：{space.name}")
        name = space.name
        async with self.db.begin():
            if await self.space_repo.exists_by_name(self.user, name):
                raise SpaceExistedError(space_name=name)

            code = hash_md5(str(name) + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            space = await self.space_repo.create(name, space.logo, space.description, self.user.uuid, code)
            await self.space_repo.add_user_to_space(space, self.user)

        data = SpaceCreateReponseSchema(
            uuid=space.uuid,
            name=space.name,
            logo=space.logo,
            description=space.description,
            code=space.code
        )

        # 创建对应的存储命名空间
        await self.storage.ensure_space_bucket(space.uuid)

        return data

    async def update_space(self, space_update_info: SpaceUpdateSchema):
        """更新空间信息"""
        space_uuid = space_update_info.space_uuid
        space = await self.space_repo.get(space_uuid)

        # 判断空间是否存在
        if not space:
            raise SpaceNotExistedError

        # 判断用户是否有权限修改
        space_access = await self.acl.check_space_role(
            user_id=self.user.uuid,
            space_id=space_uuid,
            min_role="owner"
        )
        if not space_access:
            raise SpaceAccessError
        # if space.owner != self.user.uuid:
        #     raise SpaceAccessError

        res = await self.space_repo.update_space(space, space_update_info)
        return res

    async def get_space_member_list(self, space_id: UUID):
        """获取空间成员列表"""
        # space_id = UUID(space_id)
        # 检查空间状态与所有权
        space = await self.space_repo.get(space_id)
        if not space:
            raise SpaceNotExistedError
        # else:
        #     space_entiry = SpaceEntity.model_validate(space)

        space_access = await self.acl.check_space_role(
            user_id=self.user.uuid,
            space_id=space_id,
            min_role="admin"
        )
        if not space_access:
            raise SpaceAccessError
        # if not space_entiry.is_user_have_access(self.user.uuid):
        #     raise SpaceAccessError

        res = await self.space_repo.get_space_partner_list(space_id)
        return {
            "members": [
                {
                    "uuid": user.uuid,
                    "account": user.account,
                    "name": user.name,
                    "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for user in res
            ]
        }

    async def invite_user_to_space(self, user_invite_info: SpaceInviteSchema):
        """邀请用户加入空间"""
        # 检查被邀请用户是否存在
        account = user_invite_info.account
        space_uuid = user_invite_info.space_uuid

        # 获取被邀请用户信息
        user = await self.user_repository.get_user_by_account(account)
        if not user:
            raise UserNotExistedError

        # 检查空间状态与所有权
        space = await self.space_repo.get(space_uuid)
        if not space:
            raise SpaceNotExistedError

        if not self.acl.check_space_role(
            user_id=self.user.uuid,
            space_id=space_uuid,
            min_role="admin"
        ):
            raise SpaceAccessError
        # else:
        #     space_entity = SpaceEntity.model_validate(space)
        #     if not space_entity.is_user_have_access(self.user.uuid):
        #         raise SpaceAccessError

        res = await self.space_repo.add_user_to_space(space, user)
        return res

    async def remove_member(self, space_id: UUID, target_user_id: UUID):
        """移除空间成员"""
        space = await self.space_repo.get(space_id)
        if not space:
            raise SpaceNotExistedError

        # 权限检查：操作者需为 admin 以上
        space_access = await self.acl.check_space_role(
            user_id=self.user.uuid, space_id=space_id, min_role="admin"
        )
        if not space_access:
            raise SpaceAccessError

        # 不可移除 owner
        member = await self.space_repo.get_space_member(space_id, target_user_id)
        if not member:
            raise SpaceMemberNotFoundError
        if member.space_role == "owner":
            raise SpaceOwnerCannotBeRemovedError

        res = await self.space_repo.remove_member(space_id, target_user_id)
        return res

    async def update_member_role(self, space_id: UUID, target_user_id: UUID, req: SpaceMemberRoleUpdateRequest):
        """变更空间成员角色"""
        space = await self.space_repo.get(space_id)
        if not space:
            raise SpaceNotExistedError

        # 权限检查：操作者需为 admin 以上
        space_access = await self.acl.check_space_role(
            user_id=self.user.uuid, space_id=space_id, min_role="admin"
        )
        if not space_access:
            raise SpaceAccessError

        member = await self.space_repo.get_space_member(space_id, target_user_id)
        if not member:
            raise SpaceMemberNotFoundError

        # 不可降级 owner
        if member.space_role == "owner" and req.role != "owner":
            raise SpaceOwnerCannotBeRemovedError

        res = await self.space_repo.update_member_role(space_id, target_user_id, req.role)
        return res

    async def get_space_kb_list(self, space_id: UUID):
        """获取空间知识库列表"""
        # 检查空间状态与所有权
        space = await self.space_repo.get(space_id)
        if not space:
            raise SpaceNotExistedError

        space_access = await self.acl.check_space_role(
            user_id=self.user.uuid,
            space_id=space_id,
            min_role="viewer"
        )
        if not space_access:
            raise SpaceAccessError

        res = await self.kbase_repository.get_space_kb_list(space_id)

        kb_list = []
        for kb in res:
            if kb.logo and not kb.logo.startswith("http"):
                kb.logo = await self.storage.presign(space_id, kb.logo, ttl=3600)
            # 判断用户是否拥有kb的viewer及以上权限
            try:
                await self.acl.check_acl(
                    user_id=self.user.uuid,
                    space_id=space_id,
                    resource_type="kbase",
                    resource_id=kb.uuid,
                    action=Action.kbase_view
                )
            except HTTPException as e:
                logger.debug("用户 {} 没有权限访问知识库 {}, 将在列表中隐藏".format(self.user.uuid, kb.uuid))
                continue
            chat_resource = await self.kbase_repository.get_chat_resources(space_id, kb.chat_resources)
            kb_list.append({
                "uuid": kb.uuid,
                "name": kb.name,
                "logo": kb.logo,
                "description": kb.description,
                "collection_name": kb.collection_name,
                "default_questions": kb.default_questions,
                "chat_resources": [
                    {
                        "uri": res.uri,
                        "title": res.title,
                        "description": res.description,
                        "agent": res.agent
                    }
                    for res in chat_resource
                ],
                "status": kb.status,
                "public": kb.public,
                "embed": kb.embed,
                "created_at": kb.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            })

        return kb_list

    async def delete_kbase_in_space(self, space_id: UUID, kbase_id: UUID):
        """删除空间知识库"""
        # 检查空间状态与所有权
        async with self.db.begin():
            await self.acl.check_acl(space_id=space_id, user_id=self.user.uuid, resource_id=kbase_id, resource_type="kbase", action=Action.space_delete)

            res = await self.space_repo.delete_kbase(space_id, kbase_id)
            await self.acl.delete_acl(space_id=space_id, resource_type="kbase" ,resource_id=kbase_id)
            await self.kbase_repository.delete_kbase_resources(space_id, kbase_id)
            await self.kbase_repository.delete_kbase_vector_data(space_id, kbase_id)
        return res

    async def upload_image_to_space(self, space_id: UUID, image_data: UploadFile) -> dict:
        """上传知识库图片到空间存储桶"""
        # 检查空间状态与所有权
        logger.info(f"用户 {self.user.uuid} 上传图片到空间 {space_id} 存储桶")
        space = await self.space_repo.get(space_id)
        if not space:
            raise SpaceNotExistedError

        space_access = await self.acl.check_space_role(
            user_id=self.user.uuid,
            space_id=space_id,
            min_role="admin"
        )
        if not space_access:
            raise SpaceAccessError

        ext = image_data.filename.split('.')[-1]
        if ext.lower() not in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
            raise FileTypeNotSupportedError(file_type=ext)

        filename_stem = hash_md5(image_data.filename)[:8]

        try:
            logger.info("上传图片到存储")
            return await self.storage.save_space_image(
                space_id=space_id,
                file=image_data,
                filename_stem=filename_stem,
                ext=ext,
                ttl=60 * 60 * 24,
            )
        except EndpointConnectionError:
            logger.error("图片上传失败，无法连接到存储服务")
            raise ImageUploadError

    async def upload_logo_to_space(self, space_id: UUID, image_data: UploadFile) -> dict:
        """上传空间logo到空间存储桶"""
        # 检查空间状态与所有权
        logger.info(f"用户 {self.user.uuid} 上传空间logo到空间 {space_id} 存储桶")
        space = await self.space_repo.get(space_id)
        if not space:
            raise SpaceNotExistedError

        space_access = await self.acl.check_space_role(
            user_id=self.user.uuid,
            space_id=space_id,
            min_role="member"
        )
        if not space_access:
            raise SpaceAccessError

        ext = image_data.filename.split('.')[-1]
        if ext.lower() not in ['jpg', 'jpeg', 'png']:
            raise FileTypeNotSupportedError(file_type=ext)

        try:
            logger.info("上传 logo 到存储")
            return await self.storage.save_space_logo(space_id, image_data)
        except EndpointConnectionError:
            logger.error("logo 上传失败，无法连接到存储服务")
            raise ImageUploadError

    async def get_chat_resource_list(self, space_id: UUID):
        """获取空间下的对话资源列表"""

        space = await self.space_repo.get(space_id)
        if not space:
            raise SpaceNotExistedError

        space_access = await self.acl.check_space_role(
            user_id=self.user.uuid,
            space_id=space_id,
            min_role="viewer"
        )
        if not space_access:
            raise SpaceAccessError

        res = await self.space_repo.get_space_chat_resource_list(space_id)

        return [
            item.as_dict()
            for item in res
        ]
