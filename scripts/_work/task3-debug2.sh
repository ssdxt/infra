#!/bin/bash
YML=/data1/apps/wxq-plant01-monitor/prometheus/prometheus.yml
C=wxq-prometheus
echo "===== [1] 宿主机 prometheus.yml 的 rule_files 实况 ====="
grep -n 'rule_files' -A3 "$YML"
echo "  --- md5 / mtime ---"
md5sum "$YML"; stat -c '%y  %s bytes' "$YML"
echo
echo "===== [2] 容器内看到的同一文件 ====="
docker exec $C sh -c 'grep -n "rule_files" -A3 /etc/prometheus/prometheus.yml'
echo "  --- 容器内 md5 ---"
docker exec $C md5sum /etc/prometheus/prometheus.yml
echo
echo "===== [3] 挂载点是否还是同一个 inode(bind mount 真身校验) ====="
echo -n "  宿主机 inode : "; stat -c '%i' "$YML"
echo -n "  容器内 inode : "; docker exec $C stat -c '%i' /etc/prometheus/prometheus.yml
echo
echo "===== [4] 直接用容器内路径重载一次, 并看是否加载到 230 条 ====="
echo -n "  reload HTTP: "; curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:9091/-/reload
sleep 6
curl -s http://127.0.0.1:9091/api/v1/rules | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['groups']
print('  groups =',len(d),' rules =',sum(len(g['rules']) for g in d))
print('  涉及文件:')
for f in sorted({g.get('file') for g in d}): print('    ',f)
"
echo
echo "===== [5] 容器启动命令里 config.file 指向 ====="
docker inspect $C --format '{{range .Args}}{{.}}{{"\n"}}{{end}}'
echo
echo "===== [6] 容器内 /etc/prometheus 目录(是否有覆盖文件) ====="
docker exec $C ls -la /etc/prometheus/
