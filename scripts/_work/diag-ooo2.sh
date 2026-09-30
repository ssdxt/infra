#!/bin/bash
echo "现在(UTC): $(date -u '+%H:%M:%S')"
echo
echo "===== [1] 最近 15 分钟 out-of-order 明细(完整行) ====="
docker logs wxq-prometheus --since 15m 2>&1 | grep 'Out of order sample' | tail -10
echo
echo "===== [2] 按 __name__ 归类(最近 15 分钟) ====="
docker logs wxq-prometheus --since 15m 2>&1 | grep 'Out of order sample' \
  | grep -o '__name__=\\"[^"\\]*\\"' | sed 's/__name__=\\"//; s/\\"//' | sort | uniq -c | sort -rn
echo
echo "===== [3] 是否来自我们推的 job(看 series 里的 job 标签) ====="
docker logs wxq-prometheus --since 15m 2>&1 | grep 'Out of order sample' \
  | grep -o 'job=\\"[^"\\]*\\"' | sed 's/job=\\"//; s/\\"//' | sort | uniq -c | sort -rn
echo
echo "===== [4] 是否来自远程写(带 prometheus=\"monitoring/...\") ====="
docker logs wxq-prometheus --since 15m 2>&1 | grep 'Out of order sample' \
  | grep -c 'prometheus=\\"monitoring/'
echo "  ^ 若远小于总数, 说明还有非远程写来源(如 plant01 自身重复求值)"
echo
echo "===== [5] 关键: 这些序列在 plant01 上是否"同时"有两个来源 ====="
P=http://127.0.0.1:9091
for m in 'count:up1' 'ALERTS' 'node_namespace_pod_container:container_memory_rss'; do
  echo "  --- $m"
  echo -n "      本地来源(prometheus!~monitoring): "
  curl -s --get "$P/api/v1/query" --data-urlencode "query=count(last_over_time($m{prometheus!~\"monitoring/.*\"}[3m]))" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']; print(r[0]['value'][1] if r else 0)"
  echo -n "      远程来源(prometheus=~monitoring): "
  curl -s --get "$P/api/v1/query" --data-urlencode "query=count(last_over_time($m{prometheus=~\"monitoring/.*\"}[3m]))" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']; print(r[0]['value'][1] if r else 0)"
done
echo
echo "===== [6] 全局重复指标普查: 哪些指标同时在两个来源出现 ====="
echo "  (取一个近期时间窗内, 有本地来源 且 有远程来源 的指标名)"
curl -s --get "$P/api/v1/label/__name__/values" > /tmp/all_names.json
python3 - <<'PY'
import json,urllib.request,urllib.parse
P='http://127.0.0.1:9091'
def q(expr):
    u=P+'/api/v1/query?'+urllib.parse.urlencode({'query':expr})
    d=json.load(urllib.request.urlopen(u,timeout=25))['data']['result']
    return {x['metric'].get('__name__') for x in d if x['metric'].get('__name__')}
local=q('count by(__name__)(last_over_time({prometheus!~"monitoring/.*"}[3m]))')
remote=q('count by(__name__)(last_over_time({prometheus=~"monitoring/.*"}[3m]))')
both=sorted(local & remote)
print('  本地指标名 =',len(local),' 远程指标名 =',len(remote))
print('  两边同名(潜在冲突) =',len(both))
for n in both: print('    ',n)
PY
