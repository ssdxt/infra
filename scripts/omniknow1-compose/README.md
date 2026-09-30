# omniknow1-compose — 全栈总控编排（v3 · 已上线运行）

> 状态：**2026-09-23 已完成切换，7 服务全部 healthy**。旧 systemd 三件套已停用。
> 形态：容器=进程壳（不打镜像、宿主内容全挂载），nginx 443 统一入口。

## 一、架构与访问

```
浏览器 ── https://<任意IP或localhost>/ （443，唯一客户入口）
           ├─ /        → 前端静态（web_0918 由 nginx 直出）
           ├─ /api/    → api    (127.0.0.1:8261，剥前缀)
           └─ /voice/  → speech (127.0.0.1:7870，剥前缀)
服务间调用全部 127.0.0.1（回环永不变）→ 换网络环境/换IP 零改动
```

调试直连端口全部保留：8261 / 7870 / 8105 / 8106 / 10006 / 2881 / 3333(已由443替代)。

顺序链（串行防风暴）：oceanbase → embed → reranker → glm → api → speech → gateway
双保险错峰：depends_on(healthy) + 各 command 内 sleep（应对重启后 restart 策略同时拉起）。

## 二、服务清单与要点

| 服务 | 说明 |
|---|---|
| oceanbase-ce | obnet 固定 172.20.0.2（元数据绑定勿改）；发布 2881/2882 |
| embed / bge-reranker | mis-tei 镜像，host 网络，健康检查 /health |
| glm-4-chat-9b | MindIE 双卡，conf 挂载（KV池16G/卡、batch16、32K上下文） |
| omniknow-api | ubuntu 底座 + recovery 环境挂载；modelTranslator 子进程（挂载 + /opt/mt-libs 25库）；**LibreOffice 办公转 PDF + 258 中文字体 + fontconfig（lo-extras）** |
| omniknow-speech | melo_tts 环境；**命令内 source 宿主同款 4 个昇腾 set_env.sh**（nnrt/toolkit/atb/toolbox，等价 /root/.bashrc）；挂整个 /usr/local/Ascend 与 /deploy/models；设备号必须 **0**（容器内无逻辑设备6）；ffmpeg 在 /opt/extras |
| omniknow-gateway | nginx:alpine 443 TLS；证书 ./nginx/certs（自签 SAN localhost/127.0.0.1/192.168.21.111，10年） |

**日志**：全部 `docker logs <容器名>`（api/speech 直接 stdout；nginx 走镜像内置 stdout 链接），不落文件。

## 三、日常操作

```bash
cd /deploy/omniknow1-compose
docker-compose ps                      # 状态（应全 healthy）
docker-compose logs -f omniknow-api    # 日志
docker-compose restart glm-4-chat-9b   # 单服务重启
docker-compose up -d                   # 改 compose 后应用（幂等）
```

## 四、换 IP / 迁移 Runbook（零配置改动）

1. 服务间全是 127.0.0.1、前端同源相对路径 → **后端零改动**。
2. 客户端改用 `https://<新IP>/` 访问（自签证书会告警，信任即可；如需消除告警按新 IP 重签：
   `cd nginx/certs && openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -keyout omniknow.key -out omniknow.crt -subj "/CN=omniknow" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:<新IP>"` 后 `docker-compose restart gateway`）。
3. 整机迁移：打包 /deploy + /root/anaconda3/envs（或按交付清单）→ 新机装 docker/昇腾驱动 → `docker-compose up -d`。

## 五、排障备忘（今日实证）

| 症状 | 根因 | 解法 |
|---|---|---|
| api 起不来 ImportError libX11 | recovery 的 tkinter 依赖 X11 | mt-libs 已含 X11 链（勿删该目录） |
| speech 循环重启且无 python 输出 | ASCEND_RT_VISIBLE_DEVICES=6 容器内无效 → torch_npu 段错误 | 必须用 0 |
| speech 报 funasr model not registered | 未挂载 /deploy/models | 已挂载 |
| speech 报 GEInitialize failed | 缺宿主 .bashrc 的昇腾 set_env 环境 | command 内 source 4 个 set_env.sh |
| GLM 输出乱码（多语种混杂token） | NPU 状态劣化（多次重建/段错误实验后） | `docker-compose restart glm-4-chat-9b` 干净重载即愈 |
| LibreOffice 转换崩溃 Application Error | NSS softoken 是 dlopen 加载，ldd 看不见 | lo-extras/lib 必含 softokn3/freebl3/**freeblpriv3**/nssckbi/nssdbm3 |
| soffice 报 libffi 符号错误 LIBFFI_BASE_7.0 | conda 的 libffi 遮蔽 lo-libs 的 libffi.so.7 | wrapper(/opt/lo-bin/soffice) 仅对 LO 进程树前置 lo-libs（勿放全局 LD_LIBRARY_PATH） |
| ffmpeg 找不到/缺库 | extras 演进 | extras/lib 现含完整 X11/xcb 链（speech 容器专用） |
| 改了宿主 .bashrc 的昇腾环境 | speech 依赖它 | 已内化到 compose command，不再依赖宿主 shell |

## 六、回滚（回到 systemd + 各自 compose 形态）

```bash
cd /deploy/omniknow1-compose && docker-compose down
cd /deploy/infra/oceanbase && docker-compose up -d
cd /deploy/models/docker_run/bge-m3 && docker-compose up -d
cd /deploy/models/docker_run/vllm  && docker-compose up -d
systemctl enable --now chat_doc_api chat_doc_web chat_doc_speech
# 前端/配置还原：*.bak-nginx443-* / *.bak-ipclean-* 对应覆盖回去
```

## 七、目录内容

```
/deploy/omniknow1-compose/
├── docker-compose.yml        # 总控（7 服务）
├── README.md                 # 本文件
├── nginx/                    # nginx.conf + conf.d/omniknow.conf(含80→443跳转) + certs/
├── modeltranslator-libs/     # 25个系统库（X11/tk + freeimage 链，api容器 /opt/mt-libs）
├── extras/                   # ffmpeg + 139个依赖库（speech容器 /opt/extras）
└── lo-extras/                # LibreOffice 6.4.7（libreoffice/bin/含隔离wrapper/fonts中文258套/etc-fonts/lib 154库）
```
