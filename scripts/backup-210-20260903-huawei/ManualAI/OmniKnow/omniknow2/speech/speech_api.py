# coding=utf-8
import base64
import io
import shutil
import urllib.request
from typing import Tuple
import numpy as np
import soundfile as sf
import torch
from typing import Any, Dict, List, Optional, Tuple
import uvicorn
import os
import uuid
import asyncio
from starlette.responses import FileResponse, JSONResponse
from fastapi import BackgroundTasks
from fastapi import Form, HTTPException, UploadFile
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, Query, HTTPException
import json
from contextlib import asynccontextmanager
from qwen_asr import Qwen3ASRModel
from fastapi.middleware.cors import CORSMiddleware
import logging
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from dotenv import load_dotenv
load_dotenv()


ASR_MODEL_PATH = os.getenv("ASR_MODEL_PATH")
FORCED_ALIGNER_PATH = os.getenv("FORCED_ALIGNER_PATH")
SPEECH_GPU_MEMORY_UTILIZATION = float(os.getenv("SPEECH_GPU_MEMORY_UTILIZATION", "0.5"))
HOST = os.getenv("SPEECH_SERVICE_HOST", "0.0.0.0")
PORT = int(os.getenv("SPEECH_SERVICE_PORT", "18081"))
WARMUP_ASR_TTS = os.getenv("WARMUP_ASR_TTS", "true").lower() in ("true", "1", "yes", "on")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global asr_model
    asr_model = Qwen3ASRModel.LLM(
        model=ASR_MODEL_PATH,
        gpu_memory_utilization=SPEECH_GPU_MEMORY_UTILIZATION,
        forced_aligner=FORCED_ALIGNER_PATH,
        forced_aligner_kwargs=dict(
            dtype=torch.bfloat16,
            device_map="cuda:0",
            # attn_implementation="flash_attention_2",
        ),
        max_inference_batch_size=32,
        max_new_tokens=1024,
        max_model_len=10240,
    )
    try:
        # 启动阶段做一次 warmup，确保 asr/tts 在首次真实请求前不会因为编译/加载导致超时。
        if WARMUP_ASR_TTS:
            logger.info("warmup...")
            
            try:
                dummy_wav = np.zeros(16000, dtype=np.float32)  # 1s @ 16kHz
                dummy_sr = 16000
                full_lang = map_language("zh")  # 这里用 zh 做默认 warmup
                await asyncio.to_thread(
                    asr_model.transcribe,
                    audio=[(dummy_wav, dummy_sr)],
                    language=[full_lang],
                    context=["炽橙"],
                    return_time_stamps=False,
                )
            except Exception as e:
                logger.warning("ASR warmup failed (non-critical): %s", e)

            try:
                # TTS 走最常用的一个发音人 warmup
                warm_text = os.getenv("TTS_WARMUP_TEXT", "测试一下语音输出。")
                warm_dir = os.path.join("./outputs/tts/warmup", str(uuid.uuid4().hex))
                os.makedirs(warm_dir, exist_ok=True)
                await asyncio.to_thread(
                    sambert_hifigan_tts_wm_tian.infer,
                    text=warm_text,
                    source=warm_dir,
                    scale=1.0,
                )
                # 清理 warmup 产物目录（best-effort）
                await asyncio.to_thread(shutil.rmtree, warm_dir, True)
            except Exception as e:
                logger.warning("TTS warmup failed (non-critical): %s", e)

        yield
    finally:
        asr_model = None



