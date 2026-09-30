#!/bin/bash
# 任务1 验证
echo "===== [1] 容器状态与启动参数 ====="
docker ps --filter 'name=^/wxq-prometheus$' --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo "--- Args:"
docker inspect wxq-prometheus --format '{{range .Args}}{{.}}{{"\n"}}{{end}}'
echo "--- 网络别名(必须含 prometheus):"
docker inspect wxq-prometheus --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} -> {{$v.IPAddress}} aliases={{$v.Aliases}}{{"\n"}}{{end}}'
echo
echo "===== [2] 接收端是否开启 ====="
for p in /api/v1/status/runtimeinfo /-/ready /-/healthy; do
  printf '  %-32s HTTP %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://10.100.10.29:9091$p)"
done
echo "  --- 关键: remote write 端点(空 POST, 期望 400 而不是 404) ---"
echo -n "  POST /api/v1/write (空体) => HTTP "
curl -s -o /dev/null -w '%{http_code}\n' --max-time 8 -XPOST 'http://10.100.10.29:9091/api/v1/write'
echo -n "  POST /api/v1/write (远端写协议空体) => HTTP "
curl -s -o /dev/null -w '%{http_code}\n' --max-time 8 -XPOST -H 'Content-Encoding: snappy' -H 'Content-Type: application/x-protobuf' -H 'X-Prometheus-Remote-Write-Version: 0.1.0' --data-binary '' 'http://10.100.10.29:9091/api/v1/write'
echo
echo "===== [3] 日志无报错 ====="
docker logs wxq-prometheus --tail 25 2>&1
echo "--- 关键字扫描(近 200 行):"
docker logs wxq-prometheus --tail 200 2>&1 | grep -iE 'level=error|panic|fatal|corrupt|refused' || echo "  (无 error/panic/fatal)"
echo
echo "===== [4] 数据卷保留(重启后 TSDB 应仍是原数据) ====="
curl -s 'http://10.100.10.29:9091/api/v1/status/tsdb' 2>&1 | head -c 400; echo
echo "--- 最早数据时间(min time):"
curl -s 'http://10.100.10.29:9091/api/v1/status/tsdb' 2>&1 | python3 -c "import sys,json;d=json.load(sys.stdin)['data'];print(' headStats:',d.get('headStats',{}).get('numSeries'),'series; minTime=',d.get('headStats',{}).get('minTime'))" 2>&1
echo
echo "===== [5] 依赖连通性(网络别名是否仍生效) ====="
docker exec wxq-prometheus wget -qO- --timeout=5 http://victoria-metrics:8428/-/healthy 2>&1 | head -2; echo "  ^ victoria-metrics alias"
docker exec wxq-prometheus wget -qO- --timeout=5 http://alertmanager:9093/-/healthy 2>&1 | head -2; echo "  ^ alertmanager alias"
echo
echo "===== [6] 本地抓取与规则是否正常 ====="
echo -n "  count(up) = "
curl -s 'http://10.100.10.29:9091/api/v1/query?query=count(up)' | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['result'][0]['value'][1])" 2>&1
echo -n "  规则组数 = "
curl -s http://10.100.10.29:9091/api/v1/rules | python3 -c "import sys,json;d=json.load(sys.stdin)['data']['groups'];print(len(d))" 2>&1
echo -n "  规则健康状况: "
curl -s http://10.100.10.29:9091/api/v1/rules | grep -o '"health":"[a-z]*"' | sort | uniq -c | tr '\n' ' '; echo
echo -n "  本地 remote_write 到 VM 是否恢复: "
curl -s http://10.100.10.29:9091/api/v1/query?query='prometheus_remote_storage_samples_total' | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print('series=',len(r), [x['value'][1] for x in r][:3])" 2>&1
echo
echo "===== [7] 其余容器未受影响 ====="
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -i wxq
