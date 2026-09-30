#!/bin/bash
# 105 重新部署前：彻底停掉全部运行容器（down = 移容器，保留卷/镜像/配置文件）
set +e
echo "== [1/5] aippt (/data/aippt) =="
cd /data/aippt && docker compose down 2>&1 | tail -3
echo "== [2/5] sherpa docker (/root/sherpa/docker) =="
cd /root/sherpa/docker && docker compose down 2>&1 | tail -3
echo "== [3/5] asr_work docker (/root/asr_work/docker) =="
cd /root/asr_work/docker && docker compose down 2>&1 | tail -3
echo "== [4/5] embed (/root/embed) =="
cd /root/embed && docker compose -f docker-compose-embed.yml down 2>&1 | tail -3
echo "== [5/5] mineru_2509_1.2b (/root/llm/docker_2/mineru_2509_1.2b) =="
cd /root/llm/docker_2/mineru_2509_1.2b && docker compose down 2>&1 | tail -3
echo "== 残留运行容器检查 =="
docker ps --format '{{.Names}} | {{.Status}}'
echo "== 全部容器(含停止)计数 =="
docker ps -a --format '{{.Names}}' | wc -l
echo "== DONE =="
