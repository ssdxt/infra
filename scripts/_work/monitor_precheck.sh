#!/bin/bash
IMG_NPU=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64

echo "############ 1) 宿主侧 /var/slogd /var/dmp_daemon ############"
ls -la /var/slogd /var/dmp_daemon 2>&1
echo "--- 进程 ---"
ps -ef | grep -E "slogd|dmp_daemon" | grep -v grep || echo "  (未运行)"
echo "--- /var/dmp 与 /usr/slog ---"
ls -ld /var/dmp /usr/slog /home/drv/hdc_ppc 2>&1

echo
echo "############ 2) 镜像内 /var 结构与关键路径 ############"
docker run --rm --entrypoint /bin/bash $IMG_NPU -c '
  echo "--- /var ---"; ls -la /var/ 2>&1
  echo "--- /var/slogd /var/dmp_daemon ---"; ls -la /var/slogd /var/dmp_daemon 2>&1
  echo "--- /usr/slog ---"; ls -la /usr/slog 2>&1
  echo "--- /var/dmp ---"; ls -la /var/dmp 2>&1
  echo "--- /var/log/mindx-dl ---"; ls -la /var/log/mindx-dl 2>&1
  echo "--- /usr/local/dcmi ---"; ls -la /usr/local/dcmi 2>&1
  echo "--- /home/drv ---"; ls -la /home/drv 2>&1
  echo "--- 找 slogd/dmp_daemon ---"
  for p in /var/slogd /var/dmp_daemon /usr/local/Ascend/driver/tools/slogd /usr/local/Ascend/driver/tools/dmp_daemon /usr/slog/slogd; do
    printf "    %-50s " "$p"; [ -e "$p" ] && echo "存在" || echo "-"
  done
  echo "--- 容器内是否有 su / HwHiAiUser ---"
  id HwHiAiUser 2>&1; id HwDmUser 2>&1; command -v su 2>&1
  echo "--- LD 依赖：npu-exporter 需要哪些 so ---"
  ldd /usr/local/bin/npu-exporter 2>&1 | head -20
' 2>&1

echo
echo "############ 3) socket 现状 ############"
for s in /var/run/docker.sock /run/docker.sock /run/containerd/containerd.sock \
         /run/dockershim.sock /run/docker/containerd/containerd.sock /run/docker.pid; do
  printf "  %-50s " "$s"
  ls -la "$s" 2>/dev/null | awk '{print $1, $3":"$4, $NF}' || echo "不存在"
done
echo "--- 宿主 containerd 状态 ---"
systemctl is-active containerd 2>&1
ss -lx 2>/dev/null | grep -E "containerd|docker" | head

echo
echo "############ 4) 宿主 driver 版本与 add-ons ############"
cat /usr/local/Ascend/driver/version.info 2>&1
ls -d /usr/local/Ascend/add-ons 2>&1
echo "--- /usr/local/Ascend 顶层 ---"
ls /usr/local/Ascend/ 2>&1

echo
echo "############ 5) compose 环境与目标目录 ############"
/usr/bin/docker-compose version 2>&1 | head -2
ls -la /deploy/infra/ 2>&1
ls -ld /deploy/infra/monitor 2>&1
echo "--- 现有 compose 文件风格参考 ---"
ls -la /deploy/infra/*/*.y*ml /deploy/models/docker_run/*/*.y*ml 2>/dev/null | head

echo
echo "############ 6) 端口占用复核 ############"
ss -lntp 2>/dev/null | grep -E ":(8082|11256|9100)\b" || echo "  8082 / 11256 / 9100 都空闲"
