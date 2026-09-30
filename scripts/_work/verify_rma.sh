#!/bin/bash
R=/deploy/rma-20260914-2106030737ZER3013372

echo "########## 1. npu-smi / 系统信息摘要 ##########"
sudo grep -E "Serial Number|Chip Fault|Health Status|DDR Single Bit Error Count|Total DDR Capacity|LnkSta|First power-on|Firmware Version|Software Version" \
  $R/npu-smi/npu-smi-all.txt $R/system-info.txt 2>/dev/null | head -25

echo
echo "########## 2. 关键错误是否在包内 ##########"
echo "--- 含 'DDR address of the MTE instruction is out of range' 的文件 ---"
sudo grep -l "DDR address of the MTE instruction is out of range" $R/ascend-plog/log/debug/plog/*.log 2>/dev/null
echo "--- 'mte ccu ecc 1bit error' 出现次数 ---"
sudo grep -c "mte ccu ecc 1bit error" $R/ascend-plog/log/debug/plog/*.log 2>/dev/null
echo "--- 'aicore exception' 出现次数 ---"
sudo grep -c "aicore exception" $R/ascend-plog/log/debug/plog/*.log 2>/dev/null
echo "--- watchdog errInfo ---"
sudo grep -h "SetWatchDogDevStatus" $R/ascend-plog/log/run/plog/*.log 2>/dev/null

echo
echo "########## 3. tar 包内容 ##########"
sudo tar tzf $R.tar.gz

echo
echo "########## 4. 包信息 ##########"
sudo ls -la $R.tar.gz
echo "解包后位置: $R"
echo "报修单: $R/昇腾300I-Duo故障报修单.md"
