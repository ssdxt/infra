# ============================================================
# 105 (Jetson Thor) — CDI 与 Runtime 容器注入 · 命令速查
# 环境: L4T R38.4 / Docker 29.3.1 / nvidia-container-toolkit 1.18.1
# 现状: 走 Runtime 注入 (mode=auto → JIT-CDI)，未用落盘 CDI
# ============================================================

# ---------- 1. 看当前状态 / 配置 ----------

# 容器到底用哪个 runtime (应输出 nvidia)
docker inspect qwen-nvidia-vllm | grep '"Runtime"'

# 容器有没有申请 GPU 的 env (有 = env 驱动方式)
docker inspect qwen-nvidia-vllm | grep NVIDIA_VISIBLE_DEVICES

# Docker 登记了哪些 runtime / 默认 runtime
docker info | grep -iE 'Runtimes|Default Runtime'

# daemon.json 里 nvidia runtime 指向哪个二进制
cat /etc/docker/daemon.json

# runtime 主配置: mode=auto/legacy/cdi 在这里
cat /etc/nvidia-container-runtime/config.toml

# toolkit 版本 (>=1.18 才有 JIT-CDI)
nvidia-container-runtime --version
nvidia-ctk --version

# ---------- 2. Runtime 注入 (105 现状) ----------

# 常规启动 (compose/docker): env 申请全部 GPU
docker run --rm --runtime=nvidia -e NVIDIA_VISIBLE_DEVICES=all <image> <cmd>
#   指定第 0 张卡
docker run --rm --runtime=nvidia -e NVIDIA_VISIBLE_DEVICES=0 <image> <cmd>
#   按 UUID 指定
docker run --rm --runtime=nvidia -e NVIDIA_VISIBLE_DEVICES=<uuid> <image> <cmd>

# 注: mode=auto + NVML 可用 = JIT-CDI (内存现生成, 不写 /etc/cdi)
#     所以 /etc/cdi 空 是正常的, 不代表没注入

# ---------- 3. CDI (落盘 spec 方式) ----------

# 生成 CDI spec 到 /etc/cdi (前提: 驱动+toolkit 已装)
nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

# 也可以生成到 /var/run/cdi (toolkit 1.18 默认 nvidia-cdi-refresh 写这)
nvidia-ctk cdi generate --output=/var/run/cdi/nvidia.yaml

# 查看已生成的 CDI 设备 (有输出=spec 生效; "Found 0 CDI devices"=没生成)
nvidia-ctk cdi list

# 落盘位置检查
ls -la /etc/cdi
ls -la /var/run/cdi

# CDI 启动写法 (docker >= 25 原生; 需要上面 yaml 已生成, 否则报 unresolvable)
docker run --rm --device nvidia.com/gpu=all <image> <cmd>        # 全部 GPU
docker run --rm --device nvidia.com/gpu=0 <image> <cmd>          # 指定第 0 张
docker run --rm --runtime=nvidia \
  -e NVIDIA_VISIBLE_DEVICES=nvidia.com/gpu=all <image> <cmd>     # runtime 走 cdi 名

# 编排场景(k8s/containerd)走 cdi annotation, 不是手动 docker run

# ---------- 4. 容器内验证注入产物 (全齐 = 注入成功) ----------

# 设备节点在不在
docker exec <c> ls /dev/nvidia*

# driver 库挂载数 (宿主上是 0 正常, 必须进容器查; 105 容器内=217)
docker exec <c> sh -c 'grep -c nvidia /proc/1/mountinfo'

# libcuda 能否按名找到 (105 容器内=7)
docker exec <c> sh -c 'ldconfig -p | grep -c libcuda'

# 容器内 nvidia-smi 是否可用 (走 NVML)
docker exec <c> nvidia-smi

# ---------- 5. 宿主驱动层 (注入链路之外, 先验这层) ----------

# 宿主 nvidia-smi (驱动 580.00 / CUDA 13.0)
nvidia-smi
nvidia-smi -L                       # 枚举 GPU 名+UUID
nvidia-smi --query-gpu=name,driver_version --format=csv

# NVML 库在不在 (nvidia-smi/nvidia-ctk/JIT-CDI 都靠它)
ldconfig -p | grep nvidia-ml

# 驱动库真实落点
ls -la /usr/lib/aarch64-linux-gnu/nvidia/libnvidia-ml.so.1

# ---------- 6. 常见坑 / 别误判 ----------

# a) /proc/1/mountinfo 查 nvidia 必须进容器; 宿主机 PID1 不挂 driver → 0 是正常
# b) docker inspect 的 JSON: "HostConfig" 与 "Runtime" 不在同一行,
#    grep -i hostconfig.runtime 必然空 → 要分开 grep
# c) 拼写是 libcuda 不是 lcudai
# d) "Found 0 CDI devices" 是正常日志(0个落盘设备), 不是报错
# e) /etc/cdi 空 ≠ 注入失败 (105 走 JIT-CDI 不落盘)
# f) nvidia-cdi-refresh.service 开机 failed = 竞态, 不影响 JIT-CDI 运行
# g) ldconfig -p 只列缓存; 容器内库找不到时, 注入层会跑 update-ldcache hook
