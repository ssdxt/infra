#!/bin/bash
echo "########## 1. /deploy 完整结构 ##########"
ls -la /deploy/ 2>&1

echo
echo "########## 2. 找 dockerun / docker_run ##########"
for d in /deploy/model/dockerun /deploy/models/docker_run /deploy/model /deploy/models; do
  echo "--- $d ---"
  ls -la "$d" 2>&1 | head -20
done

echo
echo "########## 3. 全盘 compose 文件 ##########"
find /deploy -maxdepth 6 \( -name "docker-compose*.y*ml" -o -name "compose*.y*ml" \) 2>/dev/null | sort

echo
echo "########## 4. docker 状态 ##########"
docker version --format 'server {{.Server.Version}}' 2>&1 | head -2
echo "--- running containers ---"
docker ps --format '  {{.ID}}  {{.Names}}  {{.Status}}  {{.Image}}' 2>&1
echo "--- all containers ---"
docker ps -a --format '  {{.ID}}  {{.Names}}  {{.Status}}  {{.Image}}' 2>&1 | head -15

echo
echo "########## 5. 谁占着 NPU 显存（PID 4492 / 4494）##########"
for p in 4492 4494; do
  echo "--- PID $p ---"
  ps -o pid,ppid,user,etime,rss,cmd -p $p 2>&1 | head -3
  echo "  cgroup: $(cat /proc/$p/cgroup 2>/dev/null | head -2)"
done

echo
echo "########## 6. 全部 mindie 相关进程 ##########"
ps -eo pid,ppid,user,etime,rss,cmd 2>/dev/null | grep -iE "[m]indie" | head -10

echo
echo "########## 7. NPU 显存明细 ##########"
npu-smi info 2>&1 | tail -18

echo
echo "########## 8. 磁盘 ##########"
df -h / /deploy 2>/dev/null

echo
echo "########## 9. docker 存储位置 ##########"
docker info 2>/dev/null | grep -E "Docker Root Dir|Storage Driver|default-runtime"
cat /etc/docker/daemon.json 2>/dev/null

echo
echo "########## 10. images ##########"
docker images --format '  {{.Repository}}:{{.Tag}}  {{.Size}}' 2>&1 | head -15
