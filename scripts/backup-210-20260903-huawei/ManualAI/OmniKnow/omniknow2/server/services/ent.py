import time
import hashlib
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Sequence

from repository.ent import UserRepository
from exceptions.errors.ent import EntExistedError, EntNotExistedError
from schemas.ent import EntSchema, UpdateEntSchema
from utils.public import hash_md5


class EntService:
    def __init__(self, db: AsyncSession):
        self.repository = UserRepository(db)

    async def get_all_tenant(self):
        res = await self.repository.get_all_tenant()
        res = [{"uuid": i.uuid, "name": i.name} for i in res]
        return res

    async def get_tenant_detail(self, tenant_id):
        res = await self.repository.get_tenant_detail_by_id(tenant_id)
        if not res:
            raise EntNotExistedError(ent_id=tenant_id)
        return res

    async def create_ent(self, ent_info: EntSchema):
        ent = await self.repository.get_tenant_id_by_name(ent_info.name)
        if ent:
            raise EntExistedError(ent_name=ent_info.name)
        md5 = hash_md5(ent_info.name.encode() + str(time.time()).encode())
        res = await self.repository.create_ent(ent_info, md5)
        return res

    async def update_ent(self, tenant_id: UUID, update_info: UpdateEntSchema):
        ent = await self.repository.get_tenant_detail_by_id(tenant_id)
        if not ent:
            raise EntNotExistedError(ent_id=tenant_id)
        res = await self.repository.update_ent(tenant_id, update_info)
        return res
    # @staticmethod
    # async def init(db, app_info: AppCreationSchema):
    #     from crud.app import save_app_to_db, get_app_by_name
    #     app = await get_app_by_name(app_info.name, db)
    #     if app:
    #         raise AppExistedError(app_name=app_info.name)
    #     res = await save_app_to_db(app_info, db)
    #     data = {
    #         "uuid": res.uuid,
    #         "name": res.name,
    #         "descption": res.description,
    #         "icon_url": res.icon,
    #         "created_at": res.created_at.strftime("%Y-%m-%d %H:%M:%S")
    #     }
    #     return data
    #
    # async def add_detail(self, app_detail: AppDetailSchema, db):
    #     from crud.app import add_app_detail
    #     # host, path = app_detail.url.split('/', 3)[2:4]
    #     protocol, host, path = app_detail.url.split('/', 3)
    #     method, param, header, body, response = (app_detail.method, app_detail.params, app_detail.headers,
    #                                              app_detail.body, app_detail.response)
    #
    #     res = await add_app_detail(uuid=self.uuid, host=host, path=path, method=method, params=param,
    #                                body=body, response=response, db=db)
    #     data = {
    #         "uuid": res.uuid,
    #         "created_at": res.created_at.strftime("%Y-%m-%d %H:%M:%S")
    #     }
    #     return data
    #
    # async def update_detail(self, app_detail: AppDetailSchema, db):
    #     from crud.app import get_app_detail_by_uuid, update_app_detail
    #     db_detail = await get_app_detail_by_uuid(self.uuid, db)
    #     if not db_detail:
    #         raise AppNotExistedError(app_name=app_detail.name)
    #     res = await update_app_detail(self.uuid, app_detail, db)
    #     data = {
    #         "uuid": res.uuid,
    #         "updated_at": res.updated_at.strftime("%Y-%m-%d %H:%M:%S")
    #     }
    #     return data

    async def delete_app(self, db):
        pass


