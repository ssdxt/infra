#!/bin/sh
echo "=== df /data1 ==="
df -h /data1
echo "=== container cmd ==="
docker inspect wxq-prometheus --format '{{json .Args}}' 2>/dev/null || docker inspect wxq-prometheus --format '{{json .Config.Cmd}}'
echo "=== started at ==="
docker inspect wxq-prometheus --format '{{.State.StartedAt}}'
echo "=== logs tail (errors) ==="
docker logs wxq-prometheus --tail 300 2>&1 | grep -iE 'out of order|error|storage|replay|full' | tail -20
echo "=== head max time (query) ==="
docker exec wxq-prometheus sh -c "wget -qO- 'http://localhost:9090/api/v1/query?query=prometheus_tsdb_head_max_time_seconds' 2>/dev/null" || curl -s 'http://localhost:9090/api/v1/query?query=prometheus_tsdb_head_max_time_seconds'
echo
date -u +%s
