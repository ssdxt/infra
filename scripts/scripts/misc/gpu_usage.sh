#!/bin/bash
echo "=== nvidia-smi 进程占用 ==="
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null
echo
echo "=== 按 PID 对应容器 ==="
for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null); do
  cname=$(docker ps --format '{{.Names}}' | while read c; do
    if docker top "$c" -o pid,comm 2>/dev/null | grep -qE "^\s*$pid\s"; then echo "$c"; break; fi
  done)
  mem=$(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null | grep "^$pid," | cut -d, -f2)
  cmd=$(ps -o comm= -p $pid 2>/dev/null | head -1)
  printf "PID %-8s 内存 %-12s 容器: %-28s 进程: %s\n" "$pid" "$mem" "${cname:-宿主机/未知}" "$cmd"
done
echo
echo "=== 总览 ==="
nvidia-smi 2>/dev/null | grep -E 'MiB|NVIDIA-SMI' | head -8
