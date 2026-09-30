#!/bin/bash
# 修复 plant01 的 compose 文件 + 修复 wxq-prometheus 的标签孤儿问题
set -u
D=/data1/apps/wxq-plant01-monitor
cd $D || exit 1
TS=$(date +%m%d-%H%M)

echo "############ 0. 先备份、留好回滚手段 ############"
mkdir -p /data1/ssdxt/plant01-compose-backup
cp -a docker-compose.yaml /data1/ssdxt/plant01-compose-backup/docker-compose.wrong-$TS.yaml 2>/dev/null
cp -a docker-compose.yaml docker-compose.yaml.wrong-from-wsl.bak 2>/dev/null
cp -a docker-compose.reconstructed.yaml /data1/ssdxt/plant01-compose-backup/docker-compose.reconstructed-$TS.yaml
echo "  错误文件已备份为 docker-compose.yaml.wrong-from-wsl.bak + /data1/ssdxt/plant01-compose-backup/"
echo "  ⚠️ 注意：原文件里如果有 .env 变量定义，重建版已把值固化，不再依赖 .env"
echo ""

echo "############ 1. 记录 wxq-prometheus 现状（重建前）+ 生成回滚命令 ############"
docker inspect wxq-prometheus > /data1/ssdxt/plant01-compose-backup/wxq-prometheus-before-$TS.json 2>/dev/null
echo "  inspect 已存: /data1/ssdxt/plant01-compose-backup/wxq-prometheus-before-$TS.json"
python3 - <<'PYEOF' > /data1/ssdxt/plant01-compose-backup/prometheus-rollback-dockerrun.sh
import json, subprocess
d = json.loads(subprocess.run(['docker','inspect','wxq-prometheus'],capture_output=True,text=True).stdout)[0]
cfg, hc = d['Config'], d['HostConfig']
cmd = ["docker","run","-d","--name","wxq-prometheus","--restart",hc.get('RestartPolicy',{}).get('Name','unless-stopped')]
for k,v in (hc.get('PortBindings') or {}).items():
    for b in (v or []):
        cmd += ["-p", "%s:%s" % (b.get('HostPort'), k.split('/')[0])]
for m in (d.get('Mounts') or []):
    src = m.get('Name') if m.get('Type')=='volume' else m.get('Source')
    s = "%s:%s" % (src, m['Destination'])
    if not m.get('RW', True): s += ":ro"
    cmd += ["-v", s]
for e in (cfg.get('Env') or []):
    if e.split('=',1)[0] in ("PATH","HOSTNAME","HOME","TERM"): continue
    cmd += ["-e", e]
net = list((d['NetworkSettings'].get('Networks') or {}).keys())
if net:
    cmd += ["--network", net[0]]
    for a in (d['NetworkSettings']['Networks'][net[0]].get('Aliases') or []):
        if a != 'wxq-prometheus': cmd += ["--network-alias", a]
cmd.append(cfg['Image'])
cmd += (d.get('Args') or [])
print("# 回滚用：把 wxq-prometheus 按重建前状态重新拉起")
print("docker rm -f wxq-prometheus 2>/dev/null")
print(" ".join("'%s'" % x if ' ' in x or '*' in x else x for x in cmd))
PYEOF
echo "  回滚脚本已生成: /data1/ssdxt/plant01-compose-backup/prometheus-rollback-dockerrun.sh"
head -3 /data1/ssdxt/plant01-compose-backup/prometheus-rollback-dockerrun.sh | sed 's/^/    /'
echo ""

echo "############ 2. 启用重建后的 compose 文件 ############"
mv -f docker-compose.reconstructed.yaml docker-compose.yaml
echo "  已 mv docker-compose.reconstructed.yaml -> docker-compose.yaml"
echo -n "  name 行: "; grep -m1 '^name:' docker-compose.yaml
echo -n "  服务数: "; docker compose config --services 2>/dev/null | wc -l
echo -n "  语法校验: "; docker compose config -q 2>&1 && echo "OK"
echo ""

echo "############ 3. compose 是否认出现有容器 ############"
docker compose ps -a 2>&1 | head -14 | sed 's/^/  /'
echo ""

echo "############ 4. 修复 wxq-prometheus（唯一需要重建的）############"
echo "  重建前状态:"
docker inspect -f '    image={{.Config.Image}}  restart={{.HostConfig.RestartPolicy.Name}}' wxq-prometheus 2>/dev/null
docker stop wxq-prometheus >/dev/null 2>&1 && echo "    已停止"
docker rm wxq-prometheus >/dev/null 2>&1 && echo "    已删除旧容器（数据在具名卷 wxq-monitor_prometheus-data 中，未动）"
echo "  用 compose 重新拉起..."
docker compose up -d prometheus 2>&1 | tail -5 | sed 's/^/    /'
sleep 12
echo ""
echo "  重建后状态:"
docker inspect -f '    image={{.Config.Image}}
    args={{.Args}}
    重启={{.HostConfig.RestartPolicy.Name}}
    网络={{range $k,$v := .NetworkSettings.Networks}}{{$k}}[{{range $v.Aliases}}{{.}} {{end}}]{{end}}
    compose标签: proj={{index .Config.Labels "com.docker.compose.project"}} svc={{index .Config.Labels "com.docker.compose.service"}}' wxq-prometheus 2>/dev/null
echo ""

echo "############ 5. 验证 ############"
echo "--- compose 全量状态"
docker compose ps 2>&1 | head -14 | sed 's/^/  /'
echo ""
echo "--- Prometheus 健康"
echo -n "    /-/ready        : "; curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://10.100.10.29:9091/-/ready; echo
echo -n "    remote-write 参数: "; docker inspect -f '{{range .Args}}{{.}} {{end}}' wxq-prometheus | grep -q 'enable-remote-write-receiver' && echo "在 ✅" || echo "丢失 ❌"
echo -n "    remote_write 队列: "; curl -s --max-time 8 'http://10.100.10.29:9091/api/v1/query?query=prometheus_remote_storage_samples_total' 2>/dev/null | head -c 150; echo
echo ""
echo "--- 其他服务未受影响（应全部 Up）"
for c in wxq-grafana wxq-alertmanager wxq-victoriametrics wxq-prometheusalert wxq-node-exporter wxq-blackbox wxq-otel wxq-process-exporter wxq-pushgateway; do
  st=$(docker inspect -f '{{.State.Status}}' $c 2>/dev/null)
  echo "    $c : ${st:-缺失}"
done
echo ""
echo "--- Grafana 能否连到 Prometheus/VictoriaMetrics（容器名解析）"
docker exec wxq-grafana sh -c 'wget -qO- --timeout=5 http://prometheus:9090/-/ready 2>/dev/null | head -c 40; echo; wget -qO- --timeout=5 http://victoria-metrics:8428/health 2>/dev/null | head -c 40' 2>/dev/null | sed 's/^/    /' || echo "    （Grafana 镜像里没有 wget，跳过）"
echo ""
echo "############ 完成 ############"
echo "  备份与回滚材料：/data1/ssdxt/plant01-compose-backup/"
ls -la /data1/ssdxt/plant01-compose-backup/ | sed 's/^/    /'