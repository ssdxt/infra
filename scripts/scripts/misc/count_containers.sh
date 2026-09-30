#!/bin/bash
echo "当前运行中容器数: $(docker ps -q | wc -l)"
echo "当前总容器数(含停止): $(docker ps -aq | wc -l)"
echo
echo "=== 当前全部容器 ==="
docker ps -a --format '{{.Names}} | {{.Status}}' | sort
