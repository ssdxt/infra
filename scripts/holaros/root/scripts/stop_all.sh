#!/bin/bash
# ============================================================
# 192.168.21.105 (Jetson AGX Thor) 全部 compose 服务关闭脚本
# 关闭顺序与启动相反: 业务应用 -> AI/GPU推理 -> 中间件 -> 数据库
# 用法: bash stop_all.sh
# 说明: 使用 docker-compose stop (保留容器, 可用 start_all.sh 重新拉起)
#       如需彻底删除容器可改用 down:  sed -i 's/ stop/ down/g' stop_all.sh
# ============================================================
set -u
DC="docker-compose"
LOG="/root/scripts/stop_all.log"

log(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

stop(){ # $1=目录 $2=文件 $3=说明
  log "== 停止: $3 =="
  if (cd "$1" && $DC -f "$2" stop) >>"$LOG" 2>&1; then
    log "   OK  $3"
  else
    log "   !! 失败 $3 (见日志 $LOG)"
  fi
}

# ---------- 1. 业务应用 ----------
log "== 阶段1: 业务应用 =="
stop /opt/1panel/apps/local/windows-arm/windows-arm docker-compose.yml "windows-arm 虚拟机"
stop /root/apps/docker/holarmeetnotesai docker-compose.yml "会议纪要AI holarmeetnotesai"
stop /root/apps/docker/holar2dhuman docker-compose.yml "2D数字人 holar2dhuman"
stop /root/apps/docker/holargwxz docker-compose.yml "公文写作 holargwxz"
stop /root/apps/docker/holarchatbi docker-compose.yml "holarchatbi (holardataq BI)"
stop /opt/1panel/apps/local/holartts/holartts docker-compose.yml "holartts TTS"
stop /opt/1panel/apps/local/holarkanban/HolarKanban docker-compose.yml "holarkanban 看板"
stop /opt/1panel/apps/local/holaros/holaros docker-compose.yml "holaros 门户套件"
stop /root/work/holarvm docker-compose.yml "视频会议 holarvm(meeting-*)"
stop /root/apps/docker/holarchat docker-compose.yml "holarchat 聊天"
stop /data/aippt docker-compose.yml "AI PPT 全套"

# ---------- 2. AI/GPU 推理服务 ----------
log "== 阶段2: AI/GPU 推理服务 =="
stop /root/llm/docker_2/qwen3_30b_a3b_instruct_nvfp4 docker-compose.yml "vLLM Qwen3-30B"
stop /root/llm/docker_2/qwen3_next_80b_a3b_instruct_nvfp4 docker-compose.yml "vLLM Qwen3-Next-80B"
stop /root/asr_work/holarasr_online docker-compose.yml "在线ASR holarasr"
stop /root/asr_work/docker docker-compose.yml "离线ASR asr_offline"
stop /root/llm/docker_2/mineru_2509_1.2b docker-compose.yml "vLLM holarfileparse_sgl_1.2b"
stop /root/sherpa/docker docker-compose.yml "TTS holar_tts_82m"
stop /root/embed docker-compose-embed.yml "embedding pytorch-embed"

# ---------- 3. 文档/文件服务 ----------
log "== 阶段3: 文档/文件服务 =="
stop /root/apps/docker/holarfileparse docker-compose.yml "holarfileparse 文件解析"
stop /root/work docker-compose-deepdoc.yml "deepdoc 文档解析"

# ---------- 4. 中间件 + 数据库 ----------
log "== 阶段4: 中间件与数据库 =="
stop /root/work docker-compose-oneapi.yml "one-api + redis"
stop /root/work docker-compose-database.yaml "数据库 pg/mysql/minio/mongo"

log "== 已全部停止 (容器保留, 未删除) =="
docker ps --format "table {{.Names}}\t{{.Status}}" | tee -a "$LOG"
