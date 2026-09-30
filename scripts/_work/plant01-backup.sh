#!/bin/bash
# ============================================================
#  plant01 监控栈 —— 改动前完整备份
#  1) 配置目录全量快照
#  2) 所有 wxq 容器的 docker inspect 全量 JSON（含原始启动参数）
#  3) 生成 prometheus 容器的"原始启动命令"记录文件
# ============================================================
set -u
BASE=/data1/apps/wxq-plant01-monitor
STAMP=$(date +%Y%m%d-%H%M%S)
OUT="$BASE/BACKUP-$STAMP"
mkdir -p "$OUT"

echo "备份目录: $OUT"
echo

echo "[1/4] 全量备份配置目录(排除 BACKUP-*)..."
tar czf "$OUT/app-config-$STAMP.tar.gz" \
  --exclude='BACKUP-*' \
  -C "$BASE" . 2>/dev/null
echo "      app-config-$STAMP.tar.gz  $(du -h "$OUT/app-config-$STAMP.tar.gz" | cut -f1)"

echo
echo "[2/4] 导出所有 wxq 容器 docker inspect 全量 JSON..."
mkdir -p "$OUT/inspect"
for c in $(docker ps -a --format '{{.Names}}' | grep -i wxq | sort); do
  docker inspect "$c" > "$OUT/inspect/$c.json" 2>/dev/null
  printf '      %-24s %s\n' "$c" "$(du -h "$OUT/inspect/$c.json" | cut -f1)"
done

echo
echo "[3/4] 记录 wxq-prometheus 原始启动命令..."
{
  echo "# wxq-prometheus 原始启动参数快照"
  echo "# 备份时间: $STAMP"
  echo "# 宿主机: $(hostname)  ($(date))"
  echo
  echo "IMAGE=$(docker inspect wxq-prometheus --format '{{.Config.Image}}')"
  echo "ENTRYPOINT=$(docker inspect wxq-prometheus --format '{{json .Config.Entrypoint}}')"
  echo "CMD=$(docker inspect wxq-prometheus --format '{{json .Config.Cmd}}')"
  echo "ARGS=$(docker inspect wxq-prometheus --format '{{json .Args}}')"
  echo "PORTBINDINGS=$(docker inspect wxq-prometheus --format '{{json .HostConfig.PortBindings}}')"
  echo "RESTART=$(docker inspect wxq-prometheus --format '{{json .HostConfig.RestartPolicy}}')"
  echo "NETWORKMODE=$(docker inspect wxq-prometheus --format '{{.HostConfig.NetworkMode}}')"
  echo "NETWORK_ALIASES=$(docker inspect wxq-prometheus --format '{{range $k,$v := .NetworkSettings.Networks}}{{$v.Aliases}}{{end}}')"
  echo "COMPOSE_LABELS=$(docker inspect wxq-prometheus --format '{{json .Config.Labels}}')"
  echo
  echo "## Mounts"
  docker inspect wxq-prometheus --format '{{range .Mounts}}{{.Type}} {{.Name}}{{.Source}} -> {{.Destination}} RW={{.RW}}{{"\n"}}{{end}}'
  echo
  echo "## 等价的完整 docker run 命令（回滚用）"
  echo "docker rm -f wxq-prometheus"
  echo -n "docker run -d --name wxq-prometheus --restart unless-stopped --network wxq-monitor --network-alias prometheus"
  for m in $(docker inspect wxq-prometheus --format '{{range .Mounts}}{{.Source}}:{{.Destination}}:{{if .RW}}rw{{else}}ro{{end}}{{"\n"}}{{end}}'); do
    echo -n " -v $m"
  done
  echo -n " -p 9091:9090 $(docker inspect wxq-prometheus --format '{{.Config.Image}}')"
  for a in $(docker inspect wxq-prometheus --format '{{range .Args}}{{.}}{{"\n"}}{{end}}'); do
    echo -n " $a"
  done
  echo
} > "$OUT/ORIGINAL-STARTUP-COMMAND.txt" 2>&1
echo "      ORIGINAL-STARTUP-COMMAND.txt"
cat "$OUT/ORIGINAL-STARTUP-COMMAND.txt"

echo
echo "[4/4] 校验备份完整性..."
ls -la "$OUT"
echo "--- inspect 文件数: $(ls "$OUT/inspect" | wc -l)"
echo "--- tar 内容抽样:"
tar tzf "$OUT/app-config-$STAMP.tar.gz" | head -8
echo
echo "BACKUP_DIR=$OUT"
