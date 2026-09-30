#!/bin/bash
# 启动图片服务

source ~/.bashrc

cd /parserspace/rag

conda activate parser

python /parserspace/rag/img_service.py 2>&1 | tee -a /parserspace/logs/img_service.log
