#!/bin/bash
# 在 111 上部署 npu-exporter + node-exporter（docker-compose）
set +e
MON=/deploy/infra/monitor
mkdir -p $MON /var/log/mindx-dl/npu-exporter

echo "############ 0) 先找 slogd / dmp_daemon 到底在不在 ############"
for p in /var/slogd /var/dmp_daemon /usr/local/Ascend/driver/tools/slogd \
         /usr/local/Ascend/driver/tools/dmp_daemon /usr/local/bin/slogd /usr/bin/slogd; do
  printf "  %-52s " "$p"; [ -e "$p" ] && echo "存在" || echo "-"
done
echo "  全盘搜（限 3 层深度）:"
find / -maxdepth 4 -name "slogd" -o -maxdepth 4 -name "dmp_daemon" 2>/dev/null | head -5

echo
echo "############ 1) 写 /deploy/infra/monitor/docker-compose.yml ############"
cat > $MON/docker-compose.yml <<'YAML'
# ============================================================================
#  昇腾 NPU + 主机指标采集 (Prometheus exporters)
#  主机: kzzk-pc / 192.168.21.111
#  启动: cd /deploy/infra/monitor && docker-compose up -d
#  停止: docker-compose down
#  说明:
#    - npu-exporter  指标 :8082/metrics   健康 :11256/healthz
#    - node-exporter 指标 :9100/metrics
#
#   为什么 npu-exporter 要覆盖 entrypoint:
#      镜像自带 ENTRYPOINT 是 `cat /usr/local/agreement.txt; exec /bin/bash`，
#      属于"交互/开发态"镜像，不会自动拉起 exporter，必须显式执行二进制。
#
#   为什么不用镜像自带的 /run_for_310P_1usoc.sh:
#      该脚本开头 `set -e` 且第一件事是启动 /var/slogd 和 /var/dmp_daemon，
#      但这两个二进制在宿主和镜像里都不存在 -> 脚本立刻非零退出 -> 容器不起。
#      这里直接调用 npu-exporter 本体，跳过这两个可选守护进程。
# ============================================================================
name: monitor

services:
  # --------------------------------------------------------------------------
  # 昇腾 NPU 指标导出器
  # --------------------------------------------------------------------------
  npu-exporter:
    image: swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64
    container_name: npu-exporter
    restart: unless-stopped
    # 需要访问 /dev/davinci*、/dev/davinci_manager、/dev/devmm_svm、/dev/hisi_hdc
    # 同时规避麒麟 5.4 内核对 docker maskedPath(tmpfs nr_inodes=1) 的拒绝
    privileged: true
    security_opt:
      - label=disable
    ports:
      - "8082:8082"      # Prometheus 抓取端口
      - "11256:11256"    # healthz
    volumes:
      # 镜像内没有 dcmi/driver 库，npu-exporter 运行时 dlopen 它们，必须挂宿主
      - /usr/local/Ascend/driver:/usr/local/Ascend/driver
      - /usr/local/dcmi:/usr/local/dcmi
      # 日志落到宿主，排障方便
      - /var/log/mindx-dl:/var/log/mindx-dl
      # 网卡信息（300I Duo 上通常为空文件，挂了无害）
      - /etc/hccn.conf:/etc/hccn.conf:ro
      # 容器与 NPU 的映射关系（-containerMode=docker 需要）
      - /var/run/docker.sock:/var/run/docker.sock
    entrypoint: ["/bin/bash", "-c"]
    command:
      - |
        mkdir -p /var/log/mindx-dl/npu-exporter
        export LD_LIBRARY_PATH=/usr/local/lib:/usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/add-ons:/usr/local/Ascend/driver/lib64:/usr/local/dcmi
        echo "[entrypoint] LD_LIBRARY_PATH=$LD_LIBRARY_PATH"
        exec /usr/local/bin/npu-exporter \
          -port=8082 \
          -ip=0.0.0.0 \
          -logFile=/var/log/mindx-dl/npu-exporter/npu-exporter.log \
          -logLevel=0 \
          -containerMode=docker \
          -endpoint=/run/dockershim.sock \
          -containerd=/run/docker/containerd/containerd.sock \
          --enable-healthz=true \
          --healthz-address=11256

  # --------------------------------------------------------------------------
  # 主机指标导出器（CPU/内存/磁盘/网络/文件系统）
  # --------------------------------------------------------------------------
  node-exporter:
    image: swr.cn-north-4.myhuaweicloud.com/ddn-k8s/quay.io/prometheus/node-exporter:v1.9.1-linuxarm64
    container_name: node-exporter
    restart: unless-stopped
    # 必须用 host 网络 + host PID，否则 network/process 类指标采集到的是容器自己的
    network_mode: host
    pid: host
    security_opt:
      - label=disable
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - --path.procfs=/host/proc
      - --path.sysfs=/host/sys
      - --path.rootfs=/rootfs
      # 注意 compose 里 $ 要写成 $$，否则会被当成变量插值
      - "--collector.filesystem.mount-points-exclude=^/(dev|proc|run/credentials/.+|sys|var/lib/docker/.+|var/lib/containers/storage/.+)($$|/)"
YAML
echo "  已写入，语法检查:"
/usr/bin/docker-compose -f $MON/docker-compose.yml config -q && echo "    compose 语法 OK" || echo "    !! 语法有问题"

echo
echo "############ 2) 启动 ############"
cd $MON
docker rm -f node-exporter npu-exporter 2>/dev/null
/usr/bin/docker-compose up -d 2>&1 | tail -20

echo
echo "############ 3) 等待并观察状态 ############"
sleep 12
/usr/bin/docker-compose ps 2>&1

echo
echo "--- npu-exporter 日志 ---"
docker logs --tail 40 npu-exporter 2>&1 | sed 's/^/  /'
echo
echo "--- node-exporter 日志 ---"
docker logs --tail 15 node-exporter 2>&1 | sed 's/^/  /'

echo
echo "############ 4) 探活 ############"
echo "--- npu-exporter :8082/metrics ---"
curl -s -m 10 http://127.0.0.1:8082/metrics 2>&1 | head -5
echo "  npu_ 开头指标条数: $(curl -s -m 10 http://127.0.0.1:8082/metrics 2>&1 | grep -c '^npu_')"
echo "  样例:"
curl -s -m 10 http://127.0.0.1:8082/metrics 2>&1 | grep -E "^npu_chip_info_(health_status|temperature|utilization|power|hbm_used_memory)" | head -8 | sed 's/^/    /'
echo "--- npu-exporter :11256/healthz ---"
curl -s -m 5 -o /dev/null -w "  HTTP %{http_code}\n" http://127.0.0.1:11256/healthz 2>&1

echo "--- node-exporter :9100/metrics ---"
echo "  node_ 开头指标条数: $(curl -s -m 10 http://127.0.0.1:9100/metrics 2>&1 | grep -c '^node_')"
curl -s -m 10 http://127.0.0.1:9100/metrics 2>&1 | grep -E "^node_(uname|load1|memory_MemTotal_bytes)" | head -4 | sed 's/^/    /'

echo
echo "############ 5) 端口监听 ############"
ss -lntp 2>/dev/null | grep -E ":(8082|11256|9100)\b"

echo
echo "############ 6) 若要排查，日志文件在 ############"
ls -la /var/log/mindx-dl/npu-exporter/ 2>&1
