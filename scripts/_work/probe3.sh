#!/bin/bash
C=glm-4-9b-chat
SVC=/usr/local/Ascend/mindie/latest/mindie-service

sudo docker exec -i $C bash -s <<'EOF'
SVC=/usr/local/Ascend/mindie/latest/mindie-service
echo "=== processes ==="
ps -ef | head -20
echo
echo "=== recent .log files touched in last 15 min ==="
find / -xdev -name "*.log" -newermt "-15 minutes" 2>/dev/null | head -40
echo
echo "=== /logs exists? ==="
ls -la /logs 2>&1
echo
echo "=== SVC/logs ==="
ls -la $SVC/logs 2>&1
echo
echo "=== SVC security tree (depth 3) ==="
find $SVC/security -maxdepth 3 2>&1 | head -40
echo
echo "=== plog dir ==="
ls -la /root/ascend/log/ 2>&1 | head
echo
echo "=== mindservice.log tail ==="
tail -60 $SVC/logs/mindservice.log 2>&1
echo
echo "=== pythonlog tail ==="
tail -40 /usr/local/Ascend/mindie/latest/mindie-llm/logs/pythonlog.log 2>&1
EOF
