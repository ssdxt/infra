#!/bin/bash
echo '== install CUDA 11.8 toolkit (no driver) =='
bash /ManualAI/driver/cuda_11.8.0_520.61.05_linux.run --toolkit --silent --no-opengl-libs > /tmp/cuda118.log 2>&1
echo "CUDA_EXIT=$?"
tail -6 /tmp/cuda118.log
echo '== verify toolkit =='
/usr/local/cuda-11.8/bin/nvcc --version 2>&1 | tail -2
echo '== extract cudnn =='
tar -xf /ManualAI/driver/cudnn-linux-x86_64-8.7.0.84_cuda11-archive.tar.xz -C /usr/local/ && echo 'extracted'
echo '== copy cudnn into cuda-11.8 =='
cp -P /usr/local/cudnn-linux-x86_64-8.7.0.84_cuda11-archive/lib/libcudnn* /usr/local/cuda-11.8/lib64/ && echo 'libs copied'
cp /usr/local/cudnn-linux-x86_64-8.7.0.84_cuda11-archive/include/cudnn*.h /usr/local/cuda-11.8/include/ && echo 'headers copied'
echo "cudnn libs count: $(ls /usr/local/cuda-11.8/lib64/ | grep -c libcudnn)"
echo '== cuda symlink =='
ls -la /usr/local/cuda 2>/dev/null | head -1
echo '== ldconfig =='
ldconfig
