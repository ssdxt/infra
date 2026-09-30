#!/bin/bash
echo "=== aippt 全部容器状态 ==="
docker ps -a --filter name=aippt --format "{{.Names}}\t{{.Status}}\t{{.Image}}"
echo
echo "=== aippt-api 最近日志 (tail 40) ==="
docker logs aippt-api --tail 40 2>&1 | tail -40
echo
echo "=== aippt-nacos 日志 (tail 20) ==="
docker logs aippt-nacos --tail 20 2>&1 | tail -20
echo
echo "=== aippt-redis / minio 退出原因 ==="
docker inspect aippt-redis --format 'RestartPolicy={{.HostConfig.RestartPolicy.Name}} ExitCode={{.State.ExitCode}} Error={{.State.Error}}' 2>/dev/null
docker inspect aippt-minio --format 'RestartPolicy={{.HostConfig.RestartPolicy.Name}} ExitCode={{.State.ExitCode}} Error={{.State.Error}}' 2>/dev/null
docker inspect aippt-nacos --format 'RestartPolicy={{.HostConfig.RestartPolicy.Name}} ExitCode={{.State.ExitCode}} Error={{.State.Error}}' 2>/dev/null
