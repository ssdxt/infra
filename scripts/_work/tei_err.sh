#!/bin/bash
C=bge-m3-npu

echo "########## 1. errInfo / 硬件错误详情 ##########"
sudo docker exec $C bash -c 'grep -rniE "errInfo|error_code|errorcode|devStatus|dev_status|fault|0x26|507015|aicore exception|ecc" /root/ascend/log/ 2>/dev/null | grep -viE "no error|errInfo is empty|error_code=0," | tail -30'

echo
echo "########## 2. 23:00:36 前后的完整日志 ##########"
sudo docker exec $C bash -c 'grep -nE "23:00:3[0-9]|23:00:4[0-9]|23:00:5[0-9]" /root/ascend/log/run/plog/*.log 2>/dev/null | tail -40'

echo
echo "########## 3. debug plog 里的 WARNING/ERROR ##########"
sudo docker exec $C bash -c 'grep -iE "\[WARNING\]|\[ERROR\]|\[EVENT\]" /root/ascend/log/debug/plog/*.log 2>/dev/null | grep -viE "PROFILING" | tail -30'

echo
echo "########## 4. device 日志全文 ##########"
sudo docker exec $C bash -c 'cat /root/ascend/log/run/device-0/*.log 2>/dev/null | tail -30'

echo
echo "########## 5. ascend 日志里所有含 devId 的行 ##########"
sudo docker exec $C bash -c 'grep -rniE "devId=|devId " /root/ascend/log/ 2>/dev/null | tail -20'
