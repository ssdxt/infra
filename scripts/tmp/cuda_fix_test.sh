#!/bin/bash
echo "=== HOST nvidia dir ==="
ls /usr/lib/aarch64-linux-gnu/nvidia/ 2>/dev/null | head -20
echo "=== CTR nvidia dir ==="
docker exec mineru-api ls /usr/lib/aarch64-linux-gnu/nvidia/ 2>/dev/null | head -20
echo "=== TEST: bind host libcuda + torch ==="
docker run --rm \
  -v /usr/lib/aarch64-linux-gnu/nvidia/libcuda.so:/usr/lib/aarch64-linux-gnu/nvidia/libcuda.so:ro \
  mineru-gpu-dustynv:v2.7.6-arm64-transformers \
  python3 -c 'import torch; print("cuda", torch.cuda.is_available(), "dev", torch.cuda.device_count())' 2>&1 | tail -3
