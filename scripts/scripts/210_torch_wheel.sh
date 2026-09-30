#!/bin/bash
echo '== aliyun cu118 torch page sample =='
curl -s --max-time 25 "https://mirrors.aliyun.com/pytorch-wheels/cu118/torch/" | grep -oE 'torch-2\.4\.1[^"]*\.whl' | head -6
echo '== HEAD cp312 wheel =='
curl -sI --max-time 15 "https://mirrors.aliyun.com/pytorch-wheels/cu118/torch/torch-2.4.1%2Bcu118-cp312-cp312-linux_x86_64.whl" | head -1
echo '== HEAD cp311 wheel =='
curl -sI --max-time 15 "https://mirrors.aliyun.com/pytorch-wheels/cu118/torch/torch-2.4.1%2Bcu118-cp311-cp311-linux_x86_64.whl" | head -1
echo '== HEAD torch 2.2.2 cp312 =='
curl -sI --max-time 15 "https://mirrors.aliyun.com/pytorch-wheels/cu118/torch/torch-2.2.2%2Bcu118-cp312-cp312-linux_x86_64.whl" | head -1
