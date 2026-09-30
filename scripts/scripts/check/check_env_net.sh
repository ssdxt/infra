#!/bin/bash
echo "=== 7个目录 .env 检查 ==="
for d in /root/llm/docker_2/qwen3_30b_a3b_instruct_nvfp4 /root/llm/docker_2/qwen3_next_80b_a3b_instruct_nvfp4 /root/apps/docker/holarchatbi /root/apps/docker/holargwxz /root/apps/docker/holar2dhuman /root/apps/docker/holarmeetnotesai /opt/1panel/apps/local/windows-arm/windows-arm; do
  if [ -f "$d/.env" ]; then echo "ENV_OK  $d"; else echo "NO_ENV  $d"; fi
done
echo
echo "=== 全部 docker 网络 ==="
docker network ls
echo
echo "=== models_network 详情 ==="
docker network inspect models_network 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print('driver:',d[0]['Driver'],'subnet:',d[0]['IPAM']['Config'][0]['Subnet'],'gateway:',d[0]['IPAM']['Config'][0]['Gateway'])" 2>&1
echo "=== 1panel-network 详情 ==="
docker network inspect 1panel-network 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print('driver:',d[0]['Driver'],'subnet:',d[0]['IPAM']['Config'][0]['Subnet'],'gateway:',d[0]['IPAM']['Config'][0]['Gateway'])" 2>&1
echo
echo "=== 容器实际存在情况 (含停止) ==="
docker ps -a --format "{{.Names}}\t{{.Status}}" | grep -iE 'qwen3|holardataq|gwxz|holarmetaman2d|meetnotesai|windows-arm|sensevoice'
