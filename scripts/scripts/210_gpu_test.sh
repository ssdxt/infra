#!/bin/bash
echo '== test1: docker --gpus all =='
docker run --rm --gpus all redis:8.6.2 sh -c 'echo --- devices:; ls /dev/nvidia* 2>/dev/null; echo --- injected libs:; ldconfig -p | grep -iE "libcuda|libnvidia-ml" | head -6' 2>&1 | head -25
echo '== test2: docker --device nvidia.com/gpu=all =='
docker run --rm --device nvidia.com/gpu=all redis:8.6.2 sh -c 'ls /dev/nvidia* 2>/dev/null' 2>&1 | head -8
