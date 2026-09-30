from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

import hashlib
import time
from uuid import UUID

from db.models.rag import Tenant
from schemas.ent import EntSchema, UpdateEntSchema

class UserRepository:
    def __init__(self, db):
        self.db = db

    async def get_all_tenant(self) -> list[Tenant]:
        # 获取所有企业
        result = await self.db.execute(select(Tenant.uuid, Tenant.name))
        return result.all()


    async def get_tenant_detail_by_id(self, tenant_id: UUID) -> Tenant:
        """
        通过 id 获取企业详情
        """
        result = await self.db.execute(select(Tenant).filter(Tenant.uuid==tenant_id))
        return result.scalar_one_or_none()


    async def get_tenant_id_by_name(self, tenant_name: str) -> Tenant:
        """
        通过 name 获取企业详情
        """
        result = await self.db.execute(select(Tenant.uuid).filter(Tenant.name==tenant_name))
        return result.scalar_one_or_none()


    async def create_ent(self, ent_info: EntSchema, md5: str):
        """
        创建一个企业
        """
        ent = Tenant(**ent_info.model_dump(), md5=md5)
        self.db.add(ent)
        await self.db.commit()
        await self.db.refresh(ent)
        return ent.to_dict()


    async def update_ent(self, ent_id: UUID, ent_info: UpdateEntSchema):
        """
        更新一个企业
        """
        db_ent = await self.db.get(Tenant, ent_id)

        for key, value in ent_info.model_dump().items():
            setattr(db_ent, key, value)

        result = await self.db.commit()
        return result