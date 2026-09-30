#!/bin/bash
echo '== parser.log 里 No route to host 上下文 =='
grep -aB12 -A6 'No route to host' /ManualAI/OmniKnow/logs/parser.log 2>/dev/null | sed -e 's/\x1b\[[0-9;]*m//g' | tail -30
echo
echo '== document_insert 相关最近记录 =='
grep -aE 'document_insert|ConnectError|milvus|MILVUS' /ManualAI/OmniKnow/logs/parser.log 2>/dev/null | sed -e 's/\x1b\[[0-9;]*m//g' | tail -10
