# GPU 容器注入两种方式：Runtime(nvidia-container-runtime) vs CDI —— 调用链路与排查逻辑

> 适用机器：105（Jetson AGX Thor，L4T R38.4，Docker 29.3.1 + containerd，nvidia-container-toolkit 1.18.1）
> 2026-09-09 现场取证 · 目标：搞清"GPU 怎么进容器"的两种路径，遇到问题能按链路逐层定位。

---

## 0. 全局：最终都汇到同一条河

**两种方式注入的"产物"完全一样**（/dev/nvidia* 设备 + driver 库挂载 + ldconfig 生效），区别只在**"谁、在哪一步、按什么清单"把这些东西加进 OCI spec**：

- Runtime 方式：启动瞬间由 runtime/hook **现场探测** 决定挂什么。
- CDI 方式：由 **预先生成好的 CDI spec（yaml）** 决定挂什么。

---

## 1. 名词与对应二进制（105 实测形态）

| 名称 | 是什么 | 105 上的文件 |
|---|---|---|
| nvidia-container-runtime | runc 的 NVIDIA wrapper（Go ELF），Docker 的 `runtime=nvidia` 实际执行体 | `/usr/bin/nvidia-container-runtime` |
| nvidia-container-runtime-hook | legacy 模式用的 OCI prestart hook（Go ELF） | `/usr/bin/nvidia-container-runtime-hook` |
| nvidia-container-cli | 底层 C 工具：`configure`(把 GPU 配进容器) / `info`(报告驱动设备) / `list`(列组件) | `/usr/bin/nvidia-container-cli` |
| nvidia-ctk | toolkit CLI：`cdi generate/list`、`config` 改 config.toml | `/usr/bin/nvidia-ctk` |
| config.toml | runtime 主配置（mode 在这） | `/etc/nvidia-container-runtime/config.toml` |
| host-files-for-container.d | legacy/csv 的挂载清单 | `devices.csv`、`drivers.csv` |
| containerd-shim-runc-v2 | 真正把 OCI spec 交给 runc 起容器的 shim | containerd 内置 |

---

## 2. 方式 A：Runtime 注入（env 驱动）—— 你 105 现在用的

### 调用链路

```
docker run --runtime=nvidia -e NVIDIA_VISIBLE_DEVICES=all IMAGE
 ① Docker(29, 内建 containerd)
     读 /etc/docker/daemon.json: runtimes.nvidia.path = "nvidia-container-runtime"
 ② nvidia-container-runtime（wrapper，读 config.toml）
     [nvidia-container-runtime] mode = "auto"
     auto 决策:
        NVML 可用(toolkit≥1.18) → JIT-CDI(nvcdi)，内存生成 CDI spec
        NVML 不可用/老版本      → legacy(hook) 路径
 ③ 注入执行（按上面决策二选一）
    JIT-CDI: nvcdi 经 NVML 现场枚举 GPU → 内存 spec → 加 devices/mounts/hooks
    legacy : nvidia-container-runtime-hook(prestart) → nvidia-container-cli configure
            按 env + devices.csv/drivers.csv 决定挂哪些设备与库
 ④ 组装好 OCI spec → containerd-shim-runc-v2 → runc 启动
 ⑤ 容器内: /dev/nvidia* + driver 库 + ldconfig 生效 → 应用可用
```

### 特征指纹（怎么认出是它）

- `docker inspect <c>` → `"Runtime": "nvidia"` 且 env 有 `NVIDIA_VISIBLE_DEVICES`
- `/etc/cdi`、`/var/run/cdi` 可以为空（JIT-CDI 不落盘）
- config.toml `mode = auto/legacy`

### 排查逻辑（Runtime 注入出问题）

```
容器内无 GPU？
 ├─ ① docker inspect <c> | grep '"Runtime"'         → 不是 nvidia？compose 漏 runtime: nvidia
 ├─ ② docker inspect <c> | grep NVIDIA_VISIBLE_DEVICES → 没 env？容器没申请 GPU
 ├─ ③ 宿主 nvidia-smi 正常吗？
 │     异常 → 驱动/模块问题，先修宿主（看 Xid/NVRM/dmesg）
 │     正常 ↓
 ├─ ④ 看 mode: grep mode config.toml
 │     legacy → 检查 hook 能否跑: nvidia-container-runtime-hook 手动起容器看 stderr
 │     auto(1.18) → 应走 JIT-CDI，正常不需 yaml
 ├─ ⑤ 起测试容器复现并看 runtime debug:
 │     config.toml 临时 log-level=debug → docker run --runtime=nvidia … 看日志
 └─ ⑥ 容器内验证注入产物(全齐=注入成功):
     ls /dev/nvidia*   /  grep -c nvidia /proc/1/mountinfo  /  ldconfig -p|grep libcuda
```

---

## 3. 方式 B：CDI 注入（spec 驱动）—— 你没在用，但要知道怎么上

### 两种 CDI 形态

| | 落盘 CDI（原生） | JIT-CDI（runtime 内） |
|---|---|---|
| spec 放哪 | `/etc/cdi` 或 `/var/run/cdi/*.yaml` | 不落盘，内存里 |
| 谁消费 | 原生 CDI 引擎：podman `--device nvidia.com/gpu=all`、containerd/k8s 的 cdi annotation | nvidia-container-runtime（mode=auto 且 NVML 可用时）|
| 谁生成 | `nvidia-cdi-refresh.service`（toolkit≥1.18）或手动 `nvidia-ctk cdi generate` | runtime 内部 nvcdi 现场生成 |
| 105 状态 | 无 yaml、`cdi list`=0（未启用） | **正在用**（当前 GPU 容器实际走这条）|

### 落盘 CDI 的调用链路

