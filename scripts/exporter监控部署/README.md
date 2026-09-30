# 昇腾 NPU + 主机指标采集（111 机器）

主机：`kzzk-pc` / `192.168.21.111`　部署目录：`/deploy/infra/monitor/`

---

## 一、启动命令

### 0. 一键部署（推荐）

归档位置：`/E:/ZP-工作信息/infra-tool-ssdxt/prometheus/exporter/npu-exporter/`

```bash
cd <本目录>
sed -i 's/\r$//' deploy.sh        # 从 Windows 拷来的先转码
bash deploy.sh install            # 部署并启动（自动提取二进制、装服务、起容器、验证）
bash deploy.sh verify             # 只验证，不改动
bash deploy.sh status             # 看状态
bash deploy.sh restart            # 重启两者
bash deploy.sh uninstall          # 卸载
```

下面的 1 / 2 / 3 是手工步骤，`deploy.sh install` 等价于它们。

### 1. node-exporter（容器，docker-compose）

```bash
cd /deploy/infra/monitor
docker-compose up -d          # 启动
docker-compose ps             # 查看
docker-compose logs -f        # 日志
docker-compose down           # 停止
```

> 注意：这台机器上 `docker compose`（空格）子命令不可用，要用独立二进制 **`docker-compose`**（v2.29.7，在 `/usr/bin/docker-compose`）。

### 2. npu-exporter（宿主 systemd 服务）

```bash
systemctl start   npu-exporter     # 启动
systemctl status  npu-exporter     # 状态
systemctl restart npu-exporter     # 重启
journalctl -u npu-exporter -f      # 日志（stdout）
systemctl stop    npu-exporter     # 停止
systemctl disable npu-exporter     # 取消开机自启
```

### 3. 一次性全量起停

```bash
# 启动全部
systemctl start npu-exporter && cd /deploy/infra/monitor && docker-compose up -d

# 停止全部
systemctl stop npu-exporter && cd /deploy/infra/monitor && docker-compose down
```

---

## 二、端口与验证

| 组件 | 指标地址 | 健康检查 | 实测 |
|---|---|---|---|
| npu-exporter | `http://<ip>:8082/metrics` | `http://<ip>:11256/healthz` | 200，29 条 `npu_` 指标 |
| node-exporter | `http://<ip>:9100/metrics` | — | 200，1060 条 `node_` 指标 |

```bash
curl -s http://127.0.0.1:8082/metrics | grep -c '^npu_'
curl -s http://127.0.0.1:8082/metrics | grep '^npu_chip_info_name'
curl -s http://127.0.0.1:9100/metrics | grep -c '^node_'
ss -lntp | grep -E ':(8082|11256|9100)'
```

正常时应看到两张卡（`id="0"` / `id="1"`）：

```
npu_chip_info_name{id="0",name="310P3-Ascend-V1",pcie_bus_info="0000:0B:00.0"} 1
npu_chip_info_name{id="1",name="310P3-Ascend-V1",pcie_bus_info="0000:0B:00.0"} 1
npu_chip_info_health_status{id="0",...} 1
npu_chip_info_power{id="0",...} 44.7
npu_chip_info_temperature{id="0",...} 57
```

### Prometheus 抓取配置

```yaml
scrape_configs:
  - job_name: 'npu'
    static_configs:
      - targets: ['192.168.21.111:8082']
  - job_name: 'node'
    static_configs:
      - targets: ['192.168.21.111:9100']
```

---

## 三、为什么 npu-exporter 不用容器跑（重要）

**结论：这台机器上，容器内 DCMI 无法枚举 NPU；同样的二进制在宿主上完全正常。**

```
容器内（镜像自带 entrypoint 之外直接调用 npu-exporter）:
  [INFO] dcmi api version is dcmi
  [WARN] deviceManager get card list failed (attempt 1..N), cardNum=-1,
         cardList=[], err: get error card quantity: 0
  → 每 10 秒重试一次，等满 600 秒后失败

宿主上（同一个二进制 /opt/npu-exporter/npu-exporter）:
  http_code=200，29 条 npu_ 指标，两张卡数据齐全
```

**关键证据：这不是 exporter 的问题，而是容器隔离层面的问题** —— 用**华为自己的 `npu-smi`**（从宿主拷进容器）在容器里跑，同样失败：

```
npu get board type failed. ret is -9005
```

`npu-smi` 在宿主上正常，在任何容器里都失败，说明是「驱动 + 容器运行时」这一层的事。

### 已排查并排除的参数组合（全部无效，症状完全一致）

