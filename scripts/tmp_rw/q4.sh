#!/bin/sh
# look at accepted samples of the chronically-rejected series on plant01
S='node_namespace_pod_container:container_memory_rss{pod="cilium-envoy-79s8x",node="wxq-run-07",instance="10.100.10.46:10250"}'
curl -s --data-urlencode "query=$S" --data 'start=-30m' 'http://localhost:9091/api/v1/query_range?step=1m' -G | tr ',' '\n' | grep -o '"[0-9]\{13\}":"[0-9.e-]*"' | head -40
echo "=== head max time ==="
curl -s 'http://localhost:9091/api/v1/query?query=prometheus_tsdb_head_max_time_seconds/1000' | head -c 400
