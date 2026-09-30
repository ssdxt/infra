#!/bin/bash
LOG=$(ls -t /ManualAI/OmniKnow/data/nginx/logs/*.log 2>/dev/null | head -1)
echo "LOG=$LOG"
echo "== image GET status distribution =="
grep -oE 'GET [^ ]*\.(png|jpg|jpeg|webp)[^ ]* HTTP[^ ]*" [0-9]+' "$LOG" 2>/dev/null | tail -60 | grep -oE '[0-9]{3}$' | sort | uniq -c | sort -rn | head
echo "== recent image request lines =="
grep -E 'GET [^ ]*\.(png|jpg|jpeg|webp)' "$LOG" 2>/dev/null | tail -5
echo "== find space id from api logs =="
grep -oE '/api/v1/spaces/[0-9a-f]{8}-[0-9a-f-]{27}' "$LOG" 2>/dev/null | head -3
