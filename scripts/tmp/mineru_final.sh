#!/bin/bash
echo "== wait qwen-27b ready =="
for i in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:8020/health 2>/dev/null)
  if [ "$code" = "200" ]; then echo "27B READY (${i}x10s)"; break; fi
  sleep 10
done
echo "== recreate mineru-api (固化镜像) =="
cd /ManualAI/llm/mineru && docker compose --profile api up -d --force-recreate mineru-api 2>&1 | tail -2
sleep 12
echo "== free mem =="
free -g | head -2
echo "== GPU usage =="
nvidia-smi --query-compute-apps=pid,used_memory --format=csv 2>/dev/null | tail -8
echo "== run GPU parse test =="
bash /tmp/mineru_gpu_test2.sh
