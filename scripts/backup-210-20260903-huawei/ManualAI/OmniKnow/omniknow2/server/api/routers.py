from fastapi import APIRouter, Depends

from api import endpoints

router = APIRouter(prefix="/api/v1")
dev_router = APIRouter(prefix="/dev")

dev_router.include_router(
    endpoints.dev.router,
    tags=["开发者"]
)

router.include_router(
    endpoints.task.router,
    tags=["任务接口"]
)

router.include_router(
    endpoints.chat.router,
    tags=["聊天接口"]
)

# 聚合认证路由
router.include_router(
    endpoints.auth.router,
    prefix="/auth",
    tags=["用户鉴权"]
)

router.include_router(
    endpoints.space.router,
    # prefix="/spaces",
    tags=["空间接口"]
)

router.include_router(
    endpoints.user.router,
    # prefix="/user",
    tags=["用户接口"]
)

router.include_router(
    endpoints.kbase.router,
    # prefix="/kbase",
    tags=["知识库"]
)

# app.include_router(router)
# 聚合商品路由（添加公共安全依赖）
router.include_router(
    endpoints.ent.router,
    prefix="/ent",
    tags=["企业管理"]
)

from training.api import router as training_router
router.include_router(training_router, tags=["考试培训"])

from report.api import router as report_router
router.include_router(report_router, tags=["报告管理"])

from admin.api import router as admin_router
router.include_router(admin_router, tags=["管理后台"])

from audit.router import router as audit_router
router.include_router(audit_router, tags=["审计日志"])

from image.api import router as image_router
router.include_router(image_router, tags=["图片管理"])

from memory.api import router as memory_router
router.include_router(memory_router, tags=["反馈记忆"])
#
# router.include_router(
#     endpoints.host.router,
#     prefix="/hosts",
#     dependencies=[Depends(check_auth_credentials)],  # 全局安全校验
#     tags=["宿主机"]
# )
