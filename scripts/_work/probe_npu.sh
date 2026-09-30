#!/bin/bash
# READ-ONLY probe. No modifications.
echo "########## 1. OS / kernel / uptime ##########"
cat /etc/os-release 2>/dev/null | head -4
uname -a
cat /proc/uptime
echo "hostname: $(hostname)"

echo
echo "########## 2. NPU hardware (PCIe) ##########"
lspci -nn 2>/dev/null | grep -iE "19e5|huawei|ascend" || echo "  no Huawei/19e5 PCIe device found"
echo "--- lspci all (first 20) ---"
lspci 2>/dev/null | head -20

echo
echo "########## 3. NPU device nodes ##########"
ls -la /dev/davinci* /dev/devmm_svm /dev/hisi_hdc 2>&1 | head -10

echo
echo "########## 4. Ascend software stack ##########"
ls -d /usr/local/Ascend 2>/dev/null && ls /usr/local/Ascend/ 2>/dev/null || echo "  /usr/local/Ascend NOT present"
echo "--- npu-smi ---"
which npu-smi 2>/dev/null || echo "  npu-smi NOT in PATH"
ls -la /usr/local/bin/npu-smi 2>/dev/null

echo
echo "########## 5. npu-smi info ##########"
npu-smi info 2>&1 | head -25

echo
echo "########## 6. kernel modules ##########"
lsmod 2>/dev/null | grep -iE "drv|ascend|davinci|devdrv" || echo "  no ascend kernel modules loaded"

echo
echo "########## 7. /deploy partition ##########"
df -h 2>/dev/null | head -12
echo "--- /deploy ---"
ls -la /deploy/ 2>&1 | head -20

echo
echo "########## 8. target compose dirs ##########"
for d in /deploy/model/dockerun /deploy/models/docker_run /deploy/model /deploy/models; do
  echo "--- $d ---"
  ls -la "$d" 2>&1 | head -15
done

echo
echo "########## 9. find compose files ##########"
find /deploy -maxdepth 5 \( -name "docker-compose*.y*ml" -o -name "compose*.y*ml" \) 2>/dev/null | sort | head -30

echo
echo "########## 10. docker ##########"
which docker 2>/dev/null && docker version --format '{{.Server.Version}}' 2>&1 | head -2 || echo "  docker NOT installed"
echo "--- containers ---"
docker ps -a --format '  {{.Names}}  {{.Status}}  {{.Image}}' 2>&1 | head -10

echo
echo "########## 11. memory / cpu ##########"
free -h 2>/dev/null
nproc 2>/dev/null
