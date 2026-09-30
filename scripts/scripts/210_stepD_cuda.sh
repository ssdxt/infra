#!/bin/bash
echo '== driver verify =='
nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>&1 | head -2
echo '== install CUDA 11.8 toolkit (driver skipped) =='
cd /ManualAI/driver
bash cuda_11.8.0_520.61.05_linux.run --toolkit --silent --no-opengl-libs > /tmp/cuda118.log 2>&1
echo "EXIT=$?"
tail -6 /tmp/cuda118.log
echo '== cudnn 8.7 install =='
cd /ManualAI/driver
tar -xf cudnn-linux-x86_64-8.7.0.84_cuda11-archive.tar.xz -C /usr/local/ && echo 'extracted'
cp -P /usr/local/cudnn-linux-x86_64-8.7.0.84_cuda11-archive/lib/libcudnn* /usr/local/cuda-11.8/lib64/ && echo 'libs copied'
cp /usr/local/cudnn-linux-x86_64-8.7.0.84_cuda11-archive/include/cudnn*.h /usr/local/cuda-11.8/include/ && echo 'headers copied'
echo '== verify toolkit =='
/usr/local/cuda-11.8/bin/nvcc --version 2>&1 | tail -2
echo "cudnn libs in cuda-11.8: $(ls /usr/local/cuda-11.8/lib64/ | grep -c libcudnn)"
ls -la /usr/local/cuda 2>/dev/null | head -2
echo '== ldconfig =='
ldconfig
