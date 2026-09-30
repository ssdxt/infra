import os
import uuid
import uvicorn
import pydantic
from pydantic import BaseModel
from scipy.io.wavfile import write as write_wav
from fastapi import FastAPI, File, UploadFile, Depends, Form,BackgroundTasks
from starlette.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask
from typing import Any
import re
from fastapi import HTTPException
import asyncio
import tempfile
import logging
# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
import time
import soundfile as sf
import shutil
import re
import numpy as np
import cn2an
current_path = os.getcwd()

prefix_to_delete = 'uploaded_files'  
outputs_dir = "outputs"

from fastapi.middleware.cors import CORSMiddleware

# os.environ['CUDA_VISIBLE_DEVICES'] = '1'
# os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
# os.environ['CUDA_MODULE_LOADING'] = 'LAZY'
# import pycuda.driver as cuda0
# cuda0.init()
# cfx = cuda0.Device(0).make_context()

import io
from pydub import AudioSegment
import torch
import torch_npu
from torch_npu.contrib import transfer_to_npu
#torch.set_num_threads(32)
from funasr import AutoModel


# asr模型部分
# 只改这个路径 、 infer_type和 tts_onnx 就可以了,其他不用改
model_path = "/deploy/models/speech/iic/"
infer_type = "torch"  # torch or trt

# TTS
#local_dir_root = model_path+"speech_sambert-hifigan_tts_zh-cn_16k"  
#tts_onnx = "/deploy/models/speech/sambert-hifigan_onnx"

asr_model = AutoModel(
                    model=model_path+"speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
                    #model="iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
                    # model = model_path+"SenseVoiceSmall",
                    # model_revision="v2.0.4",
                    #vad_model=model_path+"speech_fsmn_vad_zh-cn-16k-common-pytorch", vad_model_revision="v2.0.4",
                    #punc_model=model_path+"punc_ct-transformer_cn-en-common-vocab471067-large", punc_model_revision="v2.0.4",
                    vad_model=model_path + "speech_fsmn_vad_zh-cn-16k-common-pytorch", vad_model_revision="v2.0.4",
                    punc_model=model_path + "punc_ct-transformer_cn-en-common-vocab471067-large", punc_model_revision="v2.0.4",
                    vad_kwargs={"max_single_segment_time": 30000},
                    disable_update=True,
#                    infer_type="torch", #修改
                    use_local=True,  # 修改
                    device="cuda:0",
                    # spk_model="cam++"
                    )

model2 = AutoModel(model=model_path + "speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch", model_revision="v2.0.4",
                  vad_model=model_path + "speech_fsmn_vad_zh-cn-16k-common-pytorch", vad_model_revision="v2.0.4",
                  punc_model=model_path + "punc_ct-transformer_zh-cn-common-vocab272727-pytorch", punc_model_revision="v2.0.4",
                  #model=os.path.join("iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"), model_revision="v2.0.4",
                  #vad_model=os.path.join("iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"), vad_model_revision="v2.0.4",
                  #punc_model=os.path.join("iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch"), punc_model_revision="v2.0.4",
                  disable_update=True,
                  sentence_timestamp=True
                  # spk_model="cam++", spk_model_revision="v2.0.2",
                  )

# 阿里tts模型

# infer_type = "torch"
# zhizhe_emo（男） 、zhibei_emo（男）
# zhitian_emo（女n，默认）、zhiyan_emo（女）
class BaseResponse(BaseModel):
    code: int = pydantic.Field(200, description="API status code")
    msg: str = pydantic.Field("success", description="API status message")
    data: Any = pydantic.Field(None, description="API data")

    class Config:
        schema_extra = {
            "example": {
                "code": 200,
                "msg": "success",
            }
        }

app = FastAPI(title="STT and TTS server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

def rm_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)

        
def rm_dir(dir_path):
    import shutil
    shutil.rmtree(dir_path)
        

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

def merge_intervals(intervals):
    # 区间合并
    if not intervals:
        return []
    merged = []
    current_interval = intervals[0]

    for next_interval in intervals[1:]:
        if current_interval[1]+100 >= next_interval[0]:
            current_interval = [current_interval[0], next_interval[1]]
        else:
            merged.append(current_interval)
            current_interval = next_interval
    
    merged.append(current_interval)
    return merged



