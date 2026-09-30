from core.dependencies import RequestContext
from core.permission_cache import invalidate_user_permissions
from repository import UserRepository, SpaceRepository
from schemas import UserProfileResponse, UserProfileRequest
from exceptions.errors.users import UserNotExistedError
from utils import base64_to_str, hash_sha512
from utils.password_validator import validate_password_strength


class UserService:

    def __init__(self, ctx: RequestContext):
        self.db = ctx.db
        self.user = ctx.user
        self.redis = ctx.redis
        self.request = ctx.request
        self.user_repo = UserRepository(self.db)
        self.space_repo = SpaceRepository(self.db)

    async def get_personal_profile(self):
        user = await self.user_repo.get_by_id(self.user.uuid)
        user_detail = await self.user_repo.get_detail_by_id(self.user.uuid)
        role_codes = await self.user_repo.get_user_role_codes(self.user.uuid)

        return UserProfileResponse(
            space_id=user.space_id,
            space_role=user.space_role,
            uuid=user.uuid,
            account=user.account,
            name=user.name,
            source=user.source,
            created_at=user.created_at,
            **user_detail,
            roles=role_codes
        )

    async def update_person_profile(self, profile: UserProfileRequest):
        user = await self.user_repo.get(self.user.uuid)
        if user is None:
            raise UserNotExistedError
        async with self.db.begin():
            res = await self.user_repo.update_deatil(user,
                                                     profile.model_dump())
        return res

    async def get_user_space_list(self):
        space = await self.space_repo.get_spaces_by_user(self.user.uuid)
        # own_space = await self.space_repo.get_own_spaces(self.user.uuid)
        data = {
            "member": [
                {
                    "uuid": s.uuid,
                    "name": s.name,
                    "role": s.role
                }
                for s in space
            ],
            # "owner": [
            #     {
            #         "uuid": s.uuid,
            #         "name": s.name
            #     }
            #     for s in own_space
            # ],
        }
        return data

    async def update_person_password(self, new_password_b64: str):
        user = await self.user_repo.get(self.user.uuid)
        if user is None:
            raise UserNotExistedError

        password = base64_to_str(new_password_b64)
        validate_password_strength(password)
        msg = f"{password}{user.salt}"
        secret = hash_sha512(msg)
        res = await self.user_repo.update_password(user, secret)
        # 密码修改后清除权限缓存，强制重新登录
        await invalidate_user_permissions(self.redis, self.user.uuid)
        return res
