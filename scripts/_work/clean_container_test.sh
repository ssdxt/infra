#!/bin/bash
IMG=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64

echo "=== 1: free DCMI completely ==="
systemctl stop npu-exporter
docker rm -f npu-exporter tmpget 2>/dev/null
sleep 3
echo -n "  host DCMI free? "; npu-smi info 2>&1 | sed -n '5,6p' | tr -d '\n'; echo
echo -n "  any npu-exporter process left? "; (pgrep -a npu-exporter || echo none)

echo
echo "=== 2: start container with the OFFICIAL hook pattern (clean environment) ==="
docker run -d --name npu-exporter \
  --restart=unless-stopped \
  --runtime=ascend \
  -e ASCEND_VISIBLE_DEVICES=0,1 \
  -p 8082:8082 -p 11256:11256 \
  -v /var/log/mindx-dl:/var/log/mindx-dl \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --entrypoint /bin/bash \
  $IMG -c 'mkdir -p /var/log/mindx-dl/npu-exporter; exec /usr/local/bin/npu-exporter -port=8082 -ip=0.0.0.0 -logFile=/var/log/mindx-dl/npu-exporter/npu-exporter.log -logLevel=0 -containerMode=docker -endpoint=/run/dockershim.sock -containerd=/run/docker/containerd/containerd.sock --enable-healthz=true --healthz-address=11256' >/dev/null 2>&1

echo "  waiting 30s..."
sleep 30
docker ps --filter name=npu-exporter --format '  {{.Names}} | {{.Status}}'
echo "  --- logs ---"
docker logs --tail 18 npu-exporter 2>&1 | sed 's/^/    /'
echo "  --- metrics ---"
curl -s -m 10 -o /tmp/ct.txt -w "    http_code=%{http_code}\n" http://127.0.0.1:8082/metrics
echo "    npu_ lines: $(grep -c '^npu_' /tmp/ct.txt 2>/dev/null)"
grep -E '^npu_chip_info_(name|health_status|power|temperature)' /tmp/ct.txt 2>/dev/null | head -4 | sed 's/^/      /'

OK=$(grep -c '^npu_' /tmp/ct.txt 2>/dev/null)
echo
if [ "${OK:-0}" -gt 0 ]; then
  echo "########## CONTAINER PATH WORKS (%s metrics) ##########" 
  echo "  keeping the container, host service stays stopped+disabled"
  systemctl disable npu-exporter >/dev/null 2>&1
  systemctl stop npu-exporter >/dev/null 2>&1
else
  echo "########## CONTAINER PATH STILL FAILS ##########"
  echo "  removing container, restoring the host service"
  docker rm -f npu-exporter >/dev/null 2>&1
  systemctl enable npu-exporter >/dev/null 2>&1
  systemctl start npu-exporter
  sleep 18
fi

echo
echo "=== 3: final state ==="
echo -n "  npu-exporter service: "; systemctl is-active npu-exporter 2>&1
docker ps --filter name=npu-exporter --format '  container npu-exporter: {{.Status}}'
docker ps --filter name=node-exporter --format '  container node-exporter: {{.Status}}'
echo -n "  8082 http_code: "; curl -s -m 10 -o /tmp/f.txt -w "%{http_code}\n" http://127.0.0.1:8082/metrics
echo "  npu_ lines: $(grep -c '^npu_' /tmp/f.txt 2>/dev/null)"
echo -n "  9100 http_code: "; curl -s -m 8 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:9100/metrics
ss -lntp 2>/dev/null | grep -E ':(8082|11256|9100)' | sed 's/^/  /'
