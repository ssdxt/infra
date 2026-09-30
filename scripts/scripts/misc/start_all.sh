#!/bin/bash
# ============================================================
# 192.168.21.105 (Jetson AGX Thor) 全部 compose 服务启动脚本
# 启动顺序: 外部网络 -> 数据库 -> 中间件 -> AI/GPU推理 -> 业务应用
# 用法: bash start_all.sh   (可重复执行, 幂等)
# ============================================================
set -u
DC="docker-compose"            # 本机 docker-compose / docker compose 均为 v5.1.1
LOG="/root/scripts/start_all.log"

log(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

# 等待容器就绪(有 healthcheck 则等 healthy, 否则等 running), 最多 90s
wait_ready(){
  local cname="$1"
  for i in $(seq 1 30); do
    local hc
    hc=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cname" 2>/dev/null)
    local run
    run=$(docker inspect -f '{{.State.Running}}' "$cname" 2>/dev/null)
    if [ "$hc" = "healthy" ]; then log "    $cname 已 healthy"; return 0; fi
    if [ "$hc" = "none" ] && [ "$run" = "true" ]; then log "    $cname 已 running(无healthcheck)"; return 0; fi
    [ "$i" = "30" ] && { log "    !! $cname 90s 内未就绪 (state=$run health=$hc)"; return 1; }
    sleep 3
  done
}

# ---------- 1. 确保外部网络存在 ----------
log "== 阶段1: 外部网络 =="
if [ -f /root/scripts/create_network.sh ]; then
  bash /root/scripts/create_network.sh
else
  docker network inspect work_gptnetwork >/dev/null 2>&1 || {
    docker network create --driver bridge --subnet 172.19.0.0/16 --gateway 172.19.0.1 work_gptnetwork
    log "   已创建网络 work_gptnetwork (172.19.0.0/16)"
  }
fi

start(){ # $1=目录 $2=文件 $3=说明
  log "== 启动: $3 =="
  if (cd "$1" && $DC -f "$2" up -d --remove-orphans) >>"$LOG" 2>&1; then
    log "   OK  $3"
  else
    log "   !! 失败 $3 (见日志 $LOG)"
  fi
}

# ---------- 2. 基础设施: 数据库 ----------
log "== 阶段2: 数据库 =="
start /root/work docker-compose-database.yaml "数据库 pg/mysql/minio/mongo"
wait_ready pg; wait_ready mysql; wait_ready mongo; wait_ready minio

# ---------- 3. 中间件 ----------
log "== 阶段3: 中间件 =="
start /root/work docker-compose-oneapi.yml "one-api + redis"
wait_ready one-api; wait_ready redis

# ---------- 4. 文档/文件服务 ----------
log "== 阶段4: 文档/文件服务 =="
start /root/work docker-compose-deepdoc.yml "deepdoc 文档解析"
start /root/apps/docker/holarfileparse docker-compose.yml "holarfileparse 文件解析(含redis)"

# ---------- 5. AI/GPU 推理服务 (runtime: nvidia) ----------
# 注意: qwen3-30B / qwen3-Next-80B 两个大模型 vLLM 显存占用极大
#       (30B 用 gpu-memory-utilization 0.4≈49G / 80B 用 0.55≈67G),
#       与 mineru vLLM 等共享 Thor GPU, 不可同时全开。
#       默认不随 start_all 启动, 需要时取消下面两行注释单独起。
# start /root/llm/docker_2/qwen3_30b_a3b_instruct_nvfp4 docker-compose.yml "vLLM Qwen3-30B (GPU, 按需)"
# start /root/llm/docker_2/qwen3_next_80b_a3b_instruct_nvfp4 docker-compose.yml "vLLM Qwen3-Next-80B (GPU, 按需)"
log "== 阶段5: AI/GPU 推理服务 =="
start /root/embed docker-compose-embed.yml "embedding pytorch-embed (GPU)"
start /root/sherpa/docker docker-compose.yml "TTS holar_tts_82m (GPU)"
start /root/llm/docker_2/mineru_2509_1.2b docker-compose.yml "vLLM holarfileparse_sgl_1.2b (GPU)"
start /root/asr_work/docker docker-compose.yml "离线ASR asr_offline (GPU)"
start /root/asr_work/holarasr_online docker-compose.yml "在线ASR holarasr"

# ---------- 6. 业务应用 ----------
log "== 阶段6: 业务应用 =="
start /data/aippt docker-compose.yml "AI PPT 全套(含 nacos/redis/minio)"
wait_ready aippt-mysql; wait_ready aippt-nacos; wait_ready aippt-redis
start /root/apps/docker/holarchat docker-compose.yml "holarchat 聊天"
start /root/apps/docker/holarchatbi docker-compose.yml "holarchatbi (holardataq BI)"
start /root/apps/docker/holargwxz docker-compose.yml "公文写作 holargwxz"
start /root/apps/docker/holar2dhuman docker-compose.yml "2D数字人 holar2dhuman"
start /root/apps/docker/holarmeetnotesai docker-compose.yml "会议纪要AI holarmeetnotesai"
start /root/work/holarvm docker-compose.yml "视频会议 holarvm(meeting-*)"
start /opt/1panel/apps/local/holaros/holaros docker-compose.yml "holaros 门户套件"
wait_ready holaros-mysql
start /opt/1panel/apps/local/holarkanban/HolarKanban docker-compose.yml "holarkanban 看板"
start /opt/1panel/apps/local/holartts/holartts docker-compose.yml "holartts TTS"
start /opt/1panel/apps/local/windows-arm/windows-arm docker-compose.yml "windows-arm 虚拟机"

log "== 全部启动流程结束 =="
docker ps --format "table {{.Names}}\t{{.Status}}" | tee -a "$LOG"