app = FastAPI(title="Speech API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


def _read_wav_from_bytes(audio_bytes: bytes) -> Tuple[np.ndarray, int]:
    # 先用 soundfile 直接解码 wav/pcm 等；若解码失败（例如浏览器录音 webm/opus），再用 ffmpeg 兜底转 wav。
    try:
        with io.BytesIO(audio_bytes) as f:
            wav, sr = sf.read(f, dtype="float32", always_2d=False)
        return np.asarray(wav, dtype=np.float32), int(sr)
    except Exception as exc_sf:        
        ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")
        try:
            process = subprocess.Popen(
                [ffmpeg_bin, "-i", "pipe:0", "-f", "wav", "-"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            out, err = process.communicate(input=audio_bytes)
            if process.returncode != 0:
                raise ValueError(f"FFmpeg decoding failed: {err.decode(errors='ignore')}")
            with io.BytesIO(out) as f:
                wav, sr = sf.read(f, dtype="float32", always_2d=False)
            return np.asarray(wav, dtype=np.float32), int(sr)
        except FileNotFoundError as exc:
            raise ValueError(
                "Invalid audio file and ffmpeg is not available. "
                "Please install ffmpeg or set env var FFMPEG_BIN to ffmpeg executable path."
            ) from exc
        except Exception as exc:
            raise ValueError(f"Invalid audio file: {exc}") from exc_sf


def _format_time_stamps(time_stamps: Any) -> List[Dict[str, Any]]:
    if not time_stamps:
        return []
    return [
        {
            "text": ts.text,
            "start_time": ts.start_time,
            "end_time": ts.end_time,
        }
        for ts in time_stamps
    ]

def _format_result(result: Any) -> Dict[str, Any]:
    return {
        "success": True,
        "text": result.text,
        "time_stamps": _format_time_stamps(result.time_stamps),
    }


def map_language(lang_code: Optional[str]) -> Optional[str]:
    """Map ISO code to Qwen full name."""
    if lang_code is None:
        return None
    mapping = {
        "en": "English", "de": "German", "fr": "French", "es": "Spanish",
        "it": "Italian", "ja": "Japanese", "ko": "Korean", "zh": "Chinese",
        "ru": "Russian", "pt": "Portuguese", "nl": "Dutch", "tr": "Turkish",
        "sv": "Swedish", "id": "Indonesian", "vi": "Vietnamese",
        "hi": "Hindi", "ar": "Arabic",
    }
    return mapping.get(lang_code.lower(), lang_code)

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/asr")
@app.post("/asr/")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = Form("zh", description="Language code (e.g. en, de, fr). None for auto-detect."),
    return_time_stamps: bool = Form(False),
) -> Dict[str, Any]:
    if asr_model is None:
        raise HTTPException(status_code=500, detail="ASR model is not loaded.")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        wav, sr = _read_wav_from_bytes(audio_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid audio file: {exc}") from exc

    full_lang = map_language(language)

    try:
        results = asr_model.transcribe(
            audio=[(wav, sr)],
            language=[full_lang],
            # language=['Chinese','English'],
            context=["炽橙"],
            return_time_stamps=return_time_stamps,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ASR inference failed: {exc}") from exc

    if not results:
        raise HTTPException(status_code=500, detail="No ASR result returned.")

    print('===============================',results)
    return _format_result(results[0])


from tts import TTS
import os
TTS_MODEL_PATH = os.getenv("TTS_MODEL_PATH")
local_dir_root = TTS_MODEL_PATH+"speech_sambert-hifigan_tts_zh-cn_16k"  
tts_onnx = TTS_MODEL_PATH+"models/sambert-hifigan_onnx/"
infer_type = "torch" # torch

current_path = os.getcwd()
prefix_to_delete = 'uploaded_files'  

sambert_hifigan_tts_wm_tian = TTS(basepath=local_dir_root,
                              voice="zhitian_emo", infer_type=infer_type, onnx_dir=tts_onnx)
sambert_hifigan_tts_m_zhe = TTS(basepath=local_dir_root,
                              voice="zhizhe_emo", infer_type=infer_type, onnx_dir=tts_onnx)
sambert_hifigan_tts_wm_yan = TTS(basepath=local_dir_root,
                              voice="zhiyan_emo", infer_type=infer_type, onnx_dir=tts_onnx)
sambert_hifigan_tts_m_bei = TTS(basepath=local_dir_root,
                              voice="zhibei_emo", infer_type=infer_type, onnx_dir=tts_onnx)
sambert_hifigan_tts_m_nan = TTS(basepath=local_dir_root,
                              voice="nansheng", infer_type=infer_type, onnx_dir=tts_onnx)
sambert_hifigan_tts_m_xiao = TTS(basepath=local_dir_root,
                              voice="xiaoxiao", infer_type=infer_type, onnx_dir=tts_onnx)

_TTS_BY_VOICE = {
    "zhitian": sambert_hifigan_tts_wm_tian,
    "zhizhe": sambert_hifigan_tts_m_zhe,
    "zhibei": sambert_hifigan_tts_m_bei,
    "zhiyan": sambert_hifigan_tts_wm_yan,
    "xiaonan": sambert_hifigan_tts_m_nan,
    "xiaoxiao": sambert_hifigan_tts_m_xiao,
}


def delete_folders_starting_with(root_dir, prefix):  
    """  
    删除指定根目录下所有以特定前缀开头的文件夹  
  
    :param root_dir: 要搜索的根目录  
    :param prefix: 文件夹名前缀  
    """  
    for root, dirs, files in os.walk(root_dir, topdown=False):  
        for name in dirs:  
            if name.startswith(prefix):  
                folder_path = os.path.join(root, name)  
                # 删除文件夹及其内容  
                shutil.rmtree(folder_path)  

def _tts_engine_for_voice(sp_voice: str):
    return _TTS_BY_VOICE.get(sp_voice)


def rm_dir(dir_path):
    shutil.rmtree(dir_path)

def _tts_sync_infer(engine: TTS, text: str, upload_dir: str, scale: float) -> str:
    return engine.infer(text=text, source=upload_dir, scale=scale if scale > 0 else 1.0)

def _make_tts_session_upload_dir(source: str) -> str:
    delete_folders_starting_with(current_path, prefix_to_delete)
    if source == "czy-openapi":
        return os.path.join("./outputs/tts/czy", str(uuid.uuid4().hex))
    return os.path.join("./outputs/tts/other", str(uuid.uuid4().hex))


async def _tts_synthesize_to_wav_path(
    text: str, sp_voice: str, upload_dir: str, final_speed: float
) -> Tuple[Optional[str], Optional[str]]:
    engine = _tts_engine_for_voice(sp_voice)
    if engine is None:
        return None, "语音生成失败，请重新选择发音人"
    try:
        path = await asyncio.to_thread(_tts_sync_infer, engine, text, upload_dir, final_speed)
        return path, None
    except Exception as e:
        logger.exception("TTS infer failed: %s", e)
        return None, str(e)


@app.get("/tts")
@app.get("/tts/")
async def tts_ali(text_prompt: str, background_tasks: BackgroundTasks, source: str='None', sp_voice: str = 'zhitian',speed: float = 1.0):
    try:
        # 删除生成的文件
        delete_folders_starting_with(current_path, prefix_to_delete)

        
        if source == "czy-openapi":
            upload_dir = os.path.join('./outputs/tts/czy',str(uuid.uuid4().hex))
        else:
            upload_dir = os.path.join('./outputs/tts/other',str(uuid.uuid4().hex))
            # upload_dir = os.path.join('./outputs/tts/test',str(uuid.uuid4().hex))

        print("========================== source ============================",source)
        # delete_folders_starting_with(current_path, outputs_dir)

        # 男：zhizhe 、zhibei
        # 女：zhitian、zhiyan
        final_speed = round(1/speed,1) if speed !=0 else 1
        tmp_file_name, err = await _tts_synthesize_to_wav_path(
            text_prompt, sp_voice, upload_dir, final_speed
        )
        if err:
            if err == "语音生成失败，请重新选择发音人":
                output_msg = {"status": err}
                print(output_msg)
                return JSONResponse(content=output_msg)
            output_msg = {"status": "语音生成失败", "data": err}
            print(output_msg)
            return JSONResponse(content=output_msg)

        background_tasks.add_task(rm_dir, upload_dir)  # 异步删除文件夹
        
        # return FileResponse(tmp_file_name, filename="output.wav", background=task)
        return FileResponse(tmp_file_name, filename="output.wav")
    except Exception as e:
        output_msg = {"status": "语音生成失败", "data": str(e)}
        print(output_msg)
        return JSONResponse(content=output_msg)


@app.websocket("/tts-stream")
async def tts_stream(ws: WebSocket):
    """
    前端按句逐条发送：每条 {"type":"text","content":"..."} 视为一整句，立即 infer，多段 wav。

    可选查询参数：sp_voice、speed、source（与 GET /tts 一致）。

    客户端 JSON：
      - {"type":"start", ...}  可选，覆盖参数
      - {"type":"text", "content":"..."}  一条消息 = 一句完整话；先发 audio JSON（含 index、text），再发 wav 字节
      - {"type":"end"}  结束会话，{"type":"done","segment_count":N}，关闭连接（此前应已发过至少一句）
    """
    await ws.accept()

    sp_voice = ws.query_params.get("sp_voice", "zhitian")
    try:
        speed = float(ws.query_params.get("speed", "1") or "1")
    except ValueError:
        speed = 1.0
    source = ws.query_params.get("source", "None")

    session_upload_dir: Optional[str] = None
    segment_index = 0

    def final_speed() -> float:
        return round(1 / speed, 1) if speed != 0 else 1.0

    async def ensure_session_dir() -> bool:
        nonlocal session_upload_dir
        if session_upload_dir is not None:
            return True
        try:
            session_upload_dir = await asyncio.to_thread(_make_tts_session_upload_dir, source)
            os.makedirs(session_upload_dir, exist_ok=True)
            return True
        except Exception as e:
            logger.exception("tts-stream session dir: %s", e)
            await ws.send_json({"type": "error", "message": str(e)})
            return False

    async def synthesize_and_send(sentence: str) -> bool:
        """单句合成并发送；失败时返回 False（已发 error）。"""
        nonlocal segment_index
        st = sentence.strip()
        if not st:
            return True
        if not await ensure_session_dir():
            return False
        seg_dir = os.path.join(session_upload_dir, str(uuid.uuid4().hex))
        try:
            os.makedirs(seg_dir, exist_ok=True)
        except Exception as e:
            await ws.send_json({"type": "error", "message": str(e)})
            return False
        path, err = await _tts_synthesize_to_wav_path(
            st, sp_voice, seg_dir, final_speed()
        )
        if err:
            await ws.send_json({"type": "error", "message": err})
            return False
        try:
            with open(path, "rb") as f:
                wav_bytes = f.read()
            idx = segment_index
            segment_index += 1
            await ws.send_json(
                {"type": "audio", "format": "wav", "index": idx, "text": st}
            )
            await ws.send_bytes(wav_bytes)
        finally:
            asyncio.create_task(asyncio.to_thread(rm_dir, seg_dir))
        return True

    try:
        await ws.send_json({"type": "ready"})
    except Exception:
        return

    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg["type"] != "websocket.receive" or not msg.get("text"):
                continue
            try:
                data = json.loads(msg["text"])
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "invalid JSON"})
                continue
            if not isinstance(data, dict):
                continue
            t = data.get("type")
            if t == "start":
                sp_voice = data.get("sp_voice", sp_voice)
                source = data.get("source", source)
                if data.get("speed") is not None:
                    try:
                        speed = float(data["speed"])
                    except (TypeError, ValueError):
                        pass
                await ws.send_json({"type": "started", "sp_voice": sp_voice})
            elif t == "text":
                chunk = data.get("content", "")
                if chunk and not await synthesize_and_send(str(chunk)):
                    await ws.close(code=1003)
                    return
            elif t == "end":
                if segment_index == 0:
                    await ws.send_json({"type": "error", "message": "empty text"})
                    await ws.close(code=1003)
                    return
                await ws.send_json({"type": "done", "segment_count": segment_index})
                if session_upload_dir:
                    d = session_upload_dir
                    session_upload_dir = None
                    asyncio.create_task(asyncio.to_thread(rm_dir, d))
                await ws.close(code=1000)
                return
            else:
                await ws.send_json({"type": "error", "message": f"unknown type: {t}"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("tts-stream: %s", e)
        try:
            await ws.send_json({"type": "error", "message": str(e)})
            await ws.close(code=1011)
        except Exception:
            pass
    finally:
        if session_upload_dir and os.path.isdir(session_upload_dir):
            try:
                await asyncio.to_thread(rm_dir, session_upload_dir)
            except Exception:
                logger.warning("tts-stream cleanup failed: %s", session_upload_dir)



if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, reload=False)