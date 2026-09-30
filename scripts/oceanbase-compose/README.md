# OceanBase 容器化固定 IP 方案 — README

## 一、背景

- 现有集群数据（`/deploy/infra/oceanbase/ob`）的元数据**绑定在 172.17.0.2**（docker0 第一个地址）。
- docker0 按“容器启动顺序”分配 IP：2026-09-18 polardb 先起抢走 .2，oceanbase 拿到 .3，
  OBD 启动时报 `OBD-1013: root@172.17.0.2 connect failed: time out`，observer 起不来。
- 宿主 IP 未来会变化，因此采用 **容器自定义网络 + 固定容器 IP**（与宿主 IP 无关）。

## 二、文件清单（均为新增，不动原文件）

| 文件 | 作用 |
|---|---|
| `docker-compose.yml` | 固化启动参数 + 自定义网段 + 固定 IP + 健康检查 |
| `.env`（可选） | 覆盖网段：`OB_SUBNET` / `OB_GATEWAY` / `OB_STATIC_IP` |
| `ob-start.sh` | 过渡方案：保序启动 + IP/连通性自检 |
| `ob-stop.sh` | 停止 |

## 三、激活路径（三选一）

### 路径1（推荐，数据零风险，需一次 docker 重启）
把 docker0 挪开，让 compose 网络沿用 172.17.0.0/24 → **OB 继续用 172.17.0.2**：

```bash
# 1. 改 docker0 网段（172.17 让位给 compose）
cat > /etc/docker/daemon.json <<'EOF'
{ "bip": "172.16.0.1/16" }
EOF
# 若 daemon.json 已有内容，手动合并 "bip": "172.16.0.1/16" 一项

# 2. 写 .env 固定 IP 为原来的 172.17.0.2
cd /deploy/infra/oceanbase
cat > .env <<'EOF'
OB_SUBNET=172.17.0.0/24
OB_GATEWAY=172.17.0.1
OB_STATIC_IP=172.17.0.2
EOF

# 3. 重启 docker（所有容器会重启，GLM-4 需重新加载模型，预留 10 分钟窗口）
systemctl restart docker

# 4. 用 compose 拉起 oceanbase（固定 172.17.0.2），polardb 等照常 docker start
docker-compose up -d
docker start polardb

# 5. 验证
bash ob-start.sh   # 或 docker exec oceanbase-ce obclient -h127.0.0.1 -P2881 -uroot@test -p12345 -e "select 1"
```

### 路径2（过渡，不重启 docker）
继续用 docker0，靠 `ob-start.sh` 保证“oceanbase 先起”。
宿主重启后手动执行一次 `bash ob-start.sh`（或把它挂成开机服务）。

### 路径3（全新环境）
新环境第一次部署就直接 `docker-compose up -d`，从零初始化，
固定 IP 172.20.0.2 从第一天就与数据绑定，无历史包袱。
（空目录初始化流程见前述：等 entrypoint `boot success!`，3~5 分钟。）

## 四、验证命令

```bash
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' oceanbase-ce   # 应为固定IP
docker exec oceanbase-ce obd cluster list                                                   # obcluster running
docker exec oceanbase-ce obclient -h127.0.0.1 -P2881 -uroot@test -p12345 -e "select 1"
```

## 五、备份（建议立刻做一次）

```bash
docker stop oceanbase-ce
tar -czf /deploy/backup/ob_seed_$(date +%F).tar.gz -C /deploy/infra/oceanbase ob obd templates limits-nofile.conf docker-run.sh docker-compose.yml
docker start oceanbase-ce
```

## 六、宿主 IP 变化时的配合调整（重要）

端口发布绑的是 0.0.0.0，宿主 IP 变化**不影响 OB 本身**；
但**本机 api 的连接串**写死了 `192.168.21.111`，宿主 IP 一变就连不上库：
- `chat_doc_0918/configs/kb_config.py:66` → 建议把 `192.168.21.111:2881` 改成 `127.0.0.1:2881`
- `configs/model_config.py:96/102`（embed 8105 / rerank 8106）同理建议改 `127.0.0.1`
改完 `systemctl restart chat_doc_api`。
