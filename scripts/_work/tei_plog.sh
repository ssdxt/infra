#!/bin/bash
C=bge-m3-npu

echo "########## plog 文件列表 ##########"
sudo docker exec $C bash -c 'ls -la /root/ascend/log/run/plog/ /root/ascend/log/run/device-0/ /root/ascend/log/debug/plog/ 2>&1' | head -25

echo
echo "########## device-0 日志里的错误 ##########"
sudo docker exec $C bash -c 'grep -iE "error|exception|aicore|failed|timeout|abort" /root/ascend/log/run/device-0/*.log 2>/dev/null | tail -25'

echo
echo "########## plog 里的 ERROR ##########"
sudo docker exec $C bash -c 'grep -iE "\[ERROR\]|\[EVENT\]" /root/ascend/log/run/plog/*.log 2>/dev/null | tail -30'

echo
echo "########## nputools 日志 ##########"
sudo docker exec $C bash -c 'tail -25 /var/log/nputools_LOG_INFO.log 2>&1'

echo
echo "########## 最后一次 plog 的尾部 ##########"
sudo docker exec $C bash -c 'tail -30 /root/ascend/log/run/plog/plog-173_20260913225957574.log 2>&1'
