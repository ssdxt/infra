#!/bin/bash
echo "=== /root/llm 下所有 compose 目录 ==="
ls -la /root/llm/docker_2/ 2>/dev/null
echo
echo "=== 所有 qwen/llm 容器状态 ==="
docker ps -a --format "{{.Names}} | {{.Status}} | {{.Image}}" | grep -iE 'qwen|vllm|mineru|sgl|llm' 
echo
echo "=== qwen3_30b 日志 (tail 15) ==="
docker logs qwen3_30b_a3b_instruct_nvfp4 --tail 15 2>&1 | tail -15
echo
echo "=== qwen3_next_80b 日志 (tail 15) ==="
docker logs qwen3_next_80b_a3b_instruct_nvfp4 --tail 15 2>&1 | tail -15
echo
echo "=== sgl_1.2b 日志 (tail 15) ==="
docker logs holarfileparse_sgl_1.2b --tail 15 2>&1 | tail -15
