#!/bin/bash

export PATH=/root/anaconda3/envs/parser/bin:$PATH

cd /parserspace/rag

python /parserspace/rag/img_service.py \
  2>&1 | tee -a /parserspace/logs/img_service.log
