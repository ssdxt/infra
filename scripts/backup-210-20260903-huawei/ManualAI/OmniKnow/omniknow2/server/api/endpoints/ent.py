from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from db.session import get_session
from services import EntService
from schemas.ent import EntSchema, UpdateEntSchema
from schemas.public import ResponseModel


router = APIRouter()

# @router.get("/")
# async def get_ent_list(
#         db: AsyncSession = Depends(get_session)
# ) -> ResponseModel:
#     """
#     获取所有企业列表
#     """
#     ent_service = EntService(db)
#     res = await ent_service.get_all_tenant()
#     return ResponseModel.success(res)
#
#
# @router.get("/{tenant_id}")
# async def get_ent_detail(
#         tenant_id: UUID,
#         db: AsyncSession = Depends(get_session)
# ):
#     """
#     获取指定ID的企业详情
#     """
#     ent_service = EntService(db)
#     res = await ent_service.get_tenant_detail(tenant_id)
#     return ResponseModel.success(res)
#
#
# @router.put('/')
# async def create_ent(
#         ent_info: EntSchema,
#         db: AsyncSession = Depends(get_session)
# ):
#     """
#     创建一个企业
#     """
#     ent_service = EntService(db)
#     res = await ent_service.create_ent(ent_info)
#     return ResponseModel.success(res)


# @router.patch('/{tenant_id}')
# async def update_ent(
#         tenant_id: UUID,
#         ent_info: UpdateEntSchema,
#         db: AsyncSession = Depends(get_session)
# ):
#     """
#     更新指定ID的企业信息
#     """
#     ent_service = EntService(db)
#     res = await ent_service.update_ent(tenant_id, ent_info)
#     return ResponseModel.success(res)