def remove_extra_punctuation(text):
    # 定义中文和英文的标点符号
    punctuation = r'[,.!?;:。，！？；：]'
    
    # 使用正则表达式匹配连续的标点符号
    pattern = rf'({punctuation})(?:\1+|\s*(?:{punctuation})+)'
    
    # 如果找到匹配，只保留第一个标点符号
    cleaned_text = re.sub(pattern, r'\1', text)
    
    return cleaned_text

def replace_ap(match):
    prefix = "AP"  # 统一替换为大写AP
    number = match.group(2)

    # 判断是否为汉字数字，若是则转换为阿拉伯数字
    if number.strip().isdigit():
        arabic_number = number  # 如果不是汉字数字，直接返回原数字

    else:
        # arabic_number = cn2an.cn2an(number, "smart")  # 自动判断数字类型并转换
        arabic_number = cn2an.cn2an(number, "smart")  # 自动判断数字类型并转换


    return f"{prefix}{arabic_number}"


#@app.post("/asr/")
#@app.post("/asr")
async def asr(background_tasks: BackgroundTasks,file: UploadFile = File(...),source: str = Form("None")):
    try:
        upload_dir = os.path.join('./outputs/asr','uploaded_files_'+ str(uuid.uuid4().hex))
        os.makedirs(upload_dir, exist_ok=True)

        with open(f"{upload_dir}/{file.filename}", "wb") as f:
            f.write(await file.read())

        result = asr_model.generate(
                input="{}/{}".format(upload_dir, file.filename),
                use_itn=True,
                batch_size_s=256,
                merge_vad=True,
                merge_length_s=15,
                disable_pbar=True,
                hotword='./hotword.txt',
            )
        logger.debug(f"question 处理前：( {result[0]['text']})")
        
        if result:
            pattern = r'(ap|Ap|AP|aP)([0-9一二三四五六七八九十百千万]+)'
            result_str = re.sub(pattern, replace_ap, result[0]['text'].strip().replace(" ",""))
            
            output_msg = {"status": "语音识别完成", "data": result_str}
            background_tasks.add_task(rm_dir, upload_dir)  # 异步删除文件夹

            return JSONResponse(content=output_msg)
        else:
            output_msg = {"status": "语音识别失败", "data": str("")}
            logger.debug(f'{"status": "语音识别失败", "data": str(e)}')
            
            return JSONResponse(content=output_msg)
        
    except Exception as e:
        output_msg = {"status": "语音识别失败", "data": str(e)}
        print(output_msg)
        return JSONResponse(content=output_msg)


@app.post("/asr/")
@app.post("/asr")
async def asr(background_tasks: BackgroundTasks, file: UploadFile = File(...), source: str = Form("None")):
    try:
        # 从上传文件直接读取字节内容
        file_bytes = await file.read()

        # 使用 soundfile 直接从 bytes 解码为 waveform 和 sr
        audio = AudioSegment.from_file(io.BytesIO(file_bytes))

        # 强制转换为 16kHz、单声道、16位
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

        # 转成 numpy（注意数据类型必须是 int16）
        audio_np = np.array(audio.get_array_of_samples()).astype(np.float32) / 32768.0

        # 直接传 numpy 数组进行识别，无需保存到磁盘
        result = asr_model.generate(
            input=audio_np,
            use_itn=True,
            batch_size_s=256,
            merge_vad=True,
            merge_length_s=15,
            disable_pbar=True,
            hotword='./hotword.txt',
        )

        logger.debug(f"question 处理前：( {result[0]['text']})")

        if result:
            pattern = r'(ap|Ap|AP|aP)([0-9一二三四五六七八九十百千万]+)'
            result_str = re.sub(pattern, replace_ap, result[0]['text'].strip().replace(" ",""))
            output_msg = {"status": "语音识别完成", "data": result_str}
            return JSONResponse(content=output_msg)
        else:
            return JSONResponse(content={"status": "语音识别失败", "data": ""})

    except Exception as e:
        return JSONResponse(content={"status": "语音识别失败", "data": str(e)})



