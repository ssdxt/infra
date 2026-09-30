#!/bin/bash
echo "########## 1. ECC 错误统计 chip0 ##########"
sudo npu-smi info -t ecc -i 24 -c 0 2>&1 | head -30
echo
echo "########## 2. ECC 错误统计 chip1 ##########"
sudo npu-smi info -t ecc -i 24 -c 1 2>&1 | head -30

echo
echo "########## 3. 错误计数 ##########"
sudo npu-smi info -t err-count -i 24 -c 0 2>&1 | head -20
echo "--- chip1 ---"
sudo npu-smi info -t err-count -i 24 -c 1 2>&1 | head -20

echo
echo "########## 4. 显存信息 ##########"
sudo npu-smi info -t memory -i 24 -c 0 2>&1 | head -15
echo "--- chip1 ---"
sudo npu-smi info -t memory -i 24 -c 1 2>&1 | head -15

echo
echo "########## 5. 内存 ##########"
free -h
echo "CPU: $(nproc) 核"

echo
echo "########## 6. 首次上电日期 ##########"
sudo npu-smi info -t first-power-on-date -i 24 2>&1 | head -8

echo
echo "########## 7. PCIe 错误 ##########"
sudo npu-smi info -t pcie-err -i 24 -c 0 2>&1 | head -15
