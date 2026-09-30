#!/bin/bash
echo "=== qwen-nvidia-vllm 日志 (tail 20) ==="
docker logs qwen-nvidia-vllm --tail 20 2>&1 | tail -20
echo
echo "=== qwen-embedding 日志 (tail 15) ==="
docker logs qwen-embedding --tail 15 2>&1 | tail -15
echo
echo "=== qwen-rerank 日志 (tail 15) ==="
docker logs qwen-rerank --tail 15 2>&1 | tail -15
echo
echo "=== GPU 显存现状 ==="
nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null
nvidia-smi 2>/dev/null | grep -E 'MiB|%' | head -10
echo
echo "=== 三个 qwen 的 compose 配置 ==="
echo "--- /ManualAI/llm/qwen3.5/docker-compose.yaml ---"
cat /ManualAI/llm/qwen3.5/docker-compose.yaml 2>/dev/null | head -40
echo "--- /ManualAI/llm/base/docker-compose.yaml ---"
cat /ManualAI/llm/base/docker-compose.yaml 2>/dev/null | head -50
