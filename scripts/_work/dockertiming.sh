#!/bin/bash
echo "########## 1. 分区与挂载 ##########"
echo "--- /etc/fstab ---"
grep -vE "^\s*#|^\s*$" /etc/fstab

echo
echo "--- mount | grep deploy ---"
mount | grep -E "deploy|nvme0n1p5"

echo
echo "--- 当前挂载点 ---"
df -h / /deploy 2>&1

echo
echo "########## 2. Docker 的 data-root 配置 ##########"
echo "--- /etc/docker/daemon.json ---"
grep -E "data-root|default-runtime" /etc/docker/daemon.json
echo
echo "--- docker info 实际用的 Root Dir ---"
docker info 2>/dev/null | grep -E "Docker Root Dir|Storage Driver"

echo
echo "########## 3. docker.service 的依赖关系（关键）##########"
echo "--- RequiresMountsFor ---"
systemctl show docker -p RequiresMountsFor 2>/dev/null
echo "--- After ---"
systemctl show docker -p After 2>/dev/null | tr ' ' '\n' | grep -iE "mount|local-fs|deploy" | head -10
echo "--- Wants ---"
systemctl show docker -p Wants 2>/dev/null | tr ' ' '\n' | grep -iE "mount|local-fs" | head -5
echo
echo "--- 有没有 deploy.mount 这个 unit ---"
systemctl list-units --type=mount --all 2>/dev/null | grep -iE "deploy|nvme"

echo
echo "########## 4. 启动时序：/deploy 挂载 vs docker 启动 ##########"
echo "--- 本次启动的时间线 ---"
journalctl -b --no-pager -o short-iso 2>/dev/null \
  | grep -iE "deploy|docker\.service|mount.*nvme0n1p5|Started Docker" \
  | head -30

echo
echo "########## 5. systemd 关键链 ##########"
systemd-analyze critical-chain docker.service 2>&1 | head -25

echo
echo "########## 6. 根分区下有没有被“藏起来”的 docker 目录 ##########"
echo "--- /deploy 是挂载点，看根分区上的 /deploy 内容需要临时绑定，这里只列 /deploy 当前内容 ---"
ls -la /deploy/ 2>&1 | head -15
echo
echo "--- 根分区使用量（若根分区里有 docker 数据会很明显）---"
df -h / | tail -1
du -sh /var/lib/docker 2>/dev/null || echo "  /var/lib/docker 不存在"
