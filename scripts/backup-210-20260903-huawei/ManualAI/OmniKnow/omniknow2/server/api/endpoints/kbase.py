from fastapi import APIRouter, Depends, Query, UploadFile, File
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from audit.spec import AuditSpec
from core.dependencies import RequestContext, authorize
from db import get_session
from ext.redis_client import get_redis
from schemas import KBaseCreateSchema, KBaseUpdateSchema, ResponseModel
from schemas.kbase import DocParseRequest, MarkdownUploadSchema, DefaultQuestionCreateSchema
from core.acl.schema import ResourceType
from services import DocumentService, KbaseService

from typing import List
from uuid import UUID


router = APIRouter()


@router.post("/spaces/{space_id}/kbs")
async def create_kbase(
        space_id: UUID,
        kbase_info: KBaseCreateSchema,
        ctx: RequestContext = Depends(authorize("kbase:create"))
):
    """
    在空间下新增知识库
    """
    kbase_service = KbaseService(ctx)
    res = await kbase_service.create_kbase(space_id, kbase_info)
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/kbs/{kbase_id}")
async def get_kbase_info(
        space_id: UUID,
        kbase_id: UUID,
        ctx: RequestContext = Depends(
            authorize(
            permission_code="kbase:view",
            audit=AuditSpec(
                action="view",
                target_type="kbase"
                )
            )
        )
):
    """
    获取知识库信息
    """
    kbase_service = KbaseService(ctx)
    res = await kbase_service.get_kbase_overview(space_id, kbase_id)
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/kbs/{kbase_id}/resources")
async def get_kbase_resource_list(
        space_id: UUID,
        kbase_id: UUID,
        page: int = Query(1, ge=1, description="页码，从1开始"),
        page_size: int = Query(20, ge=1, le=100, description="每页数量，最大100"),
        ctx: RequestContext = Depends(authorize("kbase:view"))
):
    """
    获取知识库下的资源列表（统一入口，前端通过 type 过滤）
    """
    doc_service = DocumentService(ctx)
    res = await doc_service.get_kbase_resource_list(space_id, kbase_id, page=page, page_size=page_size)
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/kbs/{kbase_id}/docs")
async def get_kbase_doc_list(
        space_id: UUID,
        kbase_id: UUID,
        ctx: RequestContext = Depends(authorize("kbase:view"))
):
    """
    获取知识库下的文档列表
    """
    doc_service = DocumentService(ctx)
    res = await doc_service.get_kbase_resource_list(space_id, kbase_id, ResourceType.doc)
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/kbs/{kbase_id}/resources/{resource_id}")
async def get_resource_detail(
        space_id: UUID,
        kbase_id: UUID,
        resource_id: UUID,
        ctx: RequestContext = Depends(authorize("kbase:view"))
):
    """
    获取知识库资源详情
    """
    doc_service = DocumentService(ctx)
    res = await doc_service.get_resource_detail(space_id, kbase_id, resource_id)
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/kbs/{kbase_id}/resources/{resource_id}/url")
async def download_resource(
        space_id: UUID,
        kbase_id: UUID,
        resource_id: UUID,
        ctx: RequestContext = Depends(authorize("kbase:view"))
):
    """
    下载知识库资源
    """
    doc_service = DocumentService(ctx)
    res = await doc_service.download_resource(space_id, kbase_id, resource_id)
    return ResponseModel.success(res)


@router.patch("/spaces/{space_id}/kbs/{kbase_id}")
async def update_kbase_info(
        space_id: UUID,
        kbase_id: UUID,
        kbase_info: KBaseUpdateSchema,
        ctx: RequestContext = Depends(authorize("kbase:update"))
):
    """
    更新知识库信息
    """
    kbase_service = KbaseService(ctx)
    res = await kbase_service.update_kbase(space_id, kbase_id, kbase_info)
    return ResponseModel.success(res)


@router.delete("/spaces/{space_id}/kbs/{kbase_id}/resources/{resource_id}")
async def delete_kbase_resource(
        space_id: UUID,
        kbase_id: UUID,
        resource_id: UUID,
        ctx: RequestContext = Depends(authorize("kbase:delete"))
):
    """
    销毁知识库下的资源
    """
    doc_service = DocumentService(ctx)
    res = await doc_service.delete_resource(space_id, kbase_id, resource_id)
    return ResponseModel.success(res)


@router.post("/spaces/{space_id}/kbs/{kbase_id}/resources/{resource_id}/archive")
async def archive_kbase_resource(
        space_id: UUID,
        kbase_id: UUID,
        resource_id: UUID,
        ctx: RequestContext = Depends(authorize("kbase:update"))
):
    """
    归档知识库下的资源（软删除，保留数据但前端不展示）
    """
    doc_service = DocumentService(ctx)
    res = await doc_service.archive_resource(space_id, kbase_id, resource_id)
    return ResponseModel.success(res)


@router.post("/spaces/{space_id}/kbs/{kbase_id}/docs/upload")
async def upload_documents(
        space_id: UUID,
        kbase_id: UUID,
        files: List[UploadFile] = File(...),
        ctx: RequestContext = Depends(authorize("kbase:upload"))
):
    """
    上传文档到知识库（支持单文件和批量上传）。
    同名文件自动重命名，存在重命名时响应 code 为 201。
    """
    doc_service = DocumentService(ctx)
    res = await doc_service.upload_file_group_to_kbase(space_id, kbase_id, files)
    if res.get("has_duplicates"):
        return ResponseModel.success(res["files"], code=201, message="存在同名文件，已自动重命名")
    return ResponseModel.success(res["files"])


