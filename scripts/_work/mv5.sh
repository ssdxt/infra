#!/bin/bash
Y=/deploy/infra/milvus/data/milvus/milvus.yaml

echo "########## A. localStorage 段（第 85-100 行）##########"
sudo sed -n '80,100p' $Y

echo
echo "########## B. storageType 上下文（第 935-975 行）##########"
sudo sed -n '935,975p' $Y

echo
echo "########## C. woodpecker 的 storage 配置 ##########"
sudo sed -n '/^woodpecker:/,/^[a-z][a-z]*:/p' $Y | grep -nE "storage|type:|rootPath|path:|bucket|address" | head -30

echo
echo "########## D. woodpecker 段行号范围 ##########"
sudo grep -n "^woodpecker:\|^common:\|^storage:\|^localStorage:\|storageType" $Y

echo
echo "########## E. woodpecker storage 完整 ##########"
sudo sed -n '/^  storage:/,/^  [a-z]/p' $Y | head -40