```
生成阶段:
  nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml   (或 nvidia-cdi-refresh.service 开机自动)
     nvcdi 经 NVML 枚举 GPU/MIG → 写 yaml: kind=nvidia.com/gpu, 每个设备列 devices/mounts/hooks
使用阶段:
  podman run --device nvidia.com/gpu=all …
  或 containerd/k8s 注入 cdi annotation(cdi.k8s.io/…) / 引擎直接读 spec
     → 引擎(非 NVIDIA runtime!) 解析 yaml → 把 devices+mounts 加进 OCI spec → runc 启动
```

### 特征指纹（认出走 CDI）

- 容器 **没有** NVIDIA_* env，但容器 spec/annotations 有 CDI 设备名（`nvidia.com/gpu=…`）
- `/etc/cdi` 或 `/var/run/cdi` 里**有 nvidia.yaml**
- `nvidia-ctk cdi list` 列得出设备
- 引擎是 podman / containerd(k8s)，而不是 Docker 的 runtime=nvidia

### 排查逻辑（CDI 注入出问题）

```
CDI 容器无 GPU？
 ├─ ① nvidia-ctk cdi list            → 没设备？yaml 没生成/生成失败 → 查 nvidia-cdi-refresh
 ├─ ② ls /etc/cdi /var/run/cdi       → yaml 在不在？在哪个 spec-dir(引擎要扫这两个)
 ├─ ③ grep kind: yaml                → kind 是否 = 引擎请求的 nvidia.com/gpu
 ├─ ④ 请求方式对了吗
 │     podman: --device nvidia.com/gpu=all
 │     containerd: 确认 /etc/containerd/config.toml enable_cdi / cdi_spec_dirs
 │     docker: 原生 CDI 要 --device nvidia.com/gpu=… (docker≥25)
 ├─ ⑤ yaml 里设备是否与宿主对得上(UUID/MIG 名)
 └─ ⑥ 起测试容器看引擎报错(找不到 cdi device / 权限 / 不存在)
```

---

## 4. 两种方式对比表（一句话版）

| 维度 | Runtime(nvidia-container-runtime) | CDI |
|---|---|---|
| 触发入口 | `--runtime=nvidia` + `NVIDIA_VISIBLE_DEVICES` env | `--device nvidia.com/gpu=…` / cdi annotation |
| spec 来源 | 启动时现场生成（JIT）或 hook 现场 configure | 预先落盘 yaml |
| 是否依赖 /etc/cdi | 否（JIT/legacy 都不需要） | 是（原生 CDI）|
| 消费引擎 | nvidia-container-runtime（NVIDIA 的） | 任何支持 CDI 的引擎（podman/containerd/docker）|
| 适合 | docker compose 传统部署（105 现状）| k8s / podman / 需要精确按 GPU/MIG 分配的编排 |
| config 开关 | config.toml 的 `mode`（auto/legacy/cdi）| spec-dirs + 引擎 CDI 开关 |
| 105 当前 | ✅ 用这个（JIT-CDI 子路径）| ❌ 未启用 |

---

## 5. 通用排查决策树（先分叉再深入）

```
症状：容器内 nvidia-smi 没 GPU / 应用找不到设备

第一步 分叉：容器是用 runtime 还是 CDI 申请的？
   docker inspect <c> | grep -E '"Runtime"|NVIDIA_VISIBLE_DEVICES|cdi'
   ├─ 有 NVIDIA_* env + Runtime=nvidia  → 方式A(Runtime) → 见 §2
   ├─ 无 env 但有 cdi device/annotation → 方式B(CDI)    → 见 §3
   └─ 都没有 → 容器根本没申请 GPU，查 compose 配置

第二步 无论哪种，先验宿主：
   nvidia-smi                       # 宿主驱动层
   ldconfig -p | grep nvidia-ml     # NVML 在不在
   宿主异常 → 驱动问题(与注入无关)，查 Xid/NVRM

第三步 验注入产物（容器内，全齐=OK）：
   docker exec <c> ls /dev/nvidia*
   docker exec <c> sh -c 'grep -c nvidia /proc/1/mountinfo'   # >0
   docker exec <c> sh -c 'ldconfig -p | grep -c libcuda'       # >0
```

---

## 6. 105 现场取证记录（两种方式当前状态）

| 证据 | 结果 | 说明 |
|---|---|---|
| `nvidia-container-runtime` 形态 | Go ELF(runc NVIDIA 版) | runtime 是 wrapper，会转 runc |
| `nvidia-container-runtime-hook` | Go ELF 存在 | legacy 路径可用的前提 |
| `/usr/share/containers/oci/hooks.d` | 不存在 oci-nvidia-hook.json | podman 的 hook 未装（podman 也不用）|
| host-files-for-container.d | devices.csv + drivers.csv | legacy/csv 挂载清单 |
| `nvidia-container-cli --help` | configure / info / list | cli 三种动作 |
| containerd-shim-runc-v2 | 在跑（每容器一 shim）| OCI → runc 实际执行 |
| 容器 Runtime | `"nvidia"` + env NVIDIA_VISIBLE_DEVICES=all | 走方式 A |
| /etc/cdi | 空；cdi list=0 | 落盘 CDI 未启用 |
| toolkit 1.18 mode=auto+NVML | JIT-CDI | 方式 A 内部的当前子路径 |

---

## 7. 一句话总结

**Runtime 注入 = NVIDIA 的 runtime 在容器启动瞬间"现问现挂"（105 现在：mode=auto → JIT-CDI/NVML 内存生成）；CDI 注入 = 先把设备清单写成 yaml，让任意支持 CDI 的引擎按清单挂。** 排查先分叉"容器用哪种方式申请的"，再按"宿主驱动 → runtime/CDI spec → 容器内注入产物"三层查，最后用三条容器内命令收尾验证。
