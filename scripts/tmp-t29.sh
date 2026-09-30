#!/bin/bash
echo "=== /var/log/pods present? ==="
ls -d /var/log/pods 2>&1
echo "=== sample entries ==="
ls /var/log/pods | head -5
echo "=== full layout for 2 pods ==="
for d in $(ls -d /var/log/pods/*_* 2>/dev/null | head -2); do
  echo "  dir: $d"
  ls "$d" 2>&1 | head -3
  c=$(ls "$d" 2>/dev/null | head -1)
  ls "$d/$c" 2>&1 | head -3
done
echo "=== glob match count /var/log/pods/*/*/*.log ==="
ls /var/log/pods/*/*/*.log 2>/dev/null | wc -l
echo "=== first 3 matching paths ==="
ls /var/log/pods/*/*/*.log 2>/dev/null | head -3
echo "=== readable? ==="
head -c 100 "$(ls /var/log/pods/*/*/*.log 2>/dev/null | head -1)" 2>&1 | head -c 150
echo ""
echo "=== node hostname ==="
hostname