#!/bin/bash
echo "=== manualai_network 当前子网 ==="
docker network inspect manualai_network --format '子网={{range .IPAM.Config}}{{.Subnet}} 网关={{.Gateway}}{{end}}' 2>/dev/null || echo "manualai_network 不存在!"
echo
echo "=== 1panel-network 是否还在 ==="
docker network ls | grep -E '1panel|manualai'
echo
echo "=== 三个 qwen 容器当前状态 ==="
docker ps -a --format "{{.Names}} | {{.Status}}" | grep -E 'qwen'
echo
echo "=== 三个 qwen 的 IP 是否在子网内 ==="
for c in qwen-nvidia-vllm qwen-embedding qwen-rerank; do
  ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "$c" 2>/dev/null)
  echo "$c -> $ip"
done
echo
echo "=== 105 上可用的 Thor 版 vllm 镜像 ==="
docker images | grep -iE 'vllm|thor' | head -10
echo
echo "=== GPU 现状 ==="
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null
