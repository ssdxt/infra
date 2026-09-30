#!/bin/bash
# 启动 RAG API 服务

source ~/.bashrc

cd /parserspace/rag

conda activate parser

python /parserspace/rag/api.py 2>&1 | tee -a /parserspace/logs/api.log