# 转换音频采样率#
def convert_to_16000(file_path: str) -> str:
    try:
        audio = AudioSegment.from_file(file_path)
        audio = audio.set_frame_rate(16000)
        
        # 创建新的临时文件存储转换后的音频
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            audio.export(temp_file.name, format="wav")
            return temp_file.name
    except Exception as e:
        raise Exception(f"音频转换失败: {str(e)}")

@app.post("/wav_asr_vad/")
@app.post("/wav_asr_vad")
async def asr_vad(file: UploadFile = File(...),source: str = Form("None")):
    try:
        # 读取文件内容
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: 请换个文件试试")
    
    converted_file_path=None
    temp_file_path=None

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
        temp_file.write(file_content)
        temp_file_path = temp_file.name
        # print(temp_file_path)
       
       # 转换采样率为 16000 Hz
        converted_file_path = convert_to_16000(temp_file_path)
    try:
        res = model2.generate(input=converted_file_path, 
                    batch_size_s=300, 
                    # hotword='魔搭',
                    disable_pbar=True,
                )
        text = res[0]['text']
        # timestamp = res[0]['timestamp']
        timestamps = []
        for sentence in res[0]['sentence_info']:
            data = {
                "text" : sentence['text'],
                "start": sentence['start'],
                "end": sentence['end']
            }
            timestamps.append(data)

        # print(res)
        # 合并区间
        # merged_intervals = merge_intervals(timestamp)
        output_msg = {"status": 200, "text": text, "data": timestamps}
        # output_msg = {"status": "音频识别完成", "text": text, "timestamp": timestamps}
        return JSONResponse(content=output_msg)

    except Exception as e:
        # raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理失败: 该文件无音轨或者文件损坏，请换个文件试试")
    finally:
        # 删除临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if converted_file_path and os.path.exists(converted_file_path):
            os.remove(converted_file_path)

async def extract_audio(video_path: str, output_audio_path: str):
    # 构建 ffmpeg 命令
    command = [
        'ffmpeg',
        '-i', video_path,          # 输入视频文件
        '-q:a', '0',               # 设置音频质量（0 是最高质量）
        '-map', 'a',               # 只处理音频流
        output_audio_path          # 输出音频文件
    ]
    
    # 创建子进程并异步执行命令
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    # 检查命令是否成功执行
    if process.returncode != 0:
        raise Exception(f"FFmpeg 命令执行失败: {stderr.decode()}")

    return {"status": "success", "output_audio_path": output_audio_path}


@app.post("/mp4_asr_vad/")
@app.post("/mp4_asr_vad")
async def asr_vad(file: UploadFile = File(...),source: str = Form("None")):
    try:
        # 读取文件内容
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: 请换个文件试试")

    temp_file_path = None
    audio_path = None
    converted_file_path = None

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
        temp_file.write(file_content)
        temp_file_path = temp_file.name

    try:
    
        audio = await extract_audio(temp_file_path, temp_file_path[:-3]+'wav')
        audio_path = audio['output_audio_path']
        converted_file_path = convert_to_16000(audio_path)

        # print(audio_path)
        res = model2.generate(input=converted_file_path, 
                            batch_size_s=300, 
                            # hotword='魔搭',
                            disable_pbar=True,
                        )
        text = res[0]['text']
        # timestamp = res[0]['timestamp']
        timestamps = []
        for sentence in res[0]['sentence_info']:
            data = {
                "text" : sentence['text'],
                "start": sentence['start'],
                "end": sentence['end']
            }
            timestamps.append(data)

        # print(res)
        # 合并区间
        # merged_intervals = merge_intervals(timestamp)
        # output_msg = {"status": "视频识别完成", "text": text, "timestamp": timestamps}
        output_msg = {"status": 200, "text": text, "data": timestamps}

        return JSONResponse(content=output_msg)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理失败: 该文件无音轨或者文件损坏，请换个文件试试")
        # raise HTTPException(status_code=500, detail=f"处理失败: 该文件media_type="audio/wav"无音轨或者文件损坏，请换个文件试试，{str(e)}")
    finally:
        # 删除临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
        if converted_file_path and os.path.exists(converted_file_path):
            os.remove(converted_file_path)


