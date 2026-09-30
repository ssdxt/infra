#!/bin/bash

# 构建 Docker 镜像
docker build -t mineru:v2.6.7-vllm_openai_v0.10.2 -f Dockerfile .
