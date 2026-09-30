#!/bin/bash
cd /data1/ssdxt/logging || exit 1
chmod +x logq.py

echo "########## 1. 各命名空间日志量（近 5 分钟）##########"
python3 logq.py -n

echo ""
echo "########## 2. 可用标签 ##########"
python3 logq.py -l

echo ""
echo "########## 3. 查 kube-system 的 error 日志 ##########"
python3 logq.py '{namespace="kube-system"} |= "error"' 3 1h

echo ""
echo "########## 4. 查 etcd 慢盘证据（近 7 天，换盘前的现场记录）##########"
python3 logq.py '{namespace="kube-system"} |= "slow fdatasync"' 3 168h

echo ""
echo "########## 5. 统计：哪个 Pod 报错最多 ##########"
python3 logq.py -s 'sum by (pod) (count_over_time({namespace="kube-system"} |= "error" [5m]))' 1h
