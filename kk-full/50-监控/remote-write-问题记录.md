# remote_write 到 plant01 失败问题记录（PrometheusRemoteStorageFailures）

- 日期：2026-09-29
- 影响线：集群 Prometheus（monitoring/prometheus-prometheus-stack-kube-prom-prometheus-0）→ `http://10.100.10.29:9091/api/v1/write`（plant01，docker compose，容器 wxq-prometheus）
- 状态：**已修复**。失败增速 0、plant01 乱序拒收 0、告警已恢复（ALERTS 中 PrometheusRemoteStorageFailures 为空）

## 现象

- `prometheus_remote_storage_samples_failed_total` 累计从 ~670,000 持续涨到 ~728,000+
- `prometheus_remote_storage_samples_pending` ~1,400，`shards` = 1
- Alertmanager：PrometheusRemoteStorageFailures pending 即将 firing
- plant01 `/-/ready` 200、`count(up)` 正常可查（接收端本身活着）

## 排查命令与证据（全记录）

### 1. 判断是否正在失败（结论：正在发生，不是历史积压）

```
increase(prometheus_remote_storage_samples_failed_total[15m]) = 35172
rate(prometheus_remote_storage_samples_failed_total[5m])     = 29.6 /s
prometheus_remote_storage_samples_pending                    = 1534
```

### 2. 集群 Prometheus 日志 → 错误类型是 400 out of order（不是超时/连接拒绝）

```
kubectl -n monitoring logs prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus --tail=300 | grep -iE 'remote|error'
...
msg="non-recoverable error" failedSampleCount=2000
err="server returned HTTP status 400 Bad Request: out of order sample"
url=http://10.100.10.29:9091/api/v1/write
```

每 ~90 秒一批 2000 样本被整体拒收。

### 3. plant01 侧日志 → 服务端确认乱序拒收

```
docker logs wxq-prometheus --since 2h | grep -ciE 'out of order'   # 126 次
level=ERROR source=write_handler.go:230 msg="Out of order sample from remote write"
err="out of order sample"
series="{__name__=\"node_namespace_pod_container:container_memory_rss\", pod=\"cilium-envoy-79s8x\", ...}"
```

被拒样本时间戳仅滞后当前时间 2–4 分钟（近乎实时数据也乱序），说明不是单纯"旧积压等消化完就好"，而是 **plant01 乱序容忍=0，remote_write 链路正常的微小乱序（分片重切/重试后迟到）全部被整批拒收**。

### 4. plant01 环境

- 容器 wxq-prometheus，镜像 `harbor.wuxing.local/wxq-monitor/prometheus:v3.13.1`（真实版本 3.13.1，build 2026-07-10）
- compose：`/data1/apps/wxq-plant01-monitor/docker-compose.yaml`
- 磁盘：`df -h /data1` → 984G 总量、已用 28G（3%），**不是磁盘满/retention.size 顶格问题**
- 容器 2026-09-29 08:29 UTC 重启过（故障从该重启窗口后持续）

## 根因

1. plant01 Prometheus 于 09-29 08:29 重启，集群积压数据回放；
2. plant01 的 TSDB **乱序容忍窗口为 0**（默认），remote_write 链路固有的小概率乱序（分片 resharding 期间同系列样本被并行发送、批次超时重试后迟到）导致样本被服务端判为 out of order，**整批 400**；
3. 集群侧每批 2000 样本被 non-recoverable 丢弃，失败计数持续增长、告警触发；
4. plant01 该镜像 v3.13.1 的乱序窗口**不在** global 配置、也**没有** `--storage.tsdb.out-of-order-time-window` 启动参数（试过即 crash-loop），正确位置是配置文件 `storage.tsdb.out_of_order_time_window`。

## 修复（全部无损）

### plant01（10.100.10.29）

备份（先于一切改动）：

```
/data1/ssdxt/monitoring/backup/wxq-prometheus-inspect-20260929-pre-ooo.json   # docker inspect 快照
/data1/ssdxt/monitoring/backup/docker-compose.yaml.pre-ooo-20260929           # compose 原文件
/data1/ssdxt/monitoring/backup/prometheus.yml.pre-ooo-20260929                # 配置原文件
/data1/ssdxt/monitoring/backup/prometheus.yml.pre-storage-ooo-20260929        # 二次改前
```

改动：`/data1/apps/wxq-plant01-monitor/prometheus/prometheus.yml` 末尾追加（promtool check 通过后 `docker compose restart prometheus` 生效，TSDB 参数只能重启加载）：

```yaml
storage:
  tsdb:
    out_of_order_time_window: 30m   # 渲染为 storage.tsdb.outofordertimewindow: 1800000 (ms)
```

> 踩坑记录：v3.13.1 中 `global.out_of_order_time_window` 会报 "field not found"，`--storage.tsdb.out-of-order-time-window` 参数不存在（容器会 crash-loop，已当场回滚）。写法用 `storage.tsdb.out_of_order_time_window`。

### 集群侧（10.100.10.10）

remoteWrite 当初是 kubectl patch 打在 CR 上的（`/data1/ssdxt/monitoring/02-remote-write.sh`，不在 helm values 里，注意下次 helm upgrade 会丢，需并入 values）。为缓解积压+约束发送端，patch 了 queueConfig：

```
备份：/data1/ssdxt/monitoring/backup/prometheus-cr-pre-queue-patch-20260929.yaml
kubectl -n monitoring patch prometheus prometheus-stack-kube-prom-prometheus --type merge --patch-file /tmp/rw-patch.json
queueConfig: maxShards=1, minShards=1, maxSamplesPerSend=2000,
             batchSendDeadline=60s, minBackoff=500ms, maxBackoff=30s, sampleAgeLimit=1h
```

- `max_shards=1`：避免 resharding 并行导致的同系列乱序
- `sample_age_limit=1h`：丢弃 plant01 无法接收的过期样本，防积压雪崩
- writeRelabelConfigs 白名单原样保留，未动

## 验证

| 指标 | 修复前 | 修复后 |
|---|---|---|
| `rate(samples_failed_total[3m])` | 26–37 /s | **0** |
| `increase(samples_failed_total[5m])` | 35000+/15m | **0** |
| plant01 乱序拒收日志 | 126 次/2h | **0 次** |
| `samples_pending` | ~1500 波动 | ~1700 在途（发送 3222 samples/s，属正常队列在途量） |
| ALERTS{alertname="PrometheusRemoteStorageFailures"} | pending | **空（已恢复）** |

## 预防建议

1. **给 plant01 监控加磁盘水位告警**（node 文件系统 >80% 告警），防 retention.size=25GB 顶格引发逐出/写失败；
2. **remote_write 队列参数**保持 `max_shards` 适中（1–4），高吞吐场景如需多分片，接收端必须配乱序窗口 ≥ `max_shards 数 × batch_send_deadline`；
3. **接收端乱序窗口是必配项**：任何 remote write 接收端都建议 `out_of_order_time_window: 30m`（或至少 10m）；
4. 把 remoteWrite（含 queueConfig）**固化进 helm values**（`prometheus.prometheusSpec.remoteWrite`），否则 helm upgrade 会丢 CR patch；
5. plant01 compose/配置变更前一律先备份到 `/data1/ssdxt/monitoring/backup/`（已形成本次记录）。
