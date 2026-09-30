#!/bin/bash
echo '== mineru_parser.py URL/连接逻辑 =='
grep -nE 'MINERU|mineru|url|http|def __init__|getenv|environ|8000|8446' /ManualAI/OmniKnow/omniknow2/parser/rag/parser/mineru_parser.py 2>/dev/null | head -25
echo '== api.py 加载 env 方式 =='
grep -nE 'load_dotenv|dotenv|MINERU|getenv' /ManualAI/OmniKnow/omniknow2/parser/rag/api.py 2>/dev/null | head -10
echo '== parser 进程实际 env 中的 MINERU =='
docker exec parser sh -c 'grep -a "MINERU" /proc/1/environ 2>/dev/null | tr "\0" "\n"' 2>/dev/null
echo '== rag/.env mtime vs parser 启动时间 =='
stat -c '%y %n' /ManualAI/OmniKnow/omniknow2/parser/rag/.env 2>/dev/null
docker inspect parser --format 'started: {{.State.StartedAt}}' 2>/dev/null