| # | 尝试的配置 | 结果 |
|---|---|---|
| 1 | `--privileged` + 挂 `/usr/local/Ascend/driver` + `/usr/local/dcmi` | -9005 |
| 2 | 1 + `-v /etc/ascend_install.info` | -9005 |
| 3 | 1 + `-v /var/log/npu:/usr/slog` | -9005 |
| 4 | `--device=/dev/davinci*` + `--runtime=ascend`（不用 privileged） | -9005 |
| 5 | 1 + 挂 `/etc/ld.so.conf.d/ascend_driver_so.conf` | -9005 |
| 6 | 1 + `seccomp/apparmor/label` 全 unconfined | -9005 |
| 7 | 1 + 挂整个 `/usr/local/Ascend` | -9005 |
| 8 | 1 + `--ipc=host --pid=host` | -9005 |
| 9 | 1 + `--net=host` | -9005 |
| 10 | 以上全部叠加 | -9005 |
| 11 | **官方 vLLM-Ascend 300I DUO 参数**（含 `--shm-size=1g`、lib64、version.info、ascend_install.info） | -9005 |
| 12 | 11 + 共享宿主 `/dev/shm` / `--shm-size=8g` / `--ipc=host` / `--uts=host` | -9005 |
| 13 | 11 + `--cap-add=SYS_ADMIN --cap-add=SYS_RAWIO` | -9005 |
| 14 | **Ascend Docker Runtime hook 方式**（`--runtime=ascend` + `ASCEND_VISIBLE_DEVICES=0,1`，驱动库与设备全交给 hook 挂，不手动挂） | -9005 |
| 15 | 14 + 官方 200I Pro 配方里的宿主配置文件（`/etc/hdcBasic.cfg` 等） | -9005 |
| 16 | 上述任一组合，且**确认没有其他进程占用 DCMI** | -9005 |

已排除的因素：设备节点不可见、cgroup 设备限制（容器内为 `a *:* rwm`）、capabilities（全 `0x3fffffffff`）、selinux/apparmor/seccomp、`/dev/shm` 大小、IPC/PID/NET/UTS namespace、CANN 库缺失（`ldd` 无 `not found`）、权限位、磁盘空间。

### 值得注意的两个旁证

1. **`/var/slogd` 和 `/var/dmp_daemon` 在宿主和镜像里都不存在。** 镜像自带的 `/run_for_310P_1usoc.sh` 第一件事就是启动这两个守护进程；它们通常是驱动安装时提供的，但这台机器的 `Ascend-hdk-310p-npu-driver_24.1.0.1` 的 `filelist.csv` 里根本没有它们。**如果华为确认这两个是必需组件，那这就是根因方向。**

2. **DCMI 是独占的。** 宿主上同时跑两个 DCMI 客户端会报：
   ```
   dcmi model initialization failed, because the device is used. ret is -8020
   ```
   所以**不要**同时运行容器版和宿主版的 npu-exporter。

### 建议向华为反馈的内容

- 现象：`npu-smi info` 在宿主正常，在**任意**容器内失败，`npu get board type failed. ret is -9005`
- 环境：Atlas 300I Duo (310P3) ×2、driver 24.1.0.1 / firmware 7.5.0.5.220、CANN 8.1.RC1、Ascend Docker Runtime 7.1.RC1、Docker 26.1.3（default-runtime=ascend，cgroup v1 + **cgroupfs** 驱动）、银河麒麟桌面 V10 国防版 / kernel 5.4.18-87.76-generic
- 已排除：设备节点、cgroup、capabilities、namespace、shm、安全模块、库依赖
- 可疑点：驱动包不含 `slogd` / `dmp_daemon`；Docker 用 `cgroupfs` 而非 `systemd` cgroup 驱动（Ascend 驱动的容器识别依赖 `/proc/self/cgroup`）

---

## 四、如何切回容器方式

如果后续驱动或容器运行时修好了，直接取消 `docker-compose.yml` 里 `npu-exporter` 段的注释即可（完整配置已写在注释里）。切换步骤：

```bash
systemctl disable --now npu-exporter        # 停掉宿主服务
cd /deploy/infra/monitor
# 编辑 docker-compose.yml，取消 npu-exporter 段的注释
docker-compose up -d
curl -s http://127.0.0.1:8082/metrics | grep -c '^npu_'   # 应 > 0
```

若容器版拿不到指标（仍是 `cardNum=-1`），说明问题没修好，回退：

```bash
docker-compose down
systemctl enable --now npu-exporter
```

---

## 五、文件与路径

### 本归档目录（源文件）

| 文件 | 说明 |
|---|---|
| `docker-compose.yml` | node-exporter 定义；npu-exporter 段完整注释保留，切回容器方式时取消注释 |
| `npu-exporter.service` | npu-exporter 的 systemd 单元 |
| `deploy.sh` | 一键部署 / 验证 / 状态 / 重启 / 卸载 |
| `README.md` | 本文件 |
| `../node-exporter/docker-compose.yml` | 只要 node-exporter 时用的独立 compose（非昇腾机器可直接复用） |

### 目标机上的落点

| 路径 | 说明 |
|---|---|
| `/deploy/infra/monitor/docker-compose.yml` | node-exporter 定义 |
| `/etc/systemd/system/npu-exporter.service` | npu-exporter 宿主服务单元 |
| `/opt/npu-exporter/npu-exporter` | 从镜像 `npu-exporter:v26.1.0-openeuler24.03-linuxarm64` 的 `/usr/local/bin/npu-exporter` 提取（27MB，sha256 `a3dc424dbc558ac9...`） |
| `/var/log/mindx-dl/npu-exporter/npu-exporter.log` | npu-exporter 日志（20MB 轮转） |
| `/var/log/ascend-docker-runtime/docker-runtime-log.log` | Ascend Docker Runtime hook 日志 |
| `/etc/ascend-docker-runtime.d/base.list` | hook 自动挂进容器的路径清单 |

`/opt/npu-exporter/npu-exporter` 的重新提取命令（镜像更新时用）：

```bash
docker create --name tmpget --entrypoint /bin/true \
  swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64
docker cp tmpget:/usr/local/bin/npu-exporter /opt/npu-exporter/npu-exporter
docker rm -f tmpget
chmod 755 /opt/npu-exporter/npu-exporter
systemctl restart npu-exporter
```
