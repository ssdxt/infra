#!/usr/bin/bash

source /root/anaconda3/bin/activate glm4
#source activate glm4
cd /deploy/code/chat_doc_0520/llm_server
CUDA_VISIBLE_DEVICES=0 python test_chatglm4_trans_fp16.py
