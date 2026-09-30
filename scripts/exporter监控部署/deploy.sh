#!/bin/bash
###############################################################################
#  昇腾 NPU 监控 exporter 一键部署 / 验证
#  适用: Atlas 300I Duo (310P3) + 银河麒麟 V10 国防版 aarch64
#
#  用法:
#     bash deploy.sh install    # 部署并启动（node-exporter 容器 + npu-exporter 宿主服务）
#     bash deploy.sh verify     # 只验证，不改动
#     bash deploy.sh status     # 看状态
#     bash deploy.sh restart    # 重启两者
#     bash deploy.sh uninstall  # 卸载
#
#  前提: 本目录下有 docker-compose.yml / npu-exporter.service，
#        且镜像已存在于本机（docker images 可见）。
#  从 Windows 拷过来先转码: sed -i 's/\r$//' deploy.sh
###############################################################################
set +e
HERE=$(cd "$(dirname "$0")" && pwd)
MON=/deploy/infra/monitor
NPU_BIN=/opt/npu-exporter/npu-exporter
NPU_IMAGE=swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/ascendai/npu-exporter:v26.1.0-openeuler24.03-linuxarm64
DC=/usr/bin/docker-compose      # 本机 docker compose 子命令不可用，用独立二进制

hr(){ echo "-------------------------------------------------------------------"; }
say(){ echo; echo ">>> $*"; hr; }

install_all() {
  [ "$(id -u)" = "0" ] || { echo "必须以 root 执行"; exit 1; }

  say "1/5 准备目录"
  mkdir -p "$MON" /opt/npu-exporter /var/log/mindx-dl/npu-exporter
  cp -f "$HERE/docker-compose.yml" "$MON/docker-compose.yml"
  echo "  已放置 $MON/docker-compose.yml"

  say "2/5 从镜像提取 npu-exporter 二进制"
  if [ ! -x "$NPU_BIN" ]; then
    docker rm -f tmpget 2>/dev/null
    docker create --name tmpget --entrypoint /bin/true "$NPU_IMAGE" >/dev/null 2>&1 || {
      echo "  !! 镜像不存在: $NPU_IMAGE"; echo "     先 docker load / docker pull 再重试"; return 1; }
    docker cp tmpget:/usr/local/bin/npu-exporter "$NPU_BIN" >/dev/null 2>&1
    docker rm -f tmpget >/dev/null 2>&1
  fi
  chmod 755 "$NPU_BIN"
  ls -la "$NPU_BIN"

  say "3/5 安装 npu-exporter systemd 服务"
  cp -f "$HERE/npu-exporter.service" /etc/systemd/system/npu-exporter.service
  systemctl daemon-reload
  systemctl enable npu-exporter >/dev/null 2>&1
  systemctl restart npu-exporter
  sleep 15
  systemctl is-active npu-exporter

  say "4/5 启动 node-exporter 容器"
  cd "$MON" || return 1
  "$DC" up -d 2>&1 | tail -6

  say "5/5 验证"
  verify_all
}

verify_all() {
  say "端口监听"
  ss -lntp 2>/dev/null | grep -E ':(8082|11256|9100)' || echo "  没有任何端口在监听"

  say "npu-exporter :8082"
  local n
  n=$(curl -s -m 10 http://127.0.0.1:8082/metrics 2>/dev/null | grep -c '^npu_')
  echo "  http_code = $(curl -s -m 10 -o /dev/null -w '%{http_code}' http://127.0.0.1:8082/metrics 2>/dev/null)"
  echo "  npu_ 指标条数 = ${n:-0}     (正常应 >= 20)"
  curl -s -m 10 http://127.0.0.1:8082/metrics 2>/dev/null \
    | grep -E '^npu_chip_info_(name|health_status|temperature|power)' | head -6 | sed 's/^/    /'

  say "node-exporter :9100"
  echo "  http_code = $(curl -s -m 10 -o /dev/null -w '%{http_code}' http://127.0.0.1:9100/metrics 2>/dev/null)"
  echo "  node_ 指标条数 = $(curl -s -m 10 http://127.0.0.1:9100/metrics 2>/dev/null | grep -c '^node_')"
  curl -s -m 10 http://127.0.0.1:9100/metrics 2>/dev/null \
    | grep -E '^node_(load1|memory_MemTotal_bytes)' | head -2 | sed 's/^/    /'

  say "结论"
  if [ "${n:-0}" -gt 0 ] && curl -s -m 8 -o /dev/null http://127.0.0.1:9100/metrics 2>/dev/null; then
    echo "  >>> 两个 exporter 均正常"
  else
    echo "  >>> 有异常，检查:"
    echo "      systemctl status npu-exporter"
    echo "      journalctl -u npu-exporter -n 50"
    echo "      tail -30 /var/log/mindx-dl/npu-exporter/npu-exporter.log"
    echo "      cd $MON && $DC logs --tail 30 node-exporter"
  fi
}

status_all() {
  say "npu-exporter"
  systemctl is-enabled npu-exporter 2>&1 | sed 's/^/  enabled: /'
  systemctl is-active  npu-exporter 2>&1 | sed 's/^/  active : /'
  echo "  日志: journalctl -u npu-exporter -f"
  echo "        tail -f /var/log/mindx-dl/npu-exporter/npu-exporter.log"
  say "node-exporter"
  docker ps -a --filter name=node-exporter --format '  {{.Names}} | {{.Status}}'
  say "端口"
  ss -lntp 2>/dev/null | grep -E ':(8082|11256|9100)'
}

uninstall_all() {
  say "停止 npu-exporter"
  systemctl disable --now npu-exporter 2>/dev/null
  rm -f /etc/systemd/system/npu-exporter.service
  systemctl daemon-reload
  echo "  已移除服务（二进制保留在 $NPU_BIN，如需删除: rm -rf /opt/npu-exporter）"
  say "停止 node-exporter"
  cd "$MON" 2>/dev/null && "$DC" down 2>&1 | tail -3
  echo "  已停止"
}

case "$1" in
  install)   install_all ;;
  verify)    verify_all ;;
  status)    status_all ;;
  restart)   systemctl restart npu-exporter; cd "$MON" && "$DC" restart; status_all ;;
  uninstall) uninstall_all ;;
  *) cat <<EOF
昇腾 NPU 监控 exporter 部署脚本

  bash $0 install     部署并启动（node-exporter 容器 + npu-exporter 宿主服务）
  bash $0 verify      只验证，不改动
  bash $0 status      查看状态
  bash $0 restart     重启
  bash $0 uninstall   卸载

产物:
  /deploy/infra/monitor/docker-compose.yml           node-exporter
  /etc/systemd/system/npu-exporter.service           npu-exporter 服务
  /opt/npu-exporter/npu-exporter                     从镜像提取的二进制
  /var/log/mindx-dl/npu-exporter/npu-exporter.log    运行日志

注意: npu-exporter 跑在宿主上而不是容器里，原因见 README.md。
EOF
    ;;
esac
