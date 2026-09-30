#!/bin/bash
export no_proxy='10.100.10.0/24,harbor.wuxing.local,localhost,127.0.0.1'
export NO_PROXY='10.100.10.0/24,harbor.wuxing.local,localhost,127.0.0.1'
echo "== 测试 docker push 到 Harbor（用已有小镜像）"
docker tag prometheuscommunity/smartctl-exporter:v0.14.0 harbor.wuxing.local/monitoring/smartctl-test:v0.14.0 2>/dev/null || docker tag quay.io/prometheus/node-exporter:v1.9.1 harbor.wuxing.local/monitoring/node-exporter-test:v1.9.1
TESTIMG=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep harbor.wuxing.local/monitoring/ | head -1)
echo "testimg=$TESTIMG"
echo '<HARBOR_PASSWORD>' | docker login harbor.wuxing.local -u admin --password-stdin 2>&1 | tail -1
docker push "$TESTIMG" 2>&1 | tail -3