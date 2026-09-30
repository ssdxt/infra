#!/bin/bash
echo "== host libcuda ldd deps =="
ldd /usr/lib/aarch64-linux-gnu/nvidia/libcuda.so.1.1 2>/dev/null | grep -iE 'not found|tegra|=>' | head -15
echo "== mineru.json (mount) =="
cat /ManualAI/llm/mineru/mineru.json 2>/dev/null | head -40
echo "== model size in container =="
docker exec mineru-api du -sh /root/.cache/modelscope/models/OpenDataLab--MinerU2.5-2509-1.2B 2>/dev/null
docker exec mineru-api sh -c 'du -sh /root/.cache/modelscope/models/* 2>/dev/null | head'
echo "== host tegra dir? =="
ls /usr/lib/aarch64-linux-gnu/tegra/ 2>/dev/null | head -5
