#!/bin/bash
R=/deploy/rma-20260914-2106030737ZER3013372
D=$R/ascend-plog/log/debug/plog

echo "=== 文件是否存在 ==="
sudo ls -la $D/
echo
echo "=== 直接 grep 单个文件（不吞错误）==="
sudo grep -c "aicore exception" $D/plog-173_20260913230036718.log
echo "退出码: $?"
echo
echo "=== grep 'DDR address' ==="
sudo grep -c "DDR address of the MTE instruction is out of range" $D/plog-173_20260913230036718.log
echo
echo "=== grep 'mte ccu ecc' ==="
sudo grep -c "mte ccu ecc 1bit error" $D/plog-173_20260913230036718.log
echo
echo "=== watchdog 行 ==="
sudo grep -h "SetWatchDogDevStatus" $R/ascend-plog/log/run/plog/plog-173_20260913225957574.log
echo
echo "=== 用通配符 ==="
sudo grep -c "aicore exception" $D/*.log
