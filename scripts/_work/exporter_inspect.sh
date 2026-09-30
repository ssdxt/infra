#!/bin/bash
IMG_NPU=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64
IMG_NODE=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/quay.io/prometheus/node-exporter:v1.9.1-linuxarm64

echo "############ 1) npu-exporter 镜像构造历史（看它本来打算怎么跑）############"
docker history --no-trunc --format '{{.CreatedBy}}' $IMG_NPU 2>&1 | head -25

echo
echo "############ 2) npu-exporter 镜像内文件系统探查 ############"
docker run --rm --entrypoint /bin/bash $IMG_NPU -c '
  echo "--- / ---"; ls -la / 2>&1
  echo "--- /usr/local ---"; ls -la /usr/local 2>&1
  echo "--- /usr/local/bin ---"; ls -la /usr/local/bin 2>&1
  echo "--- /home ---"; ls -la /home 2>&1
  echo "--- agreement.txt ---"; ls -la /usr/local/agreement.txt 2>&1
  echo "--- 搜 exporter 相关文件 ---"
  find / -xdev \( -iname "*exporter*" -o -iname "*npu*" \) 2>/dev/null | grep -vE "^/proc|^/sys" | head -30
  echo "--- 搜启动脚本 ---"
  find / -xdev -maxdepth 4 \( -name "start*.sh" -o -name "run*.sh" -o -name "*.yaml" -o -name "*.yml" \) 2>/dev/null | grep -vE "^/proc|^/sys" | head -20
  echo "--- 搜二进制 ---"
  for d in /usr/local/bin /usr/bin /bin /opt /home; do
    [ -d "$d" ] && find "$d" -maxdepth 3 -type f -executable 2>/dev/null | head -20
  done
' 2>&1

echo
echo "############ 3) 找到二进制后打印 --help（拿默认端口和参数）############"
docker run --rm --entrypoint /bin/bash $IMG_NPU -c '
  BIN=$(find / -xdev -type f \( -iname "*npu-exporter*" -o -iname "*npu_exporter*" \) 2>/dev/null | head -1)
  echo "BIN=$BIN"
  if [ -n "$BIN" ]; then
    echo "--- file ---"; file "$BIN" 2>&1
    echo "--- --help ---"; "$BIN" --help 2>&1 | head -50
  fi
' 2>&1

echo
echo "############ 4) node-exporter 版本与参数 ############"
docker run --rm $IMG_NODE --version 2>&1 | head -5
echo "--- 关键参数确认 ---"
docker run --rm $IMG_NODE --help 2>&1 | grep -iE "path.procfs|path.sysfs|path.rootfs|web.listen-address|collector.filesystem.mount-points-exclude" | head -10

echo
echo "############ 5) oceanbase-ce 是怎么起的（学可用姿势）############"
docker inspect -f '  Privileged={{.HostConfig.Privileged}}' oceanbase-ce 2>&1
docker inspect -f '  SecurityOpt={{.HostConfig.SecurityOpt}}' oceanbase-ce 2>&1
docker inspect -f '  Runtime={{.HostConfig.Runtime}}  NetworkMode={{.HostConfig.NetworkMode}}' oceanbase-ce 2>&1
docker inspect -f '  RestartPolicy={{.HostConfig.RestartPolicy}}' oceanbase-ce 2>&1
docker inspect -f '  Binds={{range .HostConfig.Binds}}{{.}} {{end}}' oceanbase-ce 2>&1
docker inspect -f '  Devices={{.HostConfig.Devices}}' oceanbase-ce 2>&1
docker inspect -f '  Ulimits={{.HostConfig.Ulimits}}  Tmpfs={{.HostConfig.Tmpfs}}' oceanbase-ce 2>&1

echo
echo "############ 6) compose 可用性 ############"
command -v docker-compose && docker-compose version 2>&1 | head -2 || echo "  无 docker-compose"
command -v docker && docker compose version 2>&1 | head -2
ls /usr/libexec/docker/cli-plugins/ /usr/local/lib/docker/cli-plugins/ 2>&1

echo
echo "############ 7) 麒麟 docker 老坑验证：随便起个容器会不会报 nr_inodes ############"
docker run --rm --entrypoint /bin/sh $IMG_NODE -c 'echo container-ok' 2>&1 | tail -5

echo
echo "############ 8) 宿主内核/内存/防火墙 ############"
uname -r
free -g | head -2
echo "--- firewalld/ufw ---"
systemctl is-active firewalld 2>&1
systemctl is-active ufw 2>&1
iptables -S 2>/dev/null | head -5
