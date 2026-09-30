#!/bin/bash
echo "########## 1. 名字带 glm 的容器 ##########"
docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}' 2>&1 | grep -i glm || echo "  没有 glm 容器"
echo "--- 全部容器 ---"
docker ps -a --format '  {{.Names}} | {{.Status}} | {{.Image}}' 2>&1

echo
echo "########## 2. 容器详情 ##########"
for c in $(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -i glm); do
  echo "===== $c ====="
  docker inspect -f '  State      = {{.State.Status}}  ExitCode={{.State.ExitCode}}  OOM={{.State.OOMKilled}}  Restarting={{.State.Restarting}}  RestartCount={{.RestartCount}}' "$c" 2>&1
  docker inspect -f '  StartedAt  = {{.State.StartedAt}}   FinishedAt={{.State.FinishedAt}}' "$c" 2>&1
  docker inspect -f '  Error      = {{.State.Error}}' "$c" 2>&1
  docker inspect -f '  Health     = {{if .State.Health}}{{.State.Health.Status}}{{else}}<none>{{end}}' "$c" 2>&1
  docker inspect -f '  Cmd        = {{json .Config.Cmd}}' "$c" 2>&1
  docker inspect -f '  Entrypoint = {{json .Config.Entrypoint}}' "$c" 2>&1
  docker inspect -f '  User       = {{.Config.User}}   WorkingDir={{.Config.WorkingDir}}   Runtime={{.HostConfig.Runtime}}' "$c" 2>&1
  docker inspect -f '  Privileged = {{.HostConfig.Privileged}}  ShmSize={{.HostConfig.ShmSize}}' "$c" 2>&1
  docker inspect -f '  Devices    = {{json .HostConfig.Devices}}' "$c" 2>&1
  docker inspect -f '  GroupAdd   = {{json .HostConfig.GroupAdd}}' "$c" 2>&1
  echo "  Binds:"
  docker inspect -f '{{range .HostConfig.Binds}}    {{.}}{{"\n"}}{{end}}' "$c" 2>&1
  echo "  --- 容器内进程 ---"
  docker top "$c" 2>&1 | head -8
  echo
done

echo "########## 3. 容器日志 tail 80 ##########"
for c in $(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -i glm); do
  echo "===== $c ====="
  docker logs --tail 80 "$c" 2>&1 | tail -80
  echo
done

echo "########## 4. MindIE 日志文件 ##########"
ls -la /deploy/logs/mindie/ 2>&1
echo "--- glm-4.log tail 60 ---"
tail -60 /deploy/logs/mindie/glm-4.log 2>&1
echo "--- ascend plog 最近目录 ---"
ls -lat /deploy/logs/mindie/ascend/ 2>/dev/null | head -5
find /root/ascend/log /var/log/npu -name "plog*" -newermt "-2 hours" 2>/dev/null | head -5

echo
echo "########## 5. NPU 当前状态 ##########"
npu-smi info 2>&1 | head -14

echo
echo "########## 6. 谁在占着 NPU / DCMI ##########"
echo "--- 宿主上跑着的 npu-exporter（我部署的服务，会持续查 DCMI）---"
systemctl is-active npu-exporter 2>&1
pgrep -a npu-exporter 2>&1 | head -3
echo "--- 有没有别的进程在用 daVinci 设备 ---"
fuser -v /dev/davinci0 /dev/davinci1 /dev/davinci_manager 2>&1 | head -20 || echo "  (fuser 无输出)"

echo
echo "########## 7. dmesg 里的昇腾报错 ##########"
dmesg -T 2>/dev/null | grep -iE "aicore|davinci|devmm|ascend|mte|ecc" | tail -25

echo
echo "########## 8. 端口 10006 ##########"
ss -lntp 2>/dev/null | grep -E ':10006' || echo "  10006 没有监听"

echo
echo "########## 9. MindIE config 关键项 ##########"
for f in /deploy/models/glm-4-9b-chat/conf/config.json \
         /usr/local/Ascend/mindie/latest/mindie-service/conf/config.json; do
  echo "--- $f ---"
  if [ -f "$f" ]; then
    ls -la "$f"
    grep -nE '"(npuDeviceIds|worldSize|modelName|modelWeightPath|maxSeqLen|maxInputTokenLen|npuMemSize|port|httpsEnabled|openAiSupport)"' "$f" 2>/dev/null | head -20
  else
    echo "  不存在"
  fi
done

echo
echo "########## 10. 最近有没有 OOM / 被 kill ##########"
dmesg -T 2>/dev/null | grep -iE "out of memory|oom-kill|killed process" | tail -10 || echo "  无 OOM 记录"
free -g | head -2
