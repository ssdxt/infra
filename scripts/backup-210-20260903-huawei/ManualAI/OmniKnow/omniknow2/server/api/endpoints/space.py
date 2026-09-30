from uuid import UUID

from fastapi import APIRouter, Depends

from core.dependencies import RequestContext, get_request_context, authorize, audited
from audit.spec import AuditSpec
from schemas import ResponseModel
from schemas import SpaceCreateSchema, SpaceInviteSchema, SpaceUpdateSchema
from schemas.space import SpaceMemberRoleUpdateRequest
from services.space import SpaceService



router = APIRouter()


@router.post("/users/{user_id}/spaces")
async def create_space(
        user_id: UUID,
        space: SpaceCreateSchema,
        ctx: RequestContext = Depends(get_request_context)
) -> ResponseModel:
    """
    创建空间
    路径附带用户ID，表示为该用户创建空间
    """
    space_service = SpaceService(ctx)
    res = await space_service.create_space(user_id, space)
    return ResponseModel.success(res)


@router.patch("/spaces/{space_id}/update")
async def update_space(
        space_update_info: SpaceUpdateSchema,
        ctx: RequestContext = Depends(get_request_context)
) -> ResponseModel:
    """
    更新空间信息
    """
    space = SpaceService(ctx)
    res = await space.update_space(space_update_info)
    return ResponseModel.success(res)


@router.put("/spaces/{space_id}/invite")
async def invite_user_to_space(
        user_invite_info: SpaceInviteSchema,
        ctx: RequestContext = Depends(get_request_context)
) -> ResponseModel:
    """
    邀请用户加入空间
    """
    space_service = SpaceService(ctx)
    await space_service.invite_user_to_space(user_invite_info)
    return ResponseModel.success()


@router.get("/spaces/{space_id}/members")
async def get_space_member_list(
        space_id: UUID,
        ctx: RequestContext = Depends(get_request_context)
) -> ResponseModel:
    """
    获取空间成员列表
    """
    space_service = SpaceService(ctx)
    res = await space_service.get_space_member_list(space_id)
    return ResponseModel.success(res)


@router.delete("/spaces/{space_id}/members/{user_id}")
async def remove_space_member(
        space_id: UUID,
        user_id: UUID,
        ctx: RequestContext = Depends(audited(
            AuditSpec(action="member_remove", target_type="member", target_param="user_id")
        )),
) -> ResponseModel:
    """移除空间成员"""
    space_service = SpaceService(ctx)
    await space_service.remove_member(space_id, user_id)
    return ResponseModel.success()


@router.patch("/spaces/{space_id}/members/{user_id}/role")
async def update_space_member_role(
        space_id: UUID,
        user_id: UUID,
        req: SpaceMemberRoleUpdateRequest,
        ctx: RequestContext = Depends(audited(
            AuditSpec(action="member_role_change", target_type="member", target_param="user_id")
        )),
) -> ResponseModel:
    """变更空间成员角色"""
    space_service = SpaceService(ctx)
    await space_service.update_member_role(space_id, user_id, req)
    ctx.audit_detail = {"new_role": req.role}
    return ResponseModel.success()


@router.get("/spaces/{space_id}/kbs")
async def get_kbase_list_by_space(
        space_id: UUID,
        ctx: RequestContext = Depends(get_request_context)
) -> ResponseModel:
    """
    获取空间下的知识库列表
    """
    space_service = SpaceService(ctx)
    res = await space_service.get_space_kb_list(space_id)
    return ResponseModel.success(res)


@router.delete("/spaces/{space_id}/kbs/{kbase_id}")
async def delete_kbase_in_space(
        space_id: UUID,
        kbase_id: UUID,
        ctx: RequestContext = Depends(authorize("space:kbase:delete"))
) -> ResponseModel:
    """
    删除空间下的知识库
    """
    space_service = SpaceService(ctx)
    res = await space_service.delete_kbase_in_space(space_id, kbase_id)
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/chat-resouces")
async def get_chat_resource_list(
        space_id: UUID,
        ctx: RequestContext = Depends(get_request_context)
) -> ResponseModel:
    """
    获取空间下的对话资源列表
    """
    space_service = SpaceService(ctx)
    res = await space_service.get_chat_resource_list(space_id)
    return ResponseModel.success(res)


# @router.put("/spaces/{space_id}/images/upload")
# async def upload_kbase_image(
#         space_id: UUID,
#         image: UploadFile = File(...),
#         expire: int = Form(60 * 60 * 24, ge=0),
#         ctx: RequestContext = Depends(authorize("kbase:upload"))
# ):
#     """
#     在空间下上传图片
#     """
#     image_service = ImgService(ctx)
#     res = await image_service.upload_images(space_id, image, expire)
#     return ResponseModel.success(res)
#
#
# @router.get("/spaces/{space_id}/images/{image_id}")
# async def get_space_image(
#         space_id: UUID,
#         image_id: UUID,
#         expire: int = Query(3600, ge=0),
#         ctx: RequestContext = Depends(authorize("kbase:view"))
# ):
#     """
#     获取空间下图片的临时访问链接
#     """
#     image_service = ImgService(ctx)
#     res = await image_service.get_image_url(space_id, image_id, expire)
#     return ResponseModel.success(res)


# @router.put("/spaces/{space_id}/logos/upload")
# async def upload_space_logo(
#         space_id: UUID,
#         logo: UploadFile = File(...),
#         ctx: RequestContext = Depends(authorize("kbase:upload"))
# ):
#     """
#     在空间下上传logo
#     """
#     space_service = SpaceService(ctx)
#     res = await space_service.upload_logo_to_space(space_id, logo)
#     return ResponseModel.success(res)
