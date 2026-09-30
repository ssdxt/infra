docker-compose -f docker-compose.yaml up -d
docker-compose -f docker-compose.yaml down

## **启动方式见bash文件夹（按需调整）**

## 环境打包
### embedding、rerank 和大模型的环境
1. conda create -n vllm python==3.12
2. pip install vllm -i https://pypi.tuna.tsinghua.edu.cn/simple
3. bash里有embedding和rerank的启动脚本，看着改改

### mineru环境
1. nvidia显卡 docker安装文档如下
https://opendatalab.github.io/MinerU/zh/quick_start/docker_deployment/

2. 其他显卡 docker安装文档如下
https://opendatalab.github.io/MinerU/zh/quick_start/docker_deployment/

3. 端口号按bash中的端口改

### api、img_service环境
1. nvidia显卡
conda create -n parser python==3.12
conda activate parser
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

2. 其他显卡


### speech （按需安装


### libreoffice也要安装

### 注意：parser/rag/.env中的 IMG_DOWNLOAD_DIR 一定要改

## 普通模式
 - docx，chunk_size，chunk_overlap，delimiters 
 - pdf， chunk_size，chunk_overlap, delimiters  
 - txt,  chunk_size，chunk_overlap, delimiters
 - json，chunk_size
 - md，  chunk_size，chunk_overlap


## 专业模式
 - OFFICE_FORMATS = {".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"}
 - IMAGE_FORMATS = {".png", ".jpeg", ".jpg", ".bmp", ".tiff", ".tif", ".gif", ".webp"}
 - TEXT_FORMATS = {".txt", ".md"}
 

conda activate /mnt/ddata2/cc007/envs/vllm-qwen3

CUDA_VISIBLE_DEVICES=6 vllm serve /mnt/ddata2/cc007/MinerU-2.6.6/mineru/model/models/MinerU2___5-2509-1___2B \
--trust-remote-code \
--dtype float16 \
--cpu-offload-gb 4 \
--max-model-len 8192 \
--gpu-memory-utilization 0.8 \
--port 8406