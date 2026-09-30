#!/bin/bash
IMG=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64
CMD='npu-smi info 2>&1 | sed -n "1,6p"'

echo "=== 0: which host files from the 200I Pro recipe exist here ==="
for f in /etc/hdcBasic.cfg /etc/sys_version.conf /etc/slog.conf /etc/ld.so.conf.d/mind_so.conf \
         /etc/ascend_driver.conf /etc/ascend_filelist.info /etc/Ascend/ascend_cann_install.info \
         /usr/lib64/libstackcore.so /usr/lib64/libmmpa.so /usr/lib64/libtensorflow.so \
         /usr/lib64/libyaml-0.so.2 /var/dmp_daemon /var/slogd /var/queue_schedule; do
  printf "  %-46s " "$f"; [ -e "$f" ] && echo "存在" || echo "-"
done

echo
echo "=== 1: last try - hook + these host config files ==="
docker run --rm --runtime=ascend -e ASCEND_VISIBLE_DEVICES=0,1 \
  -v /etc/hdcBasic.cfg:/etc/hdcBasic.cfg:ro \
  -v /etc/ascend_driver.conf:/etc/ascend_driver.conf:ro \
  -v /etc/ascend_filelist.info:/etc/ascend_filelist.info:ro \
  -v /etc/ascend_install.info:/etc/ascend_install.info:ro \
  -v /usr/local/Ascend/driver/device:/usr/local/Ascend/driver/device:ro \
  --entrypoint /bin/bash $IMG -c "$CMD" 2>&1 | sed 's/^/  /'

echo "=== 2: hook + device/version.info + tools ==="
docker run --rm --runtime=ascend -e ASCEND_VISIBLE_DEVICES=0,1 \
  -v /usr/local/Ascend/driver/version.info:/usr/local/Ascend/driver/version.info:ro \
  --entrypoint /bin/bash $IMG -c "$CMD" 2>&1 | sed 's/^/  /'

echo
echo "############ FALLBACK: run npu-exporter as a HOST systemd service ############"
echo "=== clean up any containers on 8082 ==="
docker rm -f npu-exporter 2>/dev/null
docker ps -a --filter name=npu-exporter --format '  left: {{.Names}} {{.Status}}'

echo "=== install binary extracted from the image ==="
mkdir -p /opt/npu-exporter /var/log/mindx-dl/npu-exporter
if [ ! -x /opt/npu-exporter/npu-exporter ]; then
  docker rm -f tmpget 2>/dev/null
  docker create --name tmpget --entrypoint /bin/true $IMG >/dev/null 2>&1
  docker cp tmpget:/usr/local/bin/npu-exporter /opt/npu-exporter/npu-exporter >/dev/null 2>&1
  docker rm -f tmpget >/dev/null 2>&1
fi
chmod 755 /opt/npu-exporter/npu-exporter
ls -la /opt/npu-exporter/npu-exporter
echo "  sha256: $(sha256sum /opt/npu-exporter/npu-exporter | cut -c1-32)..."

echo "=== write systemd unit ==="
cat > /etc/systemd/system/npu-exporter.service <<'UNIT'
[Unit]
Description=Ascend NPU Exporter (Prometheus)
Documentation=https://gitee.com/ascend/ascend-npu-exporter
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64:/usr/local/dcmi
ExecStartPre=/bin/mkdir -p /var/log/mindx-dl/npu-exporter
ExecStart=/opt/npu-exporter/npu-exporter -port=8082 -ip=0.0.0.0 -logFile=/var/log/mindx-dl/npu-exporter/npu-exporter.log -logLevel=0 -containerMode=docker -endpoint=/run/dockershim.sock -containerd=/run/docker/containerd/containerd.sock --enable-healthz=true --healthz-address=11256
Restart=always
RestartSec=10
KillMode=process

[Install]
WantedBy=multi-user.target
UNIT
echo "  unit written"

systemctl daemon-reload
systemctl enable npu-exporter >/dev/null 2>&1
systemctl restart npu-exporter
echo "  waiting 20s..."
sleep 20
systemctl status npu-exporter --no-pager 2>&1 | head -12 | sed 's/^/  /'

echo
echo "=== verify npu-exporter on host ==="
curl -s -m 10 -o /tmp/hnpu.txt -w "  http_code=%{http_code}\n" http://127.0.0.1:8082/metrics
echo "  npu_ metric lines: $(grep -c '^npu_' /tmp/hnpu.txt 2>/dev/null)"
grep -E '^npu_chip_info_(name|health_status|temperature|power)' /tmp/hnpu.txt 2>/dev/null | head -6 | sed 's/^/    /'
curl -s -m 5 -o /dev/null -w "  healthz http_code=%{http_code}\n" http://127.0.0.1:11256/healthz

echo
echo "=== final state ==="
systemctl is-enabled npu-exporter 2>&1 | sed 's/^/  npu-exporter enabled: /'
systemctl is-active npu-exporter 2>&1 | sed 's/^/  npu-exporter active: /'
docker ps --filter name=node-exporter --format '  node-exporter: {{.Status}}'
curl -s -m 8 -o /dev/null -w "  node 9100 http_code=%{http_code}\n" http://127.0.0.1:9100/metrics
ss -lntp 2>/dev/null | grep -E ':(8082|11256|9100)' | sed 's/^/  /'
