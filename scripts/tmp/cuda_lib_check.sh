#!/bin/bash
echo "=== HOST LIBCUDA ==="
ls -l /usr/lib/aarch64-linux-gnu/libcuda* /usr/local/cuda/lib64/libcuda* 2>/dev/null | head -6
echo "=== CTR LIBCUDA ==="
docker exec mineru-api ls -l /usr/lib/aarch64-linux-gnu/libcuda* /usr/local/cuda/lib64/libcuda* 2>/dev/null | head -6
echo "=== CTR nvidia/cuda libs ==="
docker exec mineru-api sh -c 'ls /usr/lib/aarch64-linux-gnu/ | grep -iE "nvidia|cuda"' | head -20
echo "=== HOST nvidia libs ==="
ls /usr/lib/aarch64-linux-gnu/ | grep -iE "libnvidia|libcuda" | head -20
