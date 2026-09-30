#!/bin/bash
echo "############ 1) 相关镜像 ############"
docker images --format '{{.Repository}}:{{.Tag}}|{{.ID}}|{{.Size}}|{{.CreatedSince}}' 2>&1 \
  | grep -iE "export|npu|node|prom|monitor" || echo "  (没匹配到)"
echo "--- 全部镜像 ---"
docker images --format '{{.Repository}}:{{.Tag}}' 2>&1 | head -40

echo
echo "############ 2) 现有容器（含已退出的）############"
docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}' 2>&1 | head -40

echo
echo "############ 3) exporter 类容器的失败原因 ############"
for c in $(docker ps -a --format '{{.Names}}' 2>/dev/null | grep -iE "export"); do
  echo "===== $c ====="
  docker inspect -f '  Status={{.State.Status}} ExitCode={{.State.ExitCode}} OOM={{.State.OOMKilled}} Error="{{.State.Error}}" StartedAt={{.State.StartedAt}} FinishedAt={{.State.FinishedAt}}' "$c" 2>&1
  docker inspect -f '  Image={{.Config.Image}}  Cmd={{.Config.Cmd}}  Entrypoint={{.Config.Entrypoint}}' "$c" 2>&1
  docker inspect -f '  Mounts={{range .Mounts}}[{{.Source}}->{{.Destination}}:{{.Mode}}]{{end}}' "$c" 2>&1
  docker inspect -f '  Ports={{.HostConfig.PortBindings}}  Net={{.HostConfig.NetworkMode}}  Priv={{.HostConfig.Privileged}}  SecOpt={{.HostConfig.SecurityOpt}}' "$c" 2>&1
  echo "  --- logs tail 30 ---"
  docker logs --tail 30 "$c" 2>&1 | sed 's/^/    /'
  echo
done

echo
echo "############ 4) 镜像元数据（决定端口/入口）############"
for img in $(docker images --format '{{.Repository}}:{{.Tag}}' 2>/dev/null | grep -iE "export"); do
  echo "===== $img ====="
  docker inspect -f '  Entrypoint={{.Config.Entrypoint}}' "$img" 2>&1
  docker inspect -f '  Cmd={{.Config.Cmd}}' "$img" 2>&1
  docker inspect -f '  ExposedPorts={{.Config.ExposedPorts}}' "$img" 2>&1
  docker inspect -f '  User={{.Config.User}}  WorkDir={{.Config.WorkingDir}}  Env={{.Config.Env}}' "$img" 2>&1
  docker inspect -f '  Volumes={{.Config.Volumes}}  Arch={{.Architecture}}  OS={{.Os}}' "$img" 2>&1
  echo "  --- 镜像内可执行入口 ---"
  docker inspect -f '  Healthcheck={{.Config.Healthcheck}}' "$img" 2>&1
done

echo
echo "############ 5) 端口占用 ############"
ss -lntp 2>/dev/null | grep -E ":(8082|9100|8000|9400|8080|3000|9090|9091)\b" || echo "  这些端口都没被占"

echo
echo "############ 6) 已有的部署目录结构 ############"
ls -la /deploy/ 2>&1
echo "--- infra 下 ---"
ls -la /deploy/infra/ 2>&1
echo "--- 找 exporter/monitor 相关的 yaml ---"
find /deploy -maxdepth 4 \( -iname "*exporter*" -o -iname "*monitor*" -o -iname "*prometheus*" \) 2>/dev/null | head -20

echo
echo "############ 7) docker 环境 ############"
docker version --format '  Server={{.Server.Version}}  Client={{.Client.Version}}' 2>&1
docker compose version 2>&1 | head -2
docker info 2>/dev/null | grep -iE "Runtime|Storage Driver|Cgroup|Kernel"
echo "  --- networks ---"
docker network ls

echo
echo "############ 8) NPU 设备节点与驱动目录（npu-exporter 依赖）############"
ls -l /dev/davinci* /dev/davinci_manager /dev/devmm_svm /dev/hisi_hdc 2>&1
echo "--- driver 目录 ---"
ls /usr/local/Ascend/driver/ 2>&1
echo "--- driver/lib64 ---"
ls /usr/local/Ascend/driver/lib64/ 2>&1 | head
echo "--- /etc/hccn.conf ---"
ls -la /etc/hccn.conf 2>&1

echo
echo "############ 9) Ascend Docker Runtime 是否已配为默认运行时 ############"
grep -A3 -iE "runtimes|default-runtime" /etc/docker/daemon.json 2>&1
