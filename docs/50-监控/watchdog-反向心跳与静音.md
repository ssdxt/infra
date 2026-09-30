# Watchdog 反向心跳 + 管道件静音（plant01）

## 背景

- **Watchdog** 是 kube-prometheus-stack 的"死人开关"：故意永远 firing，用于反向证明告警链路存活。
- **InfoInhibitor** 是抑制辅助件：某命名空间有 warning/critical 时压掉该空间的 info 告警。
- 两者都是管道件（官方建议 route 到 null 接收器），不应该推钉钉刷屏。

## 后补调整

### 1. 静音管道件（plant01 Alertmanager）
`alertmanager/alertmanager.yml`（改前备份 .bak.*）：
```yaml
route:
  routes:
    - match_re:            # ← 插入为第一条子路由
        alertname: "Watchdog|InfoInhibitor"
      receiver: 'null'
receivers:
  - name: 'null'           # 空接收器 = 只吞不发
  - name: 'default'
    ...
```
- 插入后必须 `docker exec wxq-alertmanager /bin/amtool check-config` 校验，失败恢复备份
- ⚠️ 坑：`- name: 'null'` 必须与现有 `- name:` **同缩进**（顶格会破坏 YAML，amtool 校验失败要回滚）
- 生效：`docker compose restart alertmanager`

### 2. Watchdog 反向心跳（兑现死人开关的价值）
Watchdog 规则保留不删（仍在 Alertmanager 里 firing），在 **plant01 宿主机**加反向探针：
- 脚本：`/data1/apps/wxq-plant01-monitor/scripts/watchdog-heartbeat.sh`
- cron：`/etc/cron.d/watchdog-heartbeat`（*/5 * * * *）
- 逻辑：每 5 分钟 curl Alertmanager API 查 Watchdog 是否活跃 → 查不到 = 告警链路挂了 → 走 PrometheusAlert 发钉钉 critical（30 分钟冷却防轰炸）
- 日志：`/var/log/watchdog-heartbeat.log`

### 3. ⚠️ 关键坑：webhook 的主机名
alertmanager.yml 里的钉钉 URL 用的是 **`http://prometheus-alert:8080`（容器网络名）**——宿主机 cron 解析不了，**必须换成 `http://localhost:8280`**（host 端口映射 8280→8080）。脚本里已替换。

### 4. 验证方法
```bash
# 正常路径（应静默退出）
bash /data1/apps/wxq-plant01-monitor/scripts/watchdog-heartbeat.sh
# 故障路径演练（发一条真实测试钉钉）
TEST=1 bash /data1/apps/wxq-plant01-monitor/scripts/watchdog-heartbeat.sh
# 手动演练心跳丢失（确认收到钉钉后立刻删状态文件恢复）
systemctl stop chronyd >/dev/null 2>&1   # 无关操作勿做，仅示例
```

## 验证记录（2026-09-30）
- amtool check-config：SUCCESS（route + 4 receivers）
- Alertmanager /-/ready：200；启动日志 0 error
- 故障路径演练：POST → HTTP 200 / `errcode:0`，钉钉实收测试消息 ✅
