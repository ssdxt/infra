#!/usr/bin/env bash
set -e

export PATH=/root/anaconda3/envs/parser/bin:$PATH

cd /parserspace/rag

#conda activate parser
source /root/anaconda3/bin/activate parser

python /parserspace/rag/api.py \
  2>&1 | tee -a /parserspace/logs/parser.log
