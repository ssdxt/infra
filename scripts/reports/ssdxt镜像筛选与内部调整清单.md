# ssdxt 镜像筛选与「容器内部调整」判定

> 生成时间：2026-09-07 · 数据来源：105（192.168.21.105）现场 docker 状态 + 备份目录比对
> 目的：从 `images/ssdxt` 的 commit 备份里，筛出相对 `images/Manual`、`images/omniknow` **独有、只能靠 commit 包还原**的镜像；并判定哪些容器发生过**容器内部改动**（代码/依赖/配置写在容器层里，重跑原始 docker run 不会自带）。

---

## 一、src 三区原始镜像 tar 库存（能否离线还原的基础）

| 目录 | 数目 | 内容（文件名可见 repo/版本） |
|---|---|---|
| `images/Manual/3d/` | 13 | cc 系：nginx-1.29.6 / mysql-8.0.45 / redis-8.6.2 / minio-2024-03 / nacos-2.0.4 / mongodb-4.4.5 / rocketmq-5.3.2 / kkfileview-4.2.0 / elasticsearch-7.13.0 / czy-user / czy-server / apass-web（cyze/apass 带业务版本） |
| `images/omniknow/` | 10 | omniknow/ai 系：nginx-stable-alpine3.23 / mysql-8.0.40 / redis-8.4.2 / minio-2024-12 / milvus-2.6.14 / etcd-v3.5.25 / ai_server-3.1.0 / assistant-3.1.0-0903 / parser / torch-npu 基座 |
| `images/ssdxt/` | 22 commit tag + 22 个 tar | **本次从 31 个运行容器 commit 出的 22 组日期备份镜像** |

> 注意：`images/omniknow` 里的 assistant tar 文件名是 `3_1_0_0903`，而**当前运行的容器是 `assistant:3.0.0.0825.39fdf8e`** —— 两者版本号不一致，omniknow 那份是更早 baseline，**不能直接等价**。

---

## 二、三区比对：ssdxt 独有的镜像（Manual+omniknow 还原不了 / 版本不一致的）

对每张 `repo:2026-09-07` commit 镜像，判断它对应的**真正在跑的容器原始版本**在 Manual/omniknow 里有没有可复现 tar。

### 结论表（★ = 不能靠 Manual/omniknow 还原，必须保留 ssdxt commit）

| commit 镜像（ssdxt）| 实跑原始镜像(容器) | Manual/omniknow 里有没有同版本 tar | 必留? |
|---|---|---|
| `assistant:2026-09-07` | assistant:3.0.0.0825.39fdf8e | 仅 3.1.0.0903（版本不符）| ★ |
| `parser:2026-09-07` | parser:2.0.1.058 | omniknow parser 文件名无版本细节 | ★(待核) |
| `ai_server:2026-09-07` | ai_server:3.1.0.0824.315945 | omniknow 有同名 3.1.0.0824 aarch64 产物 | ✗ 可还原(除非内部有改) |
| `mysql:2026-09-07` | 取自 cc-mysql 8.0.45（非 ai 8.0.40）| Manual 有 8.0.45 tar | ✗ |
| `nginx:2026-09-07` | 取自 cc-nginx 1.29.6 | Manual 有 1.29.6 tar | ✗（且不含 ai_nginx stable-alpine）|
| `redis:2026-09-07` | 取自 cc-redis 8.6.2 | Manual 有 8.6.2 tar | ✗ |
| `minio/minio:2026-09-07` | 取自 minio RELEASE.2024-03 | Manual 有同版本 | ✗ |
| `nacos/nacos-server:2026-09-07` | nacos 2.0.4-slim | Manual 有 | ✗ |
| `mongo:2026-09-07` | mongo 4.4.5 | Manual 有 | ✗ |
| `apache/rocketmq:2026-09-07` | rocketmq 5.3.2 | Manual 有 | ✗ |
| `killsnow/kkfileview:2026-09-07` | kkfileview 4.2.0 | Manual 有 | ✗ |
| `elasticsearch:2026-09-07` | es 7.13.0 | Manual 有 | ✗ |
| `czy-user:2026-09-07` | czy-user:latest | Manual 有(业务版 tar) | ✗/待核 tag |
| `czy-server:2026-09-07` | czy-server:latest | Manual 有 | ✗/待核 tag |
| `apass-web:2026-09-07` | apass-web:latest | Manual 有 | ✗/待核 tag |
| `milvusdb/milvus:2026-09-07` | milvus v2.6.14 | omniknow 有 | ✗ |
| `quay.io/coreos/etcd:2026-09-07` | etcd v3.5.25 | omniknow 有 | ✗ |
| `ghcr.io/nvidia-ai-iot/vllm:2026-09-07` | qwen-nvidia-vllm(thor vllm 51G) | **无**（ghcr 只以容器形式在跑）| ★ |
| `qwen3-asr-jetson:2026-09-07` | qwen3-asr 41G | **无** | ★ |
| `qwen3-tts-jetson:2026-09-07` | qwen3-tts 51G | **无** | ★ |
| `img-server-jetson:2026-09-07` | img_server 40G | **无**(需 docker build FROM my-pytorch-embed) | ★ |
| `mineru-thor:2026-09-07` | mineru-api 53G | **无**(需 docker build) | ★ |

> 附：qwen-embedding / qwen-rerank 与 qwen-nvidia-vllm **共用同一张** `ghcr.io/.../vllm` commit 镜像（3 个容器同一 repo）——concurrency 同一 tar。embedding/rerank 实际跑的是同 base，容器内 load 同一模型配置路径不同，但镜像层相同。

