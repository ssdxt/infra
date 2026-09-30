from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from core.dependencies import RequestContext, authorize
from image.service import ImgService
from schemas import ResponseModel


router = APIRouter()


@router.put("/spaces/{space_id}/images/upload")
async def upload_kbase_image(
        space_id: UUID,
        image: UploadFile = File(..., description="上传的图片文件"),
        expire: int = Form(3600, ge=0, description="图片过期时间，单位秒，默认1小时"),
        ctx: RequestContext = Depends(authorize("public"))
):
    """
    在空间下上传图像
    """
    img_serv = ImgService(ctx)
    res = await img_serv.upload_images(space_id, image, expire)
    return ResponseModel.success(res)


@router.get("/spaces/{space_id}/images/{image_id}")
async def get_kbase_image(
        space_id: UUID,
        image_id: UUID,
        expire: int = Query(3600, ge=0, description="图片链接过期时间，单位秒，默认1小时"),
        ctx: RequestContext = Depends(authorize("kbase:view"))
):
    """
    获取空间下的图像
    """
    img_serv = ImgService(ctx)
    res = await img_serv.get_image_url(space_id, image_id, expire)
    return ResponseModel.success(res)


@router.put("/spaces/{space_id}/logos/upload")
async def upload_space_logo(
        space_id: UUID,
        logo: UploadFile = File(...),
        ctx: RequestContext = Depends(authorize("kbase:upload"))
):
    """
    在空间下上传logo
    """
    img_serv = ImgService(ctx)
    res = await img_serv.upload_logo(space_id, logo)
    return ResponseModel.success(res)