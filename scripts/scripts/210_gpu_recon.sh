#!/bin/bash
echo '== host /dev/nvidia* =='
ls -la /dev/nvidia* 2>&1
echo '== host nvidia modules =='
lsmod | grep -E '^nvidia' || echo 'no nvidia modules loaded'
echo '== host libcuda/libnvidia-ml =='
ldconfig -p | grep -E 'libcuda\.so|libnvidia-ml\.so' | head -8
echo '== cdi yaml names/devices =='
grep -nE 'name:|uvm|modeset|nvidiactl' /etc/cdi/nvidia.yaml | head -40
echo '== nvidia-ctk cdi generate help =='
nvidia-ctk cdi generate --help 2>&1 | head -45
