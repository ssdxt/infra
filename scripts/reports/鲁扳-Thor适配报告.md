# 鲁扳 AI 装备智能一体机 — NVIDIA Jetson Thor 适配报告

> 版本：v1.0（2026-08-31）
> 适用范围：鲁扳 AI 装备智能一体机产品在 NVIDIA Jetson Thor（128G 统一内存）上的完整适配

---

## 目录

1. [产品与硬件概述](#1-产品与硬件概述)
2. [软件环境](#2-软件环境)
3. [部署架构总览](#3-部署架构总览)
4. [模型部署详情](#4-模型部署详情)
5. [部署注意事项](#5-部署注意事项)
6. [常见修改点](#6-常见修改点)
7. [全量部署文档](#7-全量部署文档)
8. [测试情况](#8-测试情况)
9. [性能测试报告](#9-性能测试报告)
10. [已知问题与后续建议](#10-已知问题与后续建议)

---

## 1. 产品与硬件概述

### 1.1 产品

- **产品名称**：鲁扳 AI 装备智能一体机
- **Web 入口**：`https://192.168.21.105:8376`（HTTPS，自签名证书）
- **登录账号**：`su / admin123`（示例）
- **核心能力**：智能对话、知识库图谱（KG）、故障树分析、文档解析（MinerU）、语音识别（ASR）、语音合成（TTS）、向量检索（Milvus）、音视频等

### 1.2 目标硬件：NVIDIA Jetson Thor

| 项目 | 规格 |
|---|---|
| 处理器 | NVIDIA Jetson Thor（AGX Thor） |
| 内存 | 128 GB 统一内存（LPDDR5X，系统可见 122.8 GiB） |
| 架构 | ARM64（aarch64） |
| 系统 | Ubuntu 24.04（noble） |
| 磁盘 | NVMe 3.7 TB（当前可用 ~329 GB） |
| 网络 | 192.168.21.105（手动管理网络 manualai_network 172.18.0.0/24） |

### 1.3 硬件关键特性（影响部署的核心约束）

1. **统一内存架构**：无独立显存（VRAM），GPU 与 CPU 共享 128G 物理内存。vLLM 通过 CUDA UVM（统一虚拟内存）分配，`free` 命令显示的 used 包含 UVM 预留，**真实物理占用需看 RSS**。
2. **启动内存检查严格**：vLLM 启动时要求可用内存 ≥ `gpu_memory_utilization × 122.83G`，否则报 `ValueError: Free memory ... less than desired GPU memory utilization`。
3. **GPU 进程残留**：容器异常退出后 UVM 残留不会自动释放，**每次停止 GPU 容器后必须执行 `/usr/local/bin/cleanup-mem.sh`**（drop_caches + 杀残留进程）释放 UVM，否则后续容器启动失败。
4. **CUDAGraph 无收益**：Jetson 上 enforce-eager 与 CUDAGraph 性能持平（27B 实测 113ms vs 111ms），但 eager 启动快一倍、无编译风险，**推荐 enforce-eager**。
5. **jtop GPU MEM 显示 0k**：Thor 的 nvmap 不追踪 vLLM 的 CUDA 分配，GPU 内存监控以 `free`/`nvidia-smi`/`ps RSS` 为准。

---

## 2. 软件环境

| 组件 | 版本/说明 |
|---|---|
| vLLM（Jetson 定制） | `ghcr.io/nvidia-ai-iot/vllm:latest-jetson-thor`（v0.16.0rc2.dev479） |
| Python | 3.12（容器内）/ 3.13（ai_server 后端） |
| PyTorch（my-pytorch-embed） | 2.10.0a0+nv25.11（Jetson 定制，ASR 基础镜像） |
| PyTorch（vllm 镜像） | 2.10.0 + torchaudio 2.10.0（匹配，TTS 基础镜像） |
| Docker Compose | 各服务独立 compose（llm/、depends_on/、Omniknow/） |
| 模型推理包 | qwen-asr 0.0.6 / qwen-tts 0.1.1（transformers 后端） |

---

## 3. 部署架构总览

### 3.1 网络拓扑（manualai_network 172.18.0.0/24）

| IP | 容器 | 端口（host） | 用途 |
|---|---|---|---|
| 172.18.0.120 | qwen-nvidia-vllm-27b | 8020 | **对话 LLM**（Qwen3.8-27B-FP8 + MTP×4，业务统一入口） |
| 172.18.0.121 | qwen-embedding | 8021 | 文本向量化（Qwen3-Embedding-0.6B） |
| 172.18.0.122 | qwen-rerank | 8022 | 重排序（Qwen3-Reranker-0.6B） |
| 172.18.0.123 | qwen3-asr | 8023/8443 | 语音识别（Qwen3-ASR-1.7B，HTTP+HTTPS 双协议） |
| 172.18.0.124 | qwen3-tts | 8024 | 语音合成（Qwen3-TTS-12Hz-0.6B，vllm-omni WS 协议） |
| 172.18.0.21 | mineru-api | 8000 | 文档解析（MinerU 2.7.6） |
| 172.18.0.130 | assistant | 8366 | 业务助手（对话/知识库/故障树） |
| 172.18.0.131 | ai_server_backend | 8375 | 业务后端（任务/图谱/语音网关） |
| 172.18.0.132 | ai_server_worker | - | 异步任务执行 |
| 172.18.0.133 | ai_server_beater | - | 定时任务 |
| 172.18.0.134 | parser | 8008 | 解析回调服务 |
| 172.18.0.135 | img_server | 18080 | 图像服务（昇腾 NPU 镜像） |
| 172.18.0.11 | ai_mysql | 8306 | MySQL 8.0（业务库 ai_server） |
| 172.18.0.12 | ai_redis | 8379 | Redis 8.4 |
| 172.18.0.13 | milvus-etcd | - | Milvus 元数据 |
| 172.18.0.14 | milvus-standalone | 9091 | 向量库 Milvus 2.6 |
| 172.18.0.15 | ai_minio | 9002 | 对象存储 MinIO |
| host | ai_nginx | 8376 | Nginx（HTTPS 前端 + 反向代理） |
| 172.17.0.2 | attu | 7090 | Milvus Web GUI（可选） |

### 3.2 业务请求链路

```
浏览器(https://192.168.21.105:8376)
  ├─ /knowledge_api/*  → assistant(172.18.0.130:8366)
  ├─ /backend/*        → ai_server_backend(172.18.0.131:8375)   [含语音网关]
  │     ├─ ASR: POST /v1/audio/transcriptions → qwen3-asr(172.18.0.123:8023)
  │     └─ TTS: ws://172.18.0.124:8024/v1/audio/speech/stream  → qwen3-tts
  ├─ /api/*            → ai_server_backend(172.18.0.131:8375)
  └─ /knowledge2_api/* → 172.18.0.114:18081（外部/其他）
ai_server_backend → 对话 LLM(172.18.0.120:8020, OpenAI 兼容)
```

### 3.3 目录结构

```
/ManualAI/
├── llm/                    # LLM 相关服务（compose + 脚本）
│   ├── base/               # embedding + rerank
│   ├── qwen3.8-27b/        # 对话 LLM（27B + MTP）
│   ├── qwen3-asr/          # ASR（Dockerfile/server/compose/ssl/test）
│   ├── qwen3-tts/          # TTS（Dockerfile/server/compose/test）
│   ├── qwen3.5/            # 9B（已注释停用）
│   └── mineru/             # 文档解析
├── models/                 # 全部模型权重
├── depends_on/             # 基础依赖（mysql/redis/milvus/minio/nginx）
│   └── data/nginx/         # nginx 配置 + SSL 证书
├── Omniknow/               # 业务栈（assistant/ai_server/parser）
│   └── code/server/.env    # 业务环境配置（关键！）
└── tools/                  # 运维工具（bench 脚本、模型下载器）
```

---

## 4. 模型部署详情

### 4.1 对话 LLM — Qwen3.8-27B-FP8（主力，端口 8020）

- **权重**：`/ManualAI/models/Qwen3.8-27B-FP8`（FP8 量化，29 GB，66 safetensors）
- **架构**：`Qwen3_5ForConditionalGeneration`（Qwen3.5 原生多模态，词表 248320）
- **推理框架**：vLLM（Jetson 定制镜像）+ **MTP 投机解码**（模型自带多 token 预测头）
- **关键参数**（`/ManualAI/llm/qwen3.8-27b/docker-compose.yaml`）：

```yaml
command: >
  vllm serve /ManualAI/models/Qwen3.8-27B-FP8
  --served-model-name Qwen3.5
  --dtype auto --port 8020 --tensor-parallel-size 1
  --max-num-seqs 8 --max-model-len 16384 --max-num-batched-tokens 8192
  --gpu-memory-utilization 0.55
  --trust-remote-code --enable-prefix-caching --block-size 32
  --enforce-eager
  --speculative-config '{"method": "mtp", "num_speculative_tokens": 4}'
  --default-chat-template-kwargs '{"enable_thinking": false}'
  --enable-auto-tool-choice --tool-call-parser qwen3_xml
  --chat-template /ManualAI/models/Qwen3.8-27B-FP8/chat_template_lenient.jinja
```

- **性能**：TPOT 62-71ms，吞吐 ~14-15.5 tok/s（约 840-930 token/分钟）
- **角色**：BASIC_MODEL / VISION_MODEL / KG_LLM_MODEL 全部指向 `http://172.18.0.120:8020/v1`，model 名 `Qwen3.5`

### 4.2 向量 / 重排（端口 8021 / 8022）

```yaml
# embedding: /ManualAI/models/Qwen3-Embedding-0.6B
vllm serve ... --runner pooling --port 8021 --hf_overrides '{"matryoshka_dimensions":[1024]}'
               --gpu-memory-utilization 0.08 --max-model-len 32768
# rerank: /ManualAI/models/Qwen3-Reranker-0.6B
vllm serve ... --port 8022 --hf_overrides '{"architectures":["Qwen3ForSequenceClassification"],...}'
               --gpu-memory-utilization 0.1 --max-model-len 32768 --enforce-eager
```

### 4.3 ASR — Qwen3-ASR-1.7B（端口 8023 HTTP + 8443 HTTPS）

- **权重**：`/ManualAI/models/Qwen3-ASR-1.7B`（4.4 GB）
- **基础镜像**：`my-pytorch-embed:latest`（torch 2.10 定制，cuda 已验证）
- **镜像**：`qwen3-asr-jetson:latest`（含 ffmpeg + qwen-asr 0.0.6）
- **服务**：`asr_server.py`（FastAPI，**挂载进容器，改代码免重建**）
- **端点**：
  - `POST /v1/audio/transcriptions` — **OpenAI 兼容**（业务协议）：multipart `file` + `model` → `{"text":"..."}`
  - `POST /asr` — 自定义（测试用）：multipart `file` + `language`
  - `GET /health` — 健康检查
- **格式支持**：任意音频（mp3/wav/m4a），内部 **ffmpeg 转 16k 单声道 wav** 后识别
- **HTTPS**：证书挂载 `/app/ssl/`，存在则自动启用 8443 HTTPS；HTTP 8023 保持（业务 .env 不变）
- **compose 挂载**：

```yaml
volumes:
  - /ManualAI/models:/ManualAI/models
  - /ManualAI/llm/qwen3-asr/ssl:/app/ssl
  - /ManualAI/llm/qwen3-asr/asr_server.py:/app/asr_server.py
ports:
  - "8023:8023"
  - "8443:8443"
```

### 4.4 TTS — Qwen3-TTS-12Hz-0.6B-CustomVoice（端口 8024）

- **权重**：`/ManualAI/models/Qwen3-TTS-12Hz-0.6B-CustomVoice`（2.4 GB，含 speech_tokenizer）
- **基础镜像**：`ghcr.io/nvidia-ai-iot/vllm:latest-jetson-thor`（**torch 2.10 + torchaudio 2.10 匹配**，cuda 可用）
- **镜像**：`qwen3-tts-jetson:latest`（qwen-tts 0.1.1 + sox/onnxruntime/gradio）
- **端点**：
  - `WS /v1/audio/speech/stream` — **vllm-omni 协议**（业务）：`session.config → input.text* → input.done → audio.start + PCM帧 + audio.done + session.done`
  - `POST /tts` — HTTP（测试用）→ audio/wav
- **输出**：PCM 16bit 单声道（float32→int16），`sample_rate` 在 audio.start 中声明
- **注意**：qwen-tts 0.1.1 无流式 API，实现为整段合成后分帧输出（协议兼容，首包延迟=整句合成时间）

### 4.5 MinerU 文档解析（端口 8000）

- 镜像：`mineru-gpu-dustynv:v2.7.6-arm64-transformers`
- 环境：`MINERU_HYBRID_BATCH_RATIO=1`、`MINERU_VIRTUAL_VRAM_SIZE=7`
- 业务 parser 以 `backend="pipeline"` 方式调用（celery 模式已禁用）

### 4.6 业务栈（Omniknow）

- assistant（.130:8366）、ai_server_backend（.131:8375）、worker/beater、parser（.134:8008）、img_server（.135:18080）
- 关键配置：`/ManualAI/Omniknow/code/server/.env`

```
PARSER_API_URL=http://172.18.0.134:8008
TRAINING_BASE_URL=http://172.18.0.130:8366
AUDIO_ASR_BASE_URL=http://172.18.0.123:8023
AUDIO_ASR_MODEL=qwen3-asr
AUDIO_TTS_BASE_URL=ws://172.18.0.124:8024
AUDIO_TTS_MODEL=qwen3-tts
AUDIO_TTS_VOICE=vivian
DATABASE_HOST=172.18.0.11  REDIS_HOST=172.18.0.12  OSS_HOST=172.18.0.15  MILVUS_HOST=172.18.0.14
```

### 4.7 模型清单（/ManualAI/models/）

| 模型 | 大小 | 用途 | 状态 |
|---|---|---|---|
| Qwen3.8-27B-FP8 | 29G | 对话/多模态/图谱（8020） | ✅ 在用 |
| Qwen3.5-9B-AWQ | 12G | 历史对话模型 | ⏸ 停用（compose 注释） |
| Qwen3-Embedding-0.6B | 1.2G | 向量化（8021） | ✅ 在用 |
| Qwen3-Reranker-0.6B | 1.2G | 重排（8022） | ✅ 在用 |
| Qwen3-ASR-1.7B | 4.4G | 语音识别（8023） | ✅ 在用 |
| Qwen3-TTS-12Hz-0.6B-CustomVoice | 2.4G | 语音合成（8024） | ✅ 在用 |
| Qwen3-0.6B | 1.5G | draft 候选（词表 151936） | ⏸ 备用 |
| Qwen3.5-4B | 9.9G | draft 候选（词表 248320） | ⏸ 备用 |
| Qwen3.8-27B | 48G | BF16 原版 | ⏸ 备用 |
| dinov3-vitl16-pretrain-lvd1689m | 1.2G | 视觉特征 | ⏸ 备用 |

---

## 5. 部署注意事项

### 5.1 内存与 UVM（最重要）

1. **每次停止 GPU 容器后必须执行**：
   ```bash
   bash /usr/local/bin/cleanup-mem.sh
   ```
   否则 UVM 残留导致后续 vLLM 启动失败：`ValueError: Free memory on device cuda:0 (X GiB) is less than desired GPU memory utilization`。
2. vLLM 启动内存检查：可用内存 ≥ `utilization × 122.83G`。27B 用 0.55（需求 67.55G），与 embedding(0.08)+rerank(0.1) 共存时内存紧张（页面缓存会挤占），**启动前先 cleanup**。
3. 内存占用参考（GPU 进程视角）：27B ≈ 63G、embedding+rerank ≈ 21G、ASR ≈ 4.7G、TTS ≈ 2.6G。
4. `free` 的 used 含 UVM 虚拟预留与页缓存，真实占用看 `docker stats`（RSS）与 `nvidia-smi`。

### 5.2 Jetson 特性

1. **enforce-eager 优先**：CUDAGraph 在 Thor 上无加速（27B 持平 111 vs 113ms；9B 时代 CUDAGraph 反而慢 3 倍且伴随网络中断）。使用 `--enforce-eager` 启动更快更稳。
2. **MTP 投机解码**（Qwen3.5 系自带）：`--speculative-config '{"method":"mtp","num_speculative_tokens":4}'` 是 27B 提速关键（111→68ms）。窗口取 4 最优（6/8 因接受率下降反而变慢）。
3. **多模态模型不能配外部 draft 模型**：vLLM 报 `Speculative Decoding with draft models ... does not support multimodal models yet`。外部 draft（如 Qwen3-0.6B）只能配纯文本模型且词表必须一致（151936）。
4. **torchaudio ABI**：Jetson 定制 torch 必须配匹配的 torchaudio（vLLM 镜像自带 torch 2.10+torchaudio 2.10）。PyPI torchaudio 会 ABI 不匹配（`.so` 加载失败）。
5. **pip 源**：dustynv/mineru 系镜像配置了 `pypi.jetson-ai-lab.dev`（DNS 不可达），pip install 需显式 `-i https://pypi.org/simple/`。
6. **基础镜像选择**：`mineru-gpu-dustynv` 的 torch 在容器内 `cuda: False`（不可作 GPU 服务基础镜像）；`my-pytorch-embed` cuda 可用但无 torchaudio；vLLM 镜像最完整。

### 5.3 模型 / 协议

1. **Qwen3.5 系 chat template 严格**：27B 报 `System message must be at the beginning` → 使用 lenient 模板 `--chat-template .../chat_template_lenient.jinja`（已移除 raise）。
2. **业务协议必须对齐**：
   - ASR：业务后端（ai_server_backend `audio/client.py`）调 **OpenAI 兼容** `POST /v1/audio/transcriptions`，自定义端点（如 `/asr`）无法对接（404）。
   - TTS：业务后端（`tts_client.py`）走 **vllm-omni 流式 WS** `/v1/audio/speech/stream`（session.config/input.text/input.done → audio.start/PCM/audio.done/session.done），普通 JSON-wav 协议不兼容。
3. **浏览器麦克风需 HTTPS 安全上下文**：Web UI 必须 https 访问，否则 getUserMedia 被拒（提示"需要开启 https"）。

### 5.4 网络与端口

1. 端口冲突实例：`holarfileparse_sgl_1.2b`（17199）曾与 mineru-api 冲突 → 已停用该容器。**新服务确认端口/IP 唯一**。
2. 容器 IP 变更需先 `docker compose down` 释放（同一 IP 只能一个容器）。
3. `manualai_network` 为 external 网络（`--subnet=172.18.0.0/24 --gateway=172.18.0.1`）。

### 5.5 业务 / 数据

1. 图抽取（KG）失败案例：知识库 3 个资源中 1 个 `.md` 文件**从未解析成功**（status=received、无 parse task、0 chunk）→ assistant 只返回 2 文档图+1 总图，ai_server 校验期望 3+1=4 失败 → 任务标记失败。**排查：resource 表 status、chunk 表 doc_id 分布、expected_file_ids 与 collection 文件对比**。
2. Milvus collection 名不允许连字符：业务若直接用 kbId（`d33d64c0-...`）查询会报 `Invalid collection name`，需使用内部名（`z_` 前缀）。
3. 数据库：`ai_server` 库（MySQL .11:8306，root/ai_server）；tasks 表存任务 payload（含 expected_file_ids）。

---

## 6. 常见修改点

### 6.1 切换对话模型（如 27B ↔ 9B）

- 9B compose：`/ManualAI/llm/qwen3.5/docker-compose.yaml`（当前注释停用）
- 27B compose：`/ManualAI/llm/qwen3.8-27b/docker-compose.yaml`
- 步骤：`docker compose down`（旧）→ `up -d`（新）；两者共用 `172.18.0.120:8020` + served-model-name `Qwen3.5`，**业务层零改动**
- 9B 启用时去掉其 speculative 配置（9B 词表 248320 与 Qwen3-0.6B 151936 不匹配，且多模态不能配外部 draft）

### 6.2 修改端口 / IP

- 改 compose 的 `ports` 与 `networks.manualai_network.ipv4_address`；改 IP 前 `docker compose down` 释放
- 改端口后同步检查：业务 `.env`（如 AUDIO_ASR_BASE_URL）、nginx `subconf/omniknow.conf` 代理

### 6.3 ASR / TTS 改代码（免重建镜像）

- 脚本已挂载：`/ManualAI/llm/qwen3-asr/asr_server.py`、`/ManualAI/llm/qwen3-tts/tts_server.py`
- 改完 `docker compose restart <容器>` 即生效
- 重建镜像（如装新依赖）：`cd /ManualAI/llm/qwen3-asr && docker build -t qwen3-asr-jetson:latest .`（停→cleanup→build→启动）

### 6.4 HTTPS / 证书

- **nginx（Web UI 8376）**：证书 `/ManualAI/depends_on/data/nginx/ssl/{cert,key}.pem`，配置 `subconf/omniknow.conf`（`listen 8376 ssl` + `error_page 497` 跳转）。换证书：openssl 重新生成后 `docker exec ai_nginx nginx -s reload`
- **ASR（8443）**：证书 `/ManualAI/llm/qwen3-asr/ssl/{cert,key}.pem`，存在即自动启用；改 `CN=IP` 重新生成后重启容器
- 生成自签名证书示例：
  ```bash
  openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes \
    -subj "/CN=192.168.21.105" -addext "subjectAltName=IP:192.168.21.105,IP:127.0.0.1,DNS:localhost"
  ```

### 6.5 MTP 投机解码调优

- 参数：`--speculative-config '{"method":"mtp","num_speculative_tokens":N}'`
- 实测：N=4 最优（62-71ms）；N=2 持平；N=6/8 变慢（接受率下降）
- 改后重启：`cd /ManualAI/llm/qwen3.8-27b && docker compose up -d --force-recreate`

### 6.6 业务 .env（/ManualAI/Omniknow/code/server/.env）

- AI 服务 URL：PARSER_API_URL / TRAINING_BASE_URL / AUDIO_ASR_BASE_URL / AUDIO_TTS_BASE_URL
- 数据库：DATABASE_HOST / REDIS_HOST / OSS_HOST / MILVUS_HOST
- 修改后需重启 ai_server 相关容器生效

---

## 7. 全量部署文档

> 前提：Jetson Thor 已装 JetPack/驱动，Docker + nvidia-container-runtime 可用；以下命令均在 105（root@192.168.21.105）执行。

### 7.1 初始化网络与目录

```bash
docker network create --subnet=172.18.0.0/24 --gateway=172.18.0.1 manualai_network
mkdir -p /ManualAI/{models,llm,depends_on,Omniknow,tools}
```

### 7.2 基础依赖（depends_on）

```bash
cd /ManualAI/depends_on && docker compose up -d
# 启动: mysql/redis/milvus(etcd+standalone)/minio/nginx
# 检查: docker ps | grep -E "ai_mysql|ai_redis|milvus|ai_minio|ai_nginx"
```

### 7.3 模型下载（ModelScope 多线程）

```bash
# 下载器: /ManualAI/tools/download_model.py (递归文件列表 + LFS 多线程 + 断点跳过)
python3 /ManualAI/tools/download_model.py Qwen/Qwen3.8-27B-FP8 /ManualAI/models/Qwen3.8-27B-FP8
python3 /ManualAI/tools/download_model.py Qwen/Qwen3-Embedding-0.6B /ManualAI/models/Qwen3-Embedding-0.6B
python3 /ManualAI/tools/download_model.py Qwen/Qwen3-Reranker-0.6B /ManualAI/models/Qwen3-Reranker-0.6B
python3 /ManualAI/tools/download_model.py Qwen/Qwen3-ASR-1.7B /ManualAI/models/Qwen3-ASR-1.7B
python3 /ManualAI/tools/download_model.py Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice /ManualAI/models/Qwen3-TTS-12Hz-0.6B-CustomVoice
```

### 7.4 对话 LLM（27B）

```bash
cd /ManualAI/llm/qwen3.8-27b && docker compose up -d
# 等待 ~150s 后验证
curl http://172.18.0.120:8020/v1/models
```

### 7.5 embedding / rerank

```bash
cd /ManualAI/llm/base && docker compose up -d
```

### 7.6 MinerU

```bash
cd /ManualAI/llm/mineru && docker compose --profile api up -d
```

### 7.7 ASR（构建镜像 + 启动）

```bash
# 首次需构建镜像（my-pytorch-embed 基础 + ffmpeg + qwen-asr）
cd /ManualAI/llm/qwen3-asr
docker build -t qwen3-asr-jetson:latest .
docker compose up -d
# 验证
curl http://172.18.0.123:8023/health
curl -F "file=@test/test_zh.wav" http://172.18.0.123:8023/v1/audio/transcriptions
```

### 7.8 TTS（构建镜像 + 启动）

```bash
cd /ManualAI/llm/qwen3-tts
docker build -t qwen3-tts-jetson:latest .
docker compose up -d
# 验证（vllm-omni 协议，见第 8 节测试脚本）
```

### 7.9 Nginx HTTPS（Web UI）

```bash
mkdir -p /ManualAI/depends_on/data/nginx/ssl
openssl req -x509 -newkey rsa:2048 -keyout /ManualAI/depends_on/data/nginx/ssl/key.pem \
  -out /ManualAI/depends_on/data/nginx/ssl/cert.pem -days 365 -nodes \
  -subj "/CN=192.168.21.105" -addext "subjectAltName=IP:192.168.21.105"
docker exec ai_nginx nginx -t && docker exec ai_nginx nginx -s reload
# 浏览器访问 https://192.168.21.105:8376 (首次点"高级-继续前往")
```

### 7.10 业务栈（Omniknow）

```bash
cd /ManualAI/Omniknow && docker compose up -d
```

### 7.11 运维脚本

```bash
# 释放 UVM（停止 GPU 容器后必做）
bash /usr/local/bin/cleanup-mem.sh
# 27B 启停
/usr/local/bin/start-27b.sh / /usr/local/bin/stop-27b.sh
# 性能基准（host 直接跑，27B 8020）
python3 /ManualAI/tools/bench/bench_tok.py "标签"
```

### 7.12 验证清单

```bash
curl http://172.18.0.120:8020/v1/models        # LLM
curl http://172.18.0.121:8021/v1/models        # embedding
curl http://172.18.0.122:8022/v1/models        # rerank
curl http://172.18.0.123:8023/health           # ASR
curl -sk https://172.18.0.123:8443/health      # ASR HTTPS
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8024/tts -X POST -H 'Content-Type: application/json' -d '{}'  # TTS
curl -sk https://192.168.21.105:8376/          # Web UI HTTPS
```

---

## 8. 测试情况

### 8.1 对话 LLM（27B）

- 文本对话（非流式/流式）✅；OpenAI 兼容 API ✅；工具调用（tool-call-parser qwen3_xml）✅
- 多模态图像（VISION_MODEL 故障树图片→JSON）✅（Qwen3.5 架构原生支持）
- 图抽取（KG，知识库 3 文件场景）⚠️ 见 5.5：存在幽灵文件（.md 未解析）时任务校验失败

### 8.2 ASR

- wav 识别：`{"text":"甚至出现交易几乎停滞的情况。"}` ✅
- mp3 识别（前端录音格式）：✅（ffmpeg 转 16k wav）
- OpenAI 兼容端点（业务协议）✅；HTTPS 8443 ✅；自动语言检测 ✅

### 8.3 TTS

- HTTP /tts：返回 wav（188KB/约 4s 音频）✅
- vllm-omni WS：事件序列 `audio.start → audio.done → session.done`，PCM 184KB ✅
- 多音色（Vivian/Serena/Dylan 等 9 种）✅；中文 ✅

### 8.4 文档解析（MinerU）

- PDF/docx → 文本/表格（pipeline 模式）✅
- parser 容器 reportlab 已内置（镜像 parser:2.0.1.058-reportlab）✅

### 8.5 图抽取（KG）

- 2 文件知识库：78+32 chunks 全量抽取，291+85 实体，573s 完成 ✅
- 3 文件（含 .md 幽灵文件）：任务失败（completed 3 vs 期望 4）— 属于数据问题而非模型问题

### 8.6 HTTPS / 安全

- nginx 8376 HTTPS（自签名）✅；http 自动 302 跳转 ✅
- ASR 8443 HTTPS ✅
- 浏览器麦克风权限（HTTPS 上下文）✅

---

## 9. 性能测试报告

### 9.1 测试方法（2026-08-31 全模型实测）

- 统一脚本：`/ManualAI/tools/bench/bench_all.py`（27B/ASR/TTS/embedding/rerank 全套）+ `bench_tok.py`
- 27B：中文 200 token 流式生成，`usage.completion_tokens` 精确计数，指标 TTFT/TPOT/吞吐
- ASR：`POST /v1/audio/transcriptions`（OpenAI 端点），4 秒中文音频（wav + mp3）
- TTS：`POST /tts`（HTTP）与 `ws://.../v1/audio/speech/stream`（vllm-omni 协议，PCM 输出）
- embedding/rerank：OpenAI 兼容 `POST /v1/embeddings`、`POST /v1/rerank`
- 测试条件：全部服务在线、系统可用内存 ~11.5G（偏紧）、CPU 负载 <1.0

### 9.2 对话模型对比（Jetson Thor 实测）

| 配置 | TTFT | TPOT | 吞吐 | 每分钟 token | 备注 |
|---|---|---|---|---|---|
| Qwen3.5-9B-AWQ（eager） | 0.13s | 50-60ms | 16-19 | 960-1140 | 历史基线（内存充裕时） |
| 27B CUDAGraph（无投机） | 0.20s | 111-123ms | 8.8 | 530-740 | 基线 |
| 27B enforce-eager（无投机） | 0.25s | 113-118ms | 8.4 | 500-710 | 与 CUDAGraph 持平 |
| **27B + MTP×4（定稿）** | **0.4-0.55s** | **60-71ms** | **14-16** | **880-980** | **🏆 推荐配置**（内存充裕/热身后） |
| 27B + MTP×2 | 0.5s | 64-73ms | 13-15 | 780-900 | 与 ×4 持平 |
| 27B + MTP×6 | 0.5s | 98-111ms | 5-10 | 300-600 | 接受率下降 |
| 27B + MTP×8 | 0.5s | 74-82ms | 13 | 780 | 偏慢 |
| 27B + MTP×4 + CUDAGraph | 0.5s | 60-69ms | 14-16 | 840-960 | 与 eager 持平，启动慢一倍 |

**实测波动说明**（重要）：27B TPOT 受系统内存环境影响明显。全服务在线、可用内存 ~11.5G 时首测为 **92-109ms**；持续请求（内存状态整理/热身后）逐步恢复到 **60-71ms**。连续 6 次实测：109→97→88→71→60→66ms。**建议：部署后让 27B 保持常驻并预留 ≥15G 可用内存，可稳定在 60-71ms。**

**结论**：
1. MTP 投机解码（x4）使 27B TPOT 从 111ms 降至 **60-71ms（提升 ~40%）**，是唯一的大幅优化手段
2. 27B（MTP×4）能力全面强于 9B（27B 参数 + 原生多模态），速度达到 9B 的 ~85-90%
3. Jetson Thor 上 enforce-eager = CUDAGraph（无 graph 加速收益），选 eager（启动快、稳定）

### 9.3 内存占用（GPU 进程视角，nvidia-smi 实测）

| 服务 | GPU 占用 | RSS |
|---|---|---|
| 27B vllm（MTP×4） | ~63 GiB | ~4.0 GiB |
| embedding + rerank | ~21 GiB | ~4.6 GiB |
| ASR（1.7B） | ~4.7-9 GiB | ~1.9-2.4 GiB |
| TTS（0.6B） | ~2.6 GiB | ~2.0 GiB |
| **GPU 合计** | **~91-96 GiB** | - |

系统总内存 122.8G，业务/系统/页缓存另占 ~15-20G，**可用 ~11-15G**（偏紧，见注意事项 5.1）。GPU 服务全开时内存余量有限，27B 重启必须先 cleanup-mem.sh。

### 9.4 全模型单请求实测（2026-08-31，各测 3-6 次）

| 服务 | 实测延迟 | 说明 |
|---|---|---|
| **27B 对话**（200 token） | TTFT 0.4-0.55s；TPOT 60-71ms（热身后） | 吞吐 14.7-16.3 tok/s ≈ **880-980 token/分钟** |
| **ASR**（4s 中文音频） | wav **0.39-0.42s**；mp3 **0.40-0.41s** | 约 10 倍实时，含 ffmpeg 转码 |
| **TTS HTTP**（7-8s 音频） | **6.98-9.14s**（平均 ~8.0s） | 输出 280-342KB wav，约 1.1 倍实时 |
| **TTS WS**（vllm-omni） | 总 **8.72s**，首包 **8.71s**，PCM 337KB ≈ 7.0s 音频 | 首包=整段合成时间（非流式限制） |
| **embedding** | 首次 0.36s，稳定 **0.025-0.03s** | dim 1024 |
| **rerank**（3 文档） | 首次 0.28s，稳定 **0.056-0.062s** | scores 示例 [0.93, 0.909, 0.037] |
| 图抽取每 chunk（27B） | ~50-60s | 2 文件知识库 573s/110 chunks |

---

## 10. 已知问题与后续建议

### 10.1 已知问题

1. **内存偏紧**：可用仅 ~11-15G；27B 重启必须先 `cleanup-mem.sh`，必要时降 `--gpu-memory-utilization` 或停 embedding/rerank
2. **图抽取幽灵文件**：知识库中解析失败/未同步的文件会导致抽取任务校验失败（completed 数量不匹配）——建议 ai_server 校验逻辑改为"跳过缺失文件并告警"
3. **Milvus collection 命名**：kbId 含连字符直接查询会失败，需内部名转换（`z_` 前缀）
4. **TTS 非真流式**：qwen-tts 0.1.1 无流式 API，vllm-omni 协议为整段合成后分帧输出；升级 qwen-tts 或换流式方案可降低首包延迟
5. **自签名证书**：浏览器首次访问需手动信任；过期（365 天）需重新生成
6. **ASR/TTS 镜像大**（~40G）：基于 40G+ 基础镜像，磁盘需预留；重建时间较长

### 10.2 后续建议

1. 27B 内存优化：评估 `--kv-cache-dtype fp8`（降低 KV 缓存带宽）与 utilization 调整
2. MTP 微调：业务并发高时可测 `max-num-seqs`/`max-num-batched-tokens` 提升吞吐
3. 语音流式化：跟进 Qwen3-TTS 官方流式 API，实现真正低延迟（目标 <500ms 首包）
4. 证书自动化：写证书续期脚本（openssl 重生成 + nginx reload + ASR 重启）
5. 部署自动化：将 7.x 全量部署步骤固化为 `deploy.sh`，含顺序校验与 cleanup 规范
6. 监控：定期检查 `MemAvailable`（阈值告警），GPU 服务异常时自动 cleanup 重启

---

*报告结束。硬件与配置信息以 2026-08-31 实际部署为准。*