from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import os
import torch
import torch_npu
import uuid
import logging
import uvicorn
from melo.api import TTS  # 替换为你实际的类导入
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import os
import re
#from tn.chinese.normalizer import Normalizer
#normalizer = Normalizer(cache_dir="./tn")
from wetext import Normalizer
normalizer = Normalizer(lang="zh", operator="tn", remove_erhua=True)
os.environ['NLTK_DATA'] = '/deploy/code/melott/nltk_data'


#app = FastAPI()

#app.add_middleware(
#    CORSMiddleware,
#    allow_origins=["*"],  
#    allow_credentials=True,
#    allow_methods=["*"],  
#    allow_headers=["*"], 
#)



model_root = Path("tts_models")  # 根目录，可按需改动
ckpt_path_nv = "/deploy/models/melo/checkpoint.pth"
config_path_nv = "/deploy/models/melo/config.json"

#ckpt_path_nan = "/deploy/models/melo/checkpoint_nan.pth"
ckpt_path_nan = "/deploy/models/melo/G_185000.pth"
config_path_nan = "/deploy/models/melo/config_nan.json"

# 加载模型
model_nv = TTS(language="ZH_MIX_EN", config_path=str(config_path_nv), ckpt_path=str(ckpt_path_nv),device='npu:0',use_hf=False)
model_nan = TTS(language="ZH_MIX_EN", config_path=str(config_path_nan), ckpt_path=str(ckpt_path_nan),device='npu:0',use_hf=False)

# 数字到中文映射
num_map = {
    "0": "零", "1": "一", "2": "二", "3": "三", "4": "四",
    "5": "五", "6": "六", "7": "七", "8": "八", "9": "九"
}

def process_text(text: str) -> str:
    # 1. 数字转中文
#    for digit, chinese in num_map.items():
#        text = text.replace(digit, chinese)

    # 2. 在大写字母之间加空格（正则保证每个字母单独分开）
    text = re.sub(r'([A-Z])(?=[A-Z])', r'\1 ', text)

    # 3. 数字(已转中文)和大写字母之间加空格
    # 中文数字和大写字母之间
    text = re.sub(r'([零一二三四五六七八九])(?=[A-Z])', r'\1 ', text)
    text = re.sub(r'([A-Z])(?=[零一二三四五六七八九])', r'\1 ', text)
    return text

#@app.get("/tts")
#async def tts_get(
#    text_prompt: str = Query(..., description="输入文本"),
#    sp_voice: str = Query("zhitian", description="语音模型名（例如 zm_082, zhitian 等）"),
#    speed: float = Query(1.0, description="media_type="audio/wav"语速 (默认1.0)")
#):
#    try:

        # 创建输出目录
#        output_dir = Path("outputs") / sp_voice
#        output_dir.mkdir(parents=True, exist_ok=True)

        # 合成输出路径
#        filename = f"{uuid.uuid4().hex}.wav"
#        output_path = output_dir / filename

        #print(model.hps.data.spk2id.items())
#        text_prompt = normalizer.normalize(text_prompt)

#        text_prompt = process_text(text_prompt)
#        if sp_voice=='zhitian':
#            model_nan.tts_to_file(text_prompt, speaker_id=0, output_path=str(output_path), speed=speed)
#        else:
#            print('zou zhizhe')
            # 查找指定 speaker_id
#            spk_id = model_nv.hps.data.spk2id['ZH']
            # 调用合成方法
#            model_nv.tts_to_file(text_prompt, speaker_id=spk_id, output_path=str(output_path), speed=speed)

#        return FileResponse(
#            path=str(output_path),
#            media_type="audio/wav",
#            filename=output_path.name
#        )

#    except Exception as e:
#        logging.exception("TTS 合成失败")
#        return JSONResponse(status_code=500, content={"error": str(e)})


# 允许的中文标点
ALLOWED_PUNCTUATION = "。！？…，；：“”‘’（）—·《》、"

