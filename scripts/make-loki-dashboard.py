#!/usr/bin/env python3
# 生成并部署 Loki 看板到 Grafana（通过 sidecar 自动加载的 ConfigMap 机制）
import json, subprocess, sys, time

NS_GRAF = "monitoring"
NS_DASH = "logging"
GPOD = subprocess.run(["kubectl","-n",NS_GRAF,"get","pods","-l","app.kubernetes.io/name=grafana",
                       "-o","jsonpath={.items[0].metadata.name}"],capture_output=True,text=True).stdout.strip()
print("Grafana Pod:", GPOD)

# 1) 取 Loki 数据源 UID
def grafana_api(path):
    out = subprocess.run(["kubectl","-n",NS_GRAF,"exec",GPOD,"-c","grafana","--","sh","-c",
        'wget -qO- --header="Content-Type: application/json" "http://admin:prom-operator@localhost:3000%s"' % path],
        capture_output=True,text=True).stdout
    return json.loads(out) if out.strip() else None

ds = grafana_api("/api/datasources")
uid = None
for d in ds or []:
    print("  数据源:", d.get("name"), d.get("type"), d.get("uid"))
    if d.get("type") == "loki":
        uid = d.get("uid")
if not uid:
    print("❌ 没找到 Loki 数据源"); sys.exit(1)
print("Loki 数据源 UID:", uid)

LOKI = {"type": "loki", "uid": uid}

def ts_panel(pid, title, expr, gp, legend="{{namespace}}", unit="short", extra=None):
    p = {
        "id": pid, "title": title, "type": "timeseries",
        "datasource": LOKI, "gridPos": gp,
        "targets": [{"refId": "A", "datasource": LOKI, "expr": expr, "legendFormat": legend,
                     "queryType": "range"}],
        "fieldConfig": {"defaults": {"unit": unit, "custom": {"drawStyle": "line", "fillOpacity": 12,
                        "lineWidth": 1, "showPoints": "never"}}, "overrides": []},
        "options": {"legend": {"displayMode": "table", "placement": "right", "calcs": ["sum"]},
                    "tooltip": {"mode": "multi"}},
    }
    if extra: p.update(extra)
    return p

def logs_panel(pid, title, expr, gp):
    return {
        "id": pid, "title": title, "type": "logs",
        "datasource": LOKI, "gridPos": gp,
        "targets": [{"refId": "A", "datasource": LOKI, "expr": expr, "queryType": "range"}],
        "options": {"showTime": True, "sortOrder": "Descending", "wrapLogMessage": True,
                    "enableLogDetails": True, "dedupStrategy": "none"},
    }

DASH = {
  "uid": "wxq-loki-overview",
  "title": "Loki 日志总览（wxq 集群）",
  "tags": ["loki", "wxq", "k8s"],
  "timezone": "browser",
  "schemaVersion": 39,
  "version": 1,
  "refresh": "30s",
  "editable": True,
  "time": {"from": "now-6h", "to": "now"},
  "templating": {"list": [{
      "name": "namespace", "label": "命名空间", "type": "query", "datasource": LOKI,
      "query": {"label": "namespace", "type": 1},
      "refresh": 2, "includeAll": True, "multi": True, "allValue": ".+",
      "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
      "sort": 1,
  }]},
  "panels": [
    ts_panel(1, "各命名空间日志量（行/秒）",
             'sum by (namespace) (count_over_time({namespace=~"$namespace"}[$__auto]))',
             {"h": 9, "w": 12, "x": 0, "y": 0}),
    ts_panel(2, "日志量 Top10 Pod",
             'topk(10, sum by (pod) (count_over_time({namespace=~"$namespace"}[$__auto])))',
             {"h": 9, "w": 12, "x": 12, "y": 0}, legend="{{pod}}"),
    ts_panel(3, "错误日志速率（error/fail/panic/timeout）",
             'sum by (namespace) (count_over_time({namespace=~"$namespace"} |~ "(?i)error|fail|panic|exception|timeout|refused" [$__auto]))',
             {"h": 9, "w": 12, "x": 0, "y": 9}),
    ts_panel(4, "错误最多 Top10 Pod",
             'topk(10, sum by (pod) (count_over_time({namespace=~"$namespace"} |~ "(?i)error|fail|panic|exception" [$__auto])))',
             {"h": 9, "w": 12, "x": 12, "y": 9}, legend="{{pod}}"),
    ts_panel(5, "stdout / stderr 比例",
             'sum by (stream) (count_over_time({namespace=~"$namespace"}[$__auto]))',
             {"h": 7, "w": 8, "x": 0, "y": 18}, legend="{{stream}}"),
    ts_panel(6, "按容器日志量 Top10",
             'topk(10, sum by (container) (count_over_time({namespace=~"$namespace"}[$__auto])))',
             {"h": 7, "w": 8, "x": 8, "y": 18}, legend="{{container}}"),
    ts_panel(7, "按节点日志量",
             'sum by (node) (count_over_time({namespace=~"$namespace"}[$__auto]))',
             {"h": 7, "w": 8, "x": 16, "y": 18}, legend="{{node}}"),
    logs_panel(8, "🔴 实时错误日志", '{namespace=~"$namespace"} |~ "(?i)error|fail|panic|exception|timeout|refused"',
               {"h": 14, "w": 24, "x": 0, "y": 25}),
    logs_panel(9, "📋 日志浏览器（选定命名空间全部日志）", '{namespace=~"$namespace"}',
               {"h": 14, "w": 24, "x": 0, "y": 39}),
  ],
}

json_text = json.dumps(DASH, ensure_ascii=False, indent=1)
open("/tmp/loki-dashboard.json","w").write(json_text)
print("已生成看板 JSON，%d 字节，%d 个面板" % (len(json_text), len(DASH["panels"])))

# 2) 打成 ConfigMap 并 apply（sidecar 靠 label 发现）
with open("/tmp/cm.yaml","w") as fh:
    subprocess.run(["kubectl","-n",NS_DASH,"create","configmap","loki-dashboard",
                    "--from-file=loki-dashboard.json=/tmp/loki-dashboard.json",
                    "--dry-run=client","-o","yaml"], stdout=fh, stderr=subprocess.DEVNULL)
subprocess.run(["kubectl","apply","-f","/tmp/cm.yaml"], check=False)
subprocess.run(["kubectl","-n",NS_DASH,"label","configmap","loki-dashboard",
                "grafana_dashboard=1","--overwrite"], check=False)
print("ConfigMap loki-dashboard 已创建并打标签 grafana_dashboard=1")

# 3) 等 sidecar 加载
print("等 50 秒让 Grafana sidecar 加载...")
time.sleep(50)
res = grafana_api("/api/search?query=Loki")
found = [x for x in (res or []) if x.get("type") == "dash-db"]
print("Grafana 中匹配 'Loki' 的看板:", [(x.get("title"), x.get("url")) for x in found] or "（还没出现）")
if not found:
    print("--- sidecar 日志（排查）")
    out = subprocess.run(["kubectl","-n",NS_GRAF,"logs","-l","app.kubernetes.io/name=grafana",
                          "-c","grafana-sc-dashboard","--tail=15"],capture_output=True,text=True).stdout
    print(out or "（无 sidecar 容器日志）")
print("")
print("打开方式: http://10.100.10.10:32298/d/wxq-loki-overview")
