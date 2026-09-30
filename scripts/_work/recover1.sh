#!/bin/bash
R=/deploy/rma-20260914-2106030737ZER3013372
OUT=/deploy/crash-recovery
sudo mkdir -p $OUT

echo "########## 1. 抢救上一次启动的内核日志（崩溃现场）##########"
{
  echo "===== 启动列表 ====="; sudo journalctl --list-boots --no-pager 2>&1 | tail -5
  echo; echo "===== 上一次启动的内核日志（全文）====="
  sudo journalctl -k -b -1 --no-pager 2>&1 | tail -300
  echo; echo "===== 上一次启动里跟 NPU/panic 相关的 ====="
  sudo journalctl -b -1 --no-pager 2>&1 | grep -iE "ascend|devmm|VPD|davinci|panic|Oops|BUG:|Call trace|segfault|hung task|devdrv" | tail -80
} | sudo tee $OUT/prev-boot-kernel.log >/dev/null
echo "已保存: $OUT/prev-boot-kernel.log ($(sudo wc -l < $OUT/prev-boot-kernel.log) 行)"

echo
echo "########## 2. 本次启动的异常 ##########"
sudo journalctl -k -b --no-pager 2>&1 | grep -iE "ascend|devmm|VPD|davinci|panic|Oops|BUG:|error|fail" | tail -40

echo
echo "########## 3. Docker 存储状态 ##########"
sudo docker info 2>/dev/null | grep -E "Docker Root Dir|Storage Driver|Server Version"
echo "--- overlay2 目录 ---"
sudo ls -la /deploy/docker/ 2>&1 | head -12
echo "--- 磁盘 ---"
df -h /deploy / 2>&1

echo
echo "########## 4. 备份所有容器的配置（删除前必做）##########"
for c in glm-4-9b-chat bge-m3-npu milvus-standalone milvus-etcd oceanbase-ce; do
  if sudo docker inspect "$c" >/dev/null 2>&1; then
    sudo bash -c "docker inspect $c > $OUT/inspect-$c.json 2>&1"
    echo "  已备份 $c"
  fi
done
sudo ls -la $OUT/

echo
echo "########## 5. 检查 layerdb 里的 mount 记录 ##########"
for id in 3b7e81f54c6e eaa9baf7e5fe 79b2c1201f44 11946a752356 debe4cefc22c; do
  echo "--- $id ---"
  sudo ls -d /deploy/docker/image/overlay2/layerdb/mounts/$id* 2>&1 | head -2
done

echo
echo "########## 6. 文件系统有没有报错 ##########"
sudo dmesg -T 2>/dev/null | grep -iE "ext4|xfs|I/O error|corrupt|remount|read-only" | tail -15
