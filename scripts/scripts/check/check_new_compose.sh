#!/bin/bash
echo "=== 新发现的7个compose目录状态 ==="
for d in \
  /root/llm/docker_2/qwen3_30b_a3b_instruct_nvfp4 \
  /root/llm/docker_2/qwen3_next_80b_a3b_instruct_nvfp4 \
  /root/apps/docker/holarchatbi \
  /root/apps/docker/holargwxz \
  /root/apps/docker/holar2dhuman \
  /root/apps/docker/holarmeetnotesai \
  /opt/1panel/apps/local/windows-arm/windows-arm ; do
  if [ -f "$d/docker-compose.yml" ]; then
    echo "###### 存在: $d ($(wc -l < "$d/docker-compose.yml") 行)"
  else
    echo "###### 不存在: $d"
  fi
done
echo
echo "=== 这些项目对应的容器状态 (docker ps -a) ==="
docker ps -a --format "{{.Names}}\t{{.Status}}\t{{.Image}}" | grep -iE 'qwen|holarchatbi|holargwxz|holar2dhuman|holarmeetnotesai|windows-arm|qwen3' 
echo
echo "=== 逐个输出 yaml 内容 ==="
for d in \
  /root/llm/docker_2/qwen3_30b_a3b_instruct_nvfp4 \
  /root/llm/docker_2/qwen3_next_80b_a3b_instruct_nvfp4 \
  /root/apps/docker/holarchatbi \
  /root/apps/docker/holargwxz \
  /root/apps/docker/holar2dhuman \
  /root/apps/docker/holarmeetnotesai \
  /opt/1panel/apps/local/windows-arm/windows-arm ; do
  f="$d/docker-compose.yml"
  if [ -f "$f" ]; then
    echo "###### FILE: $f"
    cat "$f"
    echo
  fi
done
