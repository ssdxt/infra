#!/bin/bash
START=$(systemctl show chat_doc_api -p ActiveEnterTimestamp --value)
echo "服务启动于: $START"
echo

echo "########## 1. 日志总量统计 ##########"
TOT=$(journalctl -u chat_doc_api --since "$START" --no-pager -o cat 2>/dev/null | wc -l)
ERR=$(journalctl -u chat_doc_api --since "$START" --no-pager -o cat 2>/dev/null | grep -c "ERROR")
echo "  总行数: $TOT"
echo "  含 ERROR 的行: $ERR"

echo
echo "########## 2. ERROR 行按「来源标签」分类 ##########"
journalctl -u chat_doc_api --since "$START" --no-pager -o cat 2>/dev/null \
  | grep "ERROR" \
  | sed -E 's/^[0-9-]+ [0-9:.]+ \| ERROR \| [a-z]+ \| //' \
  | sed -E 's/^(.{0,60}).*/\1/' \
  | sort | uniq -c | sort -rn | head -25

echo
echo "########## 3. 真正的异常类型统计 ##########"
journalctl -u chat_doc_api --since "$START" --no-pager -o cat 2>/dev/null \
  | grep -oE "[A-Za-z_.]*(Error|Exception|Warning|error|failed|Failed|Refused|refused|timeout|Timeout)[A-Za-z_.]*" \
  | sort | uniq -c | sort -rn | head -25

echo
echo "########## 4. 完整 ERROR 日志（去掉 loguru 前缀，最多 80 行）##########"
journalctl -u chat_doc_api --since "$START" --no-pager -o cat 2>/dev/null \
  | grep "ERROR" \
  | sed -E 's/^[0-9-]+ [0-9:.]+ \| ERROR \| stderr \| //' \
  | tail -80
