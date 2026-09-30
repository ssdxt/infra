import os
from typing import List
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from loguru import logger
from PIL import Image, ImageOps
from pydantic import BaseModel, Field
from transformers import AutoImageProcessor, AutoModel
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()

class ImageEmbeddingRequest(BaseModel):
    paths: List[str] = Field(..., min_length=1, description="本地图片绝对路径列表")

class ImageEmbeddingResponse(BaseModel):
    embeddings: List[List[float]]

MODEL_PATH = os.getenv("IMG_MODEL_PATH", "/ManualAI/OmniKnow/models/dinov3-vitl16-pretrain-lvd1689m")
HOST = os.getenv("IMG_SERVICE_HOST", "0.0.0.0")
PORT = int(os.getenv("IMG_SERVICE_PORT", "18080"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ===== 启动阶段 =====
    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(f"IMG_MODEL_PATH 不存在: {MODEL_PATH}")

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    
    processor = AutoImageProcessor.from_pretrained(MODEL_PATH)
    model = AutoModel.from_pretrained(MODEL_PATH)
    model.to(device)
    model.eval()

    app.state.processor = processor
    app.state.model = model
    app.state.device = device

    logger.info(f"Image embedding model loaded, device={device}, model_path={MODEL_PATH}")

    yield

    # ===== 关闭阶段（可选）=====
    try:
        del app.state.model
        torch.cuda.empty_cache()
        logger.info("Model resources released")
    except Exception as e:
        logger.warning(f"释放资源异常: {e}")

app = FastAPI(title="Image Embedding Service",lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

def _open_single_image(image_path: str):
    image = Image.open(image_path).convert("RGB")
    return ImageOps.exif_transpose(image)


def _open_image_batch(image_paths: List[str]):
    return [_open_single_image(path) for path in image_paths]


@app.get("/healthz")
async def healthz():
    ready = app.state.model is not None and app.state.processor is not None and app.state.device is not None
    return {"model init": ready}


@app.post("/v1/embeddings/image", response_model=ImageEmbeddingResponse)
async def image_embedding(req: ImageEmbeddingRequest):
    if app.state.model is None:
        raise HTTPException(status_code=503, detail="模型未就绪")

    try:
        images = _open_image_batch(req.paths)
        with torch.no_grad():
            inputs = app.state.processor(images=images, return_tensors="pt").to(app.state.device)
            outputs = app.state.model(**inputs)
            pooled_output = outputs.pooler_output
            embedding = torch.nn.functional.normalize(pooled_output, p=2, dim=-1)
        return ImageEmbeddingResponse(embeddings=embedding.cpu().numpy().tolist())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"图片不存在: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"图片向量化失败: {exc}") from exc


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, reload=False)
