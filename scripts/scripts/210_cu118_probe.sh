#!/bin/bash
echo '== torch 2.4.1 cu118 cp312 wheel? =='
curl -s --max-time 25 "https://pypi.org/pypi/torch/2.4.1/json" | grep -oE 'torch-2\.4\.1[^"]*cp312[^"]*cu118[^"]*linux_x86_64\.whl' | head -3
echo '== torch 2.2.2 cu118 cp312? =='
curl -s --max-time 25 "https://pypi.org/pypi/torch/2.2.2/json" | grep -oE 'torch-2\.2\.2[^"]*cp312[^"]*cu118[^"]*linux_x86_64\.whl' | head -3
echo '== download.pytorch.org cu118 reachable =='
curl -sI --max-time 15 "https://download.pytorch.org/whl/cu118/torch/" 2>&1 | head -1
echo '== aliyun pytorch mirror reachable =='
curl -sI --max-time 15 "https://mirrors.aliyun.com/pytorch-wheels/cu118/" 2>&1 | head -1
echo '== cuda 11.8 runfile (520.61.05) reachable =='
curl -sI --max-time 15 "https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda_11.8.0_520.61.05_linux.run" 2>&1 | head -1
