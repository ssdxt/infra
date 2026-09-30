#!/bin/bash
IMG=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64

echo "=== 1 /etc/ascend-docker-runtime.d ==="
ls -la /etc/ascend-docker-runtime.d/ 2>&1
for f in /etc/ascend-docker-runtime.d/*; do [ -f "$f" ] && { echo "--- $f ---"; cat "$f"; }; done

echo
echo "=== 2 /etc/Ascend + ascend_driver.conf + hdcBasic.cfg ==="
ls -la /etc/Ascend/ 2>&1
echo "--- ascend_driver.conf ---"; cat /etc/ascend_driver.conf 2>&1
echo "--- hdcBasic.cfg ---"; cat /etc/hdcBasic.cfg 2>&1
echo "--- ascend_install.info ---"; cat /etc/ascend_install.info 2>&1

echo
echo "=== 3 ascend docker runtime logs ==="
find /var/log -iname "*ascend*" -o -iname "*docker*runtime*" 2>/dev/null | head -10
journalctl -u docker --since "-40 min" 2>/dev/null | grep -iE "ascend|hook" | tail -10

echo
echo "=== 4 does the container actually use the ascend runtime? ==="
docker rm -f rtcheck 2>/dev/null
docker run -d --name rtcheck -e ASCEND_VISIBLE_DEVICES=0,1 --entrypoint /bin/bash $IMG -c 'sleep 120' >/dev/null 2>&1
sleep 3
echo -n "  runtime = "; docker inspect -f '{{.HostConfig.Runtime}}' rtcheck 2>&1
echo -n "  has davinci devices? "; docker exec rtcheck sh -c 'ls /dev | grep -c davinci' 2>&1
echo -n "  ASCEND env inside: "; docker exec rtcheck sh -c 'env | grep -i ascend | tr "\n" " "' 2>&1; echo
echo "  mounts:"; docker inspect -f '{{range .Mounts}}    {{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' rtcheck 2>&1
docker rm -f rtcheck >/dev/null 2>&1

echo
echo "=== 5 same, with explicit --runtime=ascend and ASCEND_RUNTIME_OPTIONS ==="
docker rm -f rtcheck2 2>/dev/null
docker run -d --name rtcheck2 --runtime=ascend -e ASCEND_VISIBLE_DEVICES=0,1 -e ASCEND_RUNTIME_OPTIONS=ASCEND_NPU -v /usr/local/Ascend/driver/lib64:/usr/local/Ascend/driver/lib64 -v /usr/local/dcmi:/usr/local/dcmi --entrypoint /bin/bash $IMG -c 'sleep 120' >/dev/null 2>&1
sleep 3
echo -n "  runtime = "; docker inspect -f '{{.HostConfig.Runtime}}' rtcheck2 2>&1
echo -n "  has davinci devices? "; docker exec rtcheck2 sh -c 'ls /dev | grep -c davinci' 2>&1
docker exec rtcheck2 sh -c 'export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64:/usr/local/dcmi; /usr/local/bin/npu-smi info 2>&1 | head -4' 2>&1 | sed 's/^/    /'
docker rm -f rtcheck2 >/dev/null 2>&1

echo
echo "=== 6 ascend-docker-cli / plugin-install-helper ==="
/usr/local/Ascend/Ascend-Docker-Runtime/ascend-docker-cli 2>&1 | head -12
/usr/local/Ascend/Ascend-Docker-Runtime/ascend-docker-plugin-install-helper 2>&1 | head -12

echo
echo "=== 7 /proc/self/cgroup inside container (ascend driver reads this) ==="
docker run --rm --entrypoint /bin/bash $IMG -c 'cat /proc/self/cgroup; echo "---"; cat /proc/1/cgroup' 2>&1
echo "host:"; cat /proc/self/cgroup

echo
echo "=== 8 host: does the exporter work when started as a plain host process? (re-confirm) ==="
ls -la /tmp/npu-exp-host 2>&1
/usr/local/sbin/npu-smi info 2>&1 | sed -n '1,10p'
