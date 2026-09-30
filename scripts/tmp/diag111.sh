#!/bin/bash
# 只读诊断：判断 310P3 算子失败是硬件故障还是驱动/固件问题
echo "################ 1. 驱动/固件实际版本 ################"
grep -E '^Version=|^version=' /usr/local/Ascend/driver/version.info 2>&1
echo "--- npu-smi -t board (card0) ---"
npu-smi info -t board -i 0 2>&1 | head -20
echo "--- npu-smi -t board (card1) ---"
npu-smi info -t board -i 1 2>&1 | head -20
echo "--- npu-smi -t common (card0) ---"
npu-smi info -t common -i 0 2>&1 | head -40

echo
echo "################ 2. 健康 / ECC / 错误计数 ################"
npu-smi info -t health -i 0 2>&1 | head -20
echo "--- ecc (card0) ---"
npu-smi info -t ecc -i 0 2>&1 | head -40
echo "--- err-count (card0) ---"
npu-smi info -t err-count -i 0 2>&1 | head -30

echo
echo "################ 3. 内核态报错 ################"
echo "--- dmesg | davinci/ascend ---"
dmesg -T 2>/dev/null | grep -iE 'davinci|ascend|drvdev|svm|hdc|aicore|mte' | tail -40

echo
echo "################ 4. 固件包 vs 生效版本 ################"
ls -l /usr/local/Ascend/firmware/ 2>&1 | head
cat /usr/local/Ascend/firmware/version.info 2>&1 | head -20
echo "--- 安装包清单 ---"
ls -l /deploy/driver/Ascend/ 2>/dev/null | grep -iE 'driver|firmware'
ls -l /home/kzzk/*.run 2>/dev/null

echo
echo "################ 5. 历史 aicore 故障日志 ################"
ls -dt /root/ascend/log/* 2>/dev/null | head -5
grep -rl 'aicore error' /root/ascend/log/ 2>/dev/null | head -5
find /root/ascend/log -name 'plog*' -newermt '-30 days' 2>/dev/null | head -3