@router.post("/spaces/{space_id}/kbs/{kbase_id}/docs/parse")
async def parse_documents(
        space_id: UUID,
        kbase_id: UUID,
        request: DocParseRequest,
        ctx: RequestContext = Depends(authorize("kbase:parse"))
):
    """
    对已上传的文档发起解析（通过 file_ids 指定，支持单个和批量）
    """
    doc_service = DocumentService(ctx)
    res = await doc_service.parse_documents(space_id, kbase_id, request)
    return ResponseModel.success(res)


@router.post("/spaces/{space_id}/kbs/{kbase_id}/md")
async def upsert_kbase_markdown_doc(
        space_id: UUID,
        kbase_id: UUID,
        md: MarkdownUploadSchema,
        ctx: RequestContext = Depends(authorize("kbase:update"))
):
    """
    编辑知识库下的Markdown文档
    """
    doc_service = DocumentService(ctx)
    res = await doc_service.upsert_markdown_doc(space_id, kbase_id, md)
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/kbs/{kbase_id}/md/{doc_id}")
async def get_kbase_markdown_doc(
        space_id: UUID,
        kbase_id: UUID,
        doc_id: UUID,
        ctx: RequestContext = Depends(authorize("kbase:view"))
):
    """
    获取知识库下的Markdown文档
    """
    doc_service = DocumentService(ctx)
    res = await doc_service.get_markdown_doc(space_id, kbase_id, doc_id)
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/kbs/{kbase_id}/docs/{doc_id}/chunks")
async def get_kbase_doc_chunks(
        space_id: UUID,
        kbase_id: UUID,
        doc_id: UUID,
        page: int = Query(1, ge=1, description="页码，从1开始"),
        page_size: int = Query(20, ge=1, le=100, description="每页数量，最大100"),
        ctx: RequestContext = Depends(authorize("kbase:view"))
):
    """
    获取知识库下文档的分块内容
    """
    doc_service = DocumentService(ctx)
    res = await doc_service.get_doc_chunks(space_id, kbase_id, doc_id, page=page, page_size=page_size)
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/kbs/{kbase_id}/docs/{doc_id}/chunks/{chunk_id}")
async def get_kbase_doc_chunk_detail(
        space_id: UUID,
        kbase_id: UUID,
        doc_id: UUID,
        chunk_id: UUID,
        ctx: RequestContext = Depends(authorize("kbase:view"))
):
    """
    获取知识库下文档分块的详情
    """
    doc_service = DocumentService(ctx)
    res = await doc_service.get_doc_chunk_detail(space_id, kbase_id, doc_id, chunk_id)
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/kbs/{kbase_id}/docs/{doc_id}/chunk")
async def get_kbase_doc_chunk_by_index(
        space_id: UUID,
        kbase_id: UUID,
        doc_id: UUID,
        index: int = Query(..., ge=0, description="分块索引，从0开始"),
        ctx: RequestContext = Depends(authorize("kbase:view"))
):
    """
    获取知识库下文档分块的详情（通过分块索引）
    """
    doc_service = DocumentService(ctx)
    res = await doc_service.get_doc_chunk_detail_by_index(space_id, kbase_id, doc_id, index)
    return ResponseModel.success(res)


@router.get("/kbs/{collection_name}/resources")
async def get_kbase_resource_by_collection_name(
        collection_name: str,
        session: AsyncSession = Depends(get_session),
):
    """
    通过知识库集合名称获取资源列表（不带访问控制检查，仅用于内部调用）
    """
    redis = get_redis(1)
    doc_service = DocumentService.internal(session, redis)
    res = await doc_service.get_resource_url_by_collection(collection_name)
    return ResponseModel.success(res)

# @router.get("/spaces/{space_id}/kbs/{kbase_id}/questions")
# async def get_kbase_defaut_questions(
#         space_id: UUID,
#         kbase_id: UUID,
#         ctx: RequestContext = Depends(authorize("kbase:view"))
# ):
#     """
#     获取知识库默认问题列表
#     """
#     kbase_service = KbaseService(ctx)
#     res = await kbase_service.get_kbase_default_questions(space_id, kbase_id)
#     return ResponseModel.success(res)
#
#
# @router.post("/spaces/{space_id}/kbs/{kbase_id}/questions")
# async def get_kbase_defaut_questions(
#         space_id: UUID,
#         kbase_id: UUID,
#         payload: DefaultQuestionCreateSchema,
#         ctx: RequestContext = Depends(authorize("kbase:view"))
# ):
#     """
#     插入知识库默认问题列表
#     """
#     kbase_service = KbaseService(ctx)
#     res = await kbase_service.insert_kbase_default_questions(space_id, kbase_id, payload)
#     return ResponseModel.success(res)
#
#
# @router.delete("/spaces/{space_id}/kbs/{kbase_id}/questions/{question_id}")
# async def delete_kbase_defaut_question(
#         space_id: UUID,
#         kbase_id: UUID,
#         question_id: UUID ,
#         ctx: RequestContext = Depends(authorize("kbase:view"))
# ):
#     """
#     删除知识库默认问题
#     """
#     kbase_service = KbaseService(ctx)
#     await kbase_service.delete_kbase_default_questions(space_id, kbase_id, question_id)
#     return ResponseModel.success()