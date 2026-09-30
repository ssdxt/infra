#!/bin/bash
echo "== torch cuda build =="
docker exec mineru-api python3 -c 'import torch; print("torch", torch.__version__, "cuda-build", torch.version.cuda, "hip", torch.version.hip)'
echo "== mineru version =="
docker exec mineru-api python3 -c 'import mineru; print(mineru.__version__)' 2>&1 | tail -1
echo "== mineru models location =="
docker exec mineru-api sh -c 'find / -maxdepth 6 -name "*.pdmodel" 2>/dev/null | head -5; du -sh /root/.mineru /root/.cache/huggingface 2>/dev/null'
echo "== container cuda toolkit =="
docker exec mineru-api sh -c 'ls /usr/local/ | grep -i cuda; nvcc --version 2>/dev/null | tail -2 || echo no-nvcc'
