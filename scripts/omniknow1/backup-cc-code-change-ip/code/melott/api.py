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
import os
#from tn.chinese.normalizer import Normalizer
#normalizer = Normalizer(cache_dir="./tn")
from wetext import Normalizer
normalizer = Normalizer(lang="zh", operator="tn", remove_erhua=True)

os.environ['NLTK_DATA'] = '/deploy/code/melott/nltk_data'

torch.npu.set_device("npu:0")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"], 
)


import re
model_root = Path("tts_models")  # 根目录，可按需改动
ckpt_path = "/deploy/models/melo/G_185000.pth"
config_path = "/deploy/models/melo/config_nan.json"

# 加载模型
model = TTS(language="ZH_MIX_EN", config_path=str(config_path), ckpt_path=str(ckpt_path),device="npu:0",use_hf=False)

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
    text = text.replace(".","点")
#    text = text.replace("","百分之")
    return text



@app.get("/tts")
async def tts_get(
    text_prompt: str = Query(..., description="输入文本"),
    sp_voice: str = Query("zm_029", description="语音模型名（例如 zm_082, zhitian 等）"),
    speed: float = Query(1.0, description="语速 (默认1.0)")
):
    try:

        # 创建输出目录
        output_dir = Path("outputs") / sp_voice
        output_dir.mkdir(parents=True, exist_ok=True)

        # 合成输出路径
        filename = f"{uuid.uuid4().hex}.wav"
        output_path = output_dir / filename

        print(model.hps.data.spk2id.items())

        # 查找指定 speaker_id
#        spk_id = model.hps.data.spk2id['ZH']i
#        if spk_id is None:
#            raise ValueError(f"找不到说话人 {sp_voice} 的 ID")
        text_prompt = normalizer.normalize(text_prompt)
        text_prompt = process_text(text_prompt)
        # 调用合成方法
        model.tts_to_file(text_prompt, speaker_id=0, output_path=str(output_path), speed=speed)

        return FileResponse(
            path=str(output_path),
            media_type="audio/wav",
            filename=output_path.name
        )

    except Exception as e:
        logging.exception("TTS 合成失败")
        return JSONResponse(status_code=500, content={"error": str(e)})



def main():
    uvicorn.run(app, host='0.0.0.0', port=7871, workers=1)


if __name__ == '__main__':
    main()
