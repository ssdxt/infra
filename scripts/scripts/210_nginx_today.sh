#!/bin/bash
LOG=/ManualAI/OmniKnow/data/nginx/logs/_space_2026-09-03.log
echo '== 今天访问日志最后 30 条 =='
tail -30 "$LOG" 2>/dev/null | awk '{print $1, $4, $5, $6, $7, $9}' | sed 's|/api/v1/spaces/[0-9a-f-]*|/spaces/{s}|g; s|/kbs/[0-9a-f-]*|/kbs/{kb}|g'
echo
echo '== 含 upload / POST 非200 的请求 =='
grep -E 'docs/upload|images/upload|logos/upload|"POST' "$LOG" 2>/dev/null | tail -15 | awk '{print $4, $6, $7, $9}'
echo
echo '== 5xx/4xx 统计 =='
grep -oE '" (4[0-9]{2}|5[0-9]{2}) ' "$LOG" 2>/dev/null | sort | uniq -c
