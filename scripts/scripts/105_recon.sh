#!/bin/bash
echo '== 本机也搜不到的话这里忽略；105 各目录体积 =='
du -sh /ManualAI/* 2>/dev/null | sort -h
echo '== 顶层目录内容概览 =='
for d in depends_on driver images llm MetaManual Omniknow system_info tools; do
  echo "--- /ManualAI/$d ---"
  ls /ManualAI/$d 2>/dev/null | head -12
done
echo '== llm 下各服务 compose/修改点 =='
find /ManualAI/llm -maxdepth 3 \( -name 'docker-compose*.y*ml' -o -name '*.patch' -o -name 'chat_utils.py' -o -name 'asr_server.py' -o -name 'tts_server.py' \) 2>/dev/null | head -20
echo '== Omniknow 是否含关键 conf/env =='
ls /ManualAI/Omniknow 2>/dev/null | head -10
