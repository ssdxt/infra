#!/bin/bash
R=/deploy/rma-20260914-2106030737ZER3013372

echo "########## 1. 修正权限（a+rX：目录补 x 位，普通文件不加执行位）##########"
sudo chmod -R a+rX $R
sudo find $R -type d -exec chmod 755 {} \;
sudo find $R -type f -exec chmod 644 {} \;
sudo ls -ld $R $R/ascend-plog $R/ascend-plog/log/debug/plog

echo
echo "########## 2. 复核关键证据（这次 glob 由 root 展开）##########"
sudo bash -c '
R=/deploy/rma-20260914-2106030737ZER3013372
D=$R/ascend-plog/log/debug/plog
echo "--- aicore exception 次数 ---"
grep -c "aicore exception" $D/*.log
echo "--- DDR address out of range 次数 ---"
grep -c "DDR address of the MTE instruction is out of range" $D/*.log
echo "--- mte ccu ecc 1bit error 次数 ---"
grep -c "mte ccu ecc 1bit error" $D/*.log
echo "--- 报错的 core id 列表 ---"
grep -oE "core id is [0-9]" $D/*.log | sed "s/.*core id is /core /" | sort -u | tr "\n" " "
echo
echo "--- watchdog ---"
grep -h "SetWatchDogDevStatus" $R/ascend-plog/log/run/plog/*.log
'

echo
echo "########## 3. 重新打包 ##########"
sudo rm -f $R.tar.gz
cd /deploy || exit 1
sudo tar czf $R.tar.gz -C /deploy "$(basename $R)"
sudo chmod 644 $R.tar.gz
sudo ls -la $R.tar.gz
echo "sha256: $(sudo sha256sum $R.tar.gz | awk '{print $1}')"

echo
echo "########## 4. 包内核对 ##########"
sudo tar tzf $R.tar.gz | grep -E "报修单|plog|npu-smi|system-info"
