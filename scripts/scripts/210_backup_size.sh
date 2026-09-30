#!/bin/bash
tar tvzf /tmp/backup210-20260903.tgz 2>/dev/null | awk '{print $3, $6}' | sort -rn | head -15 | awk '{printf "%.1f MB  %s\n", $1/1048576, $2}'
echo '== 各顶层目录体积 =='
tar tvzf /tmp/backup210-20260903.tgz 2>/dev/null | awk '{n=$6; sub(/\/.*/,"",n); s[n]+=$3} END{for(k in s) printf "%.1f MB  %s\n", s[k]/1048576, k}' | sort -rn
