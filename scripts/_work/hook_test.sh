#!/bin/bash
IMG=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64
CMD='npu-smi info 2>&1 | sed -n "1,10p"'
CMD2='export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64:/usr/local/dcmi; npu-smi info 2>&1 | sed -n "1,10p"'

echo "=== A: ascend runtime + ASCEND_VISIBLE_DEVICES only, no manual mounts ==="
docker run --rm --runtime=ascend -e ASCEND_VISIBLE_DEVICES=0,1 --entrypoint /bin/bash $IMG -c "$CMD" 2>&1 | sed 's/^/  /'

echo
echo "=== B: same, with explicit LD_LIBRARY_PATH ==="
docker run --rm --runtime=ascend -e ASCEND_VISIBLE_DEVICES=0,1 --entrypoint /bin/bash $IMG -c "$CMD2" 2>&1 | sed 's/^/  /'

echo
echo "=== C: what did the hook mount into /dev and where are the libs ==="
docker run --rm --runtime=ascend -e ASCEND_VISIBLE_DEVICES=0,1 --entrypoint /bin/bash $IMG -c '
  echo "--- /dev ---"; ls /dev | grep -iE "davinci|devmm|hisi"
  echo "--- /usr/local/Ascend/driver ---"; ls /usr/local/Ascend/driver 2>&1 | head
  echo "--- /usr/local/Ascend/driver/lib64 ---"; ls /usr/local/Ascend/driver/lib64 2>&1 | head
  echo "--- /usr/local/dcmi ---"; ls /usr/local/dcmi 2>&1
  echo "--- /usr/local/bin/npu-smi ---"; ls -la /usr/local/bin/npu-smi 2>&1
  echo "--- /var/queue_schedule ---"; ls -la /var/queue_schedule 2>&1
  echo "--- mount points ---"; mount | grep -iE "ascend|dcmi|davinci"
' 2>&1 | sed 's/^/  /'

echo
echo "=== D: start npu-exporter with the hook pattern ==="
docker rm -f npu-exporter 2>/dev/null
docker run -d --name npu-exporter \
  --restart=unless-stopped \
  --runtime=ascend \
  -e ASCEND_VISIBLE_DEVICES=0,1 \
  -p 8082:8082 -p 11256:11256 \
  -v /var/log/mindx-dl:/var/log/mindx-dl \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --entrypoint /bin/bash \
  $IMG -c 'mkdir -p /var/log/mindx-dl/npu-exporter; exec /usr/local/bin/npu-exporter -port=8082 -ip=0.0.0.0 -logFile=/var/log/mindx-dl/npu-exporter/npu-exporter.log -logLevel=0 -containerMode=docker -endpoint=/run/dockershim.sock -containerd=/run/docker/containerd/containerd.sock --enable-healthz=true --healthz-address=11256' 2>&1 | tail -3

echo "--- wait 20s ---"
sleep 20
docker ps --filter name=npu-exporter --format '  {{.Names}} | {{.Status}} | {{.Ports}}'
echo "--- logs ---"
docker logs --tail 20 npu-exporter 2>&1 | sed 's/^/  /'
echo "--- metrics ---"
curl -s -m 10 -o /tmp/npu2.txt -w "  http_code=%{http_code}\n" http://127.0.0.1:8082/metrics
echo "  npu_ lines: $(grep -c '^npu_' /tmp/npu2.txt 2>/dev/null)"
grep -E '^npu_chip_info_(name|health_status|temperature|power|hbm_used_memory)' /tmp/npu2.txt 2>/dev/null | head -8 | sed 's/^/    /'

echo
echo "=== E: node-exporter still up? ==="
docker ps --filter name=node-exporter --format '  {{.Names}} | {{.Status}}'
curl -s -m 8 -o /dev/null -w "  node 9100 http_code=%{http_code}\n" http://127.0.0.1:9100/metrics