### 一句话结论
**真正"只有 ssdxt commit tar 才能还原"的独有镜像 = 7 项：**
`assistant`、`parser`、`ghcr vllm`(=qwen-nvidia-vllm/embedding/rerank 共用)、`qwen3-asr-jetson`、`qwen3-tts-jetson`、`img-server-jetson`、`mineru-thor`。

中间件（mysql/nginx/redis/minio/nacos/mongo/rocketmq/kkfile/es/etcd/milvus）以及含 tar 库的 ai_server 都**能用 Manual/omniknow 离线 tar 还原，ssdxt 的 commit 不是唯一来源**——但**前提是这些容器没有不可复现的内部改动**。

---

## 三、哪些容器有「容器内部调整」（代码/依赖/配置写在容器层）

判定方法：`docker diff`（相对基准镜像的改动，剔除运行噪音: /tmp,/var/log,/proc,/sys,**.pyc**/__pycache__ 等）+ docker images 尺寸对照。

### 依据 1：commit 镜像相对原 tag 的尺寸增量（docker 层叠加证据）

| repo | 原 tag 尺寸 | commit 尺寸 | 增量 | 说明 |
|---|---|---|---|---|
| **assistant** | 2.56G | 2.63G | **+0.07G** | 确有增层（site-packages）|
| ai_server | 1.46G | 1.53G | +0.07G | 有增层(疑依赖) |
| ghcr vllm | 51.2G | 51.4G | +0.2G | 有增层 |
| qwen3-asr / tts / img / mineru | 与 commit 同 | 同 | ≈0 | commit 是原层直接 commit，未额外改动 |

### 依据 2：docker diff 内容（真实改动扫描）

- **assistant**：diff 显示 `C /opt/venv/lib/python3.13/site-packages/...` 整批新增/replaced —— 里面出现 omniknow 基准镜像里**没有**的包：`langchain_google_genai`、`mcp` / `mcp/fastmcp`、`langgraph`(store/prebuilt/pregel)、`openai`(新版含 skills/v1 embed params)、`pymilvus`、`fastapi`、`sqlalchemy`, `google/genai` 等。这是**线上在容器里补充装进去的依赖**，属业务侧热改热点（报告生成/kb/neo 等链路的关联库）。同时 `A /app/.env`（运行时生成）。**→ 确认为做过容器内依赖安装 + 运行时改动，commit 值保留。**
- **ai_server_backend/worker/beater**：大 diff 但多为运行写入与 site-packages 微动（backend 338 / worker 349 / beater 216 条），需进一步看是否代码改动；当前无明确业务源码改动迹象。
- **qwen-nvidia-vllm / qwen-embedding / qwen-rerank**：diff 以模型/缓存/运行态为主（600 条左右 clean），未见业务源码类改动。
- **parser / mineru / img / qwen3-asr / qwen3-tts / czy / t-apass**：与基准差异以运行缓存/状态为主。

**说明（诚实标注）**：`docker diff` 对长时运行容器会混入大量运行期残留，无法100%分离"人为代码编辑"。能**高度确证做过多轮容器内依赖/代码层面干预的**主要是 **assistant**（依赖增层 + 早前会话的内联补丁在容器层）与**疑似 ai_server**；**qwen-nvidia-vllm(9B) 服务参数类修复（chat-template 等）主要是启动命令/挂载层面，不在镜像层**，故 diff 不明显。

### 汇总「容器内部确实动过、需靠 commit 包保留」的判断
| 容器 | 内部调整 | commit 保留建议 |
|---|---|---|
| **assistant** | 高（venv 依赖增层 + 源码线上 patch）| ★ 必留 |
| **qwen-nvidia-vllm (9B)** | 运行期参数级修复（chat-template 等）；镜像层增量小 | commit 镜像可作**服务配置回退冗余**，中优先 |
| **ai_server 三件套** | 疑有依赖层变化，待细核 | 中优先 |
| 其余中间件/模型镜像 | 无不可复现内部改动痕迹 | ssdxt commit 可视为冗余，**只用 Manual/omniknow tar 即可** |

---

## 四、给筛选动作的直接建议

面向"重部署/精简备份"，建议把 ssdxt 分成三档：

1. **必留独有包（★7）**：assistant / parser / ghcr-vllm(共用，3 容器 1 tar) / qwen3-asr / qwen3-tts / img-server-jetson / mineru-thor —— Manual+omniknow 还原不了。
2. **建议保留（上表中优先）**：ai_server_2026-09-07、qwen-nvidia-vllm = ghcr-vllm 那张已并入 ★。
3. **可与原始 tar 去重删除**：mysql/nginx/redis/minio/nacos/mongo/rocketmq/kkfile/es/etcd/milvus/apass/czy 的 commit tar（它们都有 Manual/omniknow 同版本原始 tar；但要注意 nginx/redis/mysql/minio 的 commit **只捕获了 cc 系代表**，要用原始 tar 才能同时还原 ai 系 Web 栈）。

> ⚠️ 版本口径提醒（此前已知坑被本次数据证实）：
> - `nginx:2026-09-07`=1.29.6（cc-nginx），不含 `nginx:stable-alpine3.23`(ai_nginx)。
> - `redis:2026-09-07`=8.6.2（cc），不含 8.4.2(ai)。
> - `mysql:2026-09-07`=8.0.45（cc），不含 8.0.40(ai_mysql)。
> - `minio/minio:2026-09-07`=RELEASE.2024-03，**不含 2024-12(ai_minio)**；重放时勿用旧版 minio 读新版桶数据。
> - assistant：omniknow 有 3.1.0.0903，现场跑 3.0.0.0825 —— 若切 omniknow 那份版本不同步。