def clean_text_input(text: str) -> str:
    """
    过滤非法字符，只保留：
    - 中文字符
    - 英文和数字
    - 常用中文标点
    """
    cleaned = []
    for c in text:
        if '\u4e00' <= c <= '\u9fff' or c.isalnum() or c in ALLOWED_PUNCTUATION or c.isspace():
            cleaned.append(c)
    return ''.join(cleaned)

@app.get("/tts")
async def tts_get(
    text_prompt: str = Query(..., description="输入文本"),
    sp_voice: str = Query("zhitian", description="语音模型名（例如 zm_082, zhitian 等）"),
    speed: float = Query(1.0, description="语速 (默认1.0)")
):
    try:
        # 文本预处理
        text_prompt = text_prompt.replace("-"," ")
        text_prompt = normalizer.normalize(text_prompt)
        text_prompt = process_text(text_prompt)
        text_prompt = clean_text_input(text_prompt)
        if not text_prompt.strip():
            return JSONResponse(status_code=400, content={"error": "文本内容为空或全部非法字符"})

        # 创建输出目录
        output_dir = Path("outputs") / sp_voice
        output_dir.mkdir(parents=True, exist_ok=True)

        # 合成输出路径
        media_type="audio/wav"      
        filename = f"{uuid.uuid4().hex}.wav"
        output_path = output_dir / filename

        # 调用 TTS
        if sp_voice == 'zhitian':
            model_nan.tts_to_file(text_prompt, speaker_id=0, output_path=str(output_path), speed=speed)
#            audio_buf = model_nan.tts_to_file(text_prompt, speaker_id=0, output_path=str(output_path), speed=speed)
        else:
            # 查找指定 speaker_id
            spk_id = model_nv.hps.data.spk2id['ZH']
            model_nv.tts_to_file(text_prompt, speaker_id=spk_id, output_path=str(output_path), speed=speed)
#            audio_buf = model_nv.tts_to_file(text_prompt, speaker_id=spk_id, output_path=str(output_path), speed=speed)
        return FileResponse(
            path=str(output_path),
            media_type="audio/wav",
            filename=output_path.name
        )
#        return StreamingResponse(audio_buf,media_type="audio/wav")

    except AssertionError as e:
        logging.exception("TTS 文本处理出错")
        print('出错文本为：',text_prompt)
        return JSONResponse(status_code=400, content={"error": "文本包含非法字符或标点"})

    except RuntimeError as e:
        logging.exception("TTS NPU 推理失败")
        print('出错文本为：',text_prompt)
        return JSONResponse(status_code=500, content={"error": "设备资源不足或推理失败，请重试或缩短文本"})

    except Exception as e:
        logging.exception("TTS 合成失败")
        print('出错文本为：',text_prompt)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.on_event("startup")
async def startup_event():
    logger.info("正在进行模型预热...")

    # 调用 TTS 模型进行一次预热
    try:
        text_prompt = "你好"
        output_dir = Path("outputs") / "preheat"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "preheat.wav"
#        spk_id = model.hps.data.spk2id['ZH']

#        model_nv.tts_to_file(text_prompt, speaker_id=spk_id, output_path=str(output_path), speed=1.0)
        model_nan.tts_to_file(text_prompt, speaker_id=0, output_path=str(output_path), speed=1.0)
        logger.info("TTS 预热完成")
    except Exception as e:
        logger.warning(f"TTS 预热失败: {e}")

    # 调用 ASR 模型进行一次预热
    try:
        dummy_audio = str(output_path)
        res = asr_model.generate(
            input=dummy_audio,
            use_itn=True,
            batch_size_s=256,
            merge_vad=True,
            merge_length_s=15,
            disable_pbar=True,
        )
        logger.info(f"ASR 预热结果: {res[0]['text']}")

    except Exception as e:
        logger.warning(f"ASR 预热失败: {e}")

    if output_path.exists():
        os.remove(output_path)




def main():
    uvicorn.run(app, host='0.0.0.0', port=7870, workers=1,ssl_keyfile="./key.pem", ssl_certfile="./cert.pem")


if __name__ == '__main__':
    main()


