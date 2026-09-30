#!/usr/bin/env python3
# 生成/更新 Loki 看板（v3）
#   v3 新增: 命名空间 / Pod / 容器 / 日志级别 四个筛选变量
#   性能优化: minInterval=1m、maxDataPoints=300、默认范围 3h、刷新 1m、日志面板 maxLines=400
import json, subprocess, time

NS_GRAF, NS_DASH = "monitoring", "logging"
GPOD = subprocess.run(["kubectl","-n",NS_GRAF,"get","pods","-l","app.kubernetes.io/name=grafana",
                       "-o","jsonpath={.items[0].metadata.name}"],capture_output=True,text=True).stdout.strip()

def grafana_api(path):
    out = subprocess.run(["kubectl","-n",NS_GRAF,"exec",GPOD,"-c","grafana","--","sh","-c",
        'wget -qO- --header="Content-Type: application/json" "http://admin:prom-operator@localhost:3000%s"' % path],
        capture_output=True,text=True).stdout
    return json.loads(out) if out.strip() else None

LOKI = {"type": "loki", "uid": next(d["uid"] for d in grafana_api("/api/datasources") if d["type"]=="loki")}
print("Loki UID:", LOKI["uid"])

SEL   = '{namespace=~"$namespace", pod=~"$pod", container=~"$container"}'
LEVEL = ' |~ "(?i)$level"'          # $level 默认为空 = 不额外过滤

def ts(pid, title, expr, gp, legend):
    return {"id": pid, "title": title, "type": "timeseries", "datasource": LOKI,
            "gridPos": gp, "maxDataPoints": 300, "interval": "1m",
            "targets": [{"refId":"A","datasource":LOKI,"expr":expr,"legendFormat":legend,"queryType":"range"}],
            "fieldConfig": {"defaults": {"unit":"short","custom":{"drawStyle":"line","fillOpacity":10,
                            "lineWidth":1,"showPoints":"never"}}, "overrides":[]},
            "options": {"legend":{"displayMode":"table","placement":"right","calcs":["sum"]},
                        "tooltip":{"mode":"multi"}}}

def logs(pid, title, expr, gp):
    return {"id": pid, "title": title, "type": "logs", "datasource": LOKI,
            "gridPos": gp, "maxDataPoints": 300,
            "targets": [{"refId":"A","datasource":LOKI,"expr":expr,"queryType":"range"}],
            "options": {"showTime":True,"sortOrder":"Descending","wrapLogMessage":True,
                        "enableLogDetails":True,"dedupStrategy":"none","maxLines":400}}

DASH = {
 "uid":"wxq-loki-overview","title":"Loki 日志总览（wxq 集群）","tags":["loki","wxq","k8s"],
 "timezone":"browser","schemaVersion":39,"version":3,"editable":True,
 "refresh":"1m","time":{"from":"now-3h","to":"now"},
 "minInterval":"1m",
 "templating":{"list":[
   {"name":"namespace","label":"命名空间","type":"query","datasource":LOKI,
    "query":{"label":"namespace","type":1},"refresh":2,"includeAll":True,"multi":True,
    "allValue":".+","sort":1,"current":{"selected":True,"text":["All"],"value":["$__all"]}},
   {"name":"pod","label":"Pod","type":"query","datasource":LOKI,
    "query":{"label":"pod","type":1,"stream":'{namespace=~"$namespace"}'},"refresh":2,
    "includeAll":True,"multi":True,"allValue":".+","sort":1,
    "current":{"selected":True,"text":["All"],"value":["$__all"]}},
   {"name":"container","label":"容器","type":"query","datasource":LOKI,
    "query":{"label":"container","type":1,"stream":'{namespace=~"$namespace"}'},"refresh":2,
    "includeAll":True,"multi":True,"allValue":".+","sort":1,
    "current":{"selected":True,"text":["All"],"value":["$__all"]}},
   {"name":"level","label":"日志级别","type":"custom","datasource":LOKI,
    "query":" : 全部, (?i)error|fatal|panic|exception : 错误(ERROR/FATAL/PANIC), (?i)warn : 警告(WARN), (?i)info : 信息(INFO), (?i)debug|trace : 调试(DEBUG/TRACE)",
    "includeAll":False,"multi":False,"current":{"selected":True,"text":"全部","value":""}},
 ]},
 "panels":[
  ts(1,"日志量 by 命名空间", 'sum by (namespace) (count_over_time(%s%s [$__interval]))'%(SEL,LEVEL), {"h":8,"w":12,"x":0,"y":0},"{{namespace}}"),
  ts(2,"日志量 Top10 Pod",  'topk(10, sum by (pod) (count_over_time(%s%s [$__interval])))'%(SEL,LEVEL), {"h":8,"w":12,"x":12,"y":0},"{{pod}}"),
  ts(3,"🔴 错误速率 by 命名空间", 'sum by (namespace) (count_over_time(%s |~ "(?i)error|fail|panic|exception|timeout|refused" [$__interval]))'%SEL, {"h":8,"w":12,"x":0,"y":8},"{{namespace}}"),
  ts(4,"🔴 错误最多 Top10 Pod",   'topk(10, sum by (pod) (count_over_time(%s |~ "(?i)error|fail|panic|exception" [$__interval])))'%SEL, {"h":8,"w":12,"x":12,"y":8},"{{pod}}"),
  ts(5,"stdout / stderr",   'sum by (stream) (count_over_time(%s%s [$__interval]))'%(SEL,LEVEL), {"h":7,"w":8,"x":0,"y":16},"{{stream}}"),
  ts(6,"按容器 Top10",      'topk(10, sum by (container) (count_over_time(%s%s [$__interval])))'%(SEL,LEVEL), {"h":7,"w":8,"x":8,"y":16},"{{container}}"),
  ts(7,"按节点",           'sum by (node) (count_over_time(%s%s [$__interval]))'%(SEL,LEVEL), {"h":7,"w":8,"x":16,"y":16},"{{node}}"),
  logs(8,"🔴 实时错误日志", '%s |~ "(?i)error|fail|panic|exception|timeout|refused"'%SEL, {"h":12,"w":24,"x":0,"y":23}),
  logs(9,"📋 日志浏览器（受 4 个变量过滤）", '%s%s'%(SEL,LEVEL), {"h":12,"w":24,"x":0,"y":35}),
 ],
}

open("/tmp/loki-dashboard.json","w").write(json.dumps(DASH, ensure_ascii=False, indent=1))
print("已生成 v3：%d 面板 / 变量=%s" % (len(DASH["panels"]), [v["name"] for v in DASH["templating"]["list"]]))

subprocess.run(["kubectl","-n",NS_DASH,"delete","configmap","loki-dashboard","--ignore-not-found"],capture_output=True,text=True)
with open("/tmp/cm.yaml","w") as fh:
    subprocess.run(["kubectl","-n",NS_DASH,"create","configmap","loki-dashboard",
                    "--from-file=loki-dashboard.json=/tmp/loki-dashboard.json",
                    "--dry-run=client","-o","yaml"], stdout=fh, stderr=subprocess.DEVNULL)
print(subprocess.run(["kubectl","apply","-f","/tmp/cm.yaml"],capture_output=True,text=True).stdout.strip())
subprocess.run(["kubectl","-n",NS_DASH,"label","configmap","loki-dashboard","grafana_dashboard=1","--overwrite"],capture_output=True,text=True)
time.sleep(45)
d = grafana_api("/api/dashboards/uid/wxq-loki-overview")
if d:
    dd = d["dashboard"]
    print("Grafana: 《%s》面板=%d 变量=%s minInterval=%s" % (
        dd["title"], len(dd["panels"]), [v["name"] for v in dd["templating"]["list"]], dd.get("minInterval")))
print("URL: http://10.100.10.10:32298/d/wxq-loki-overview")
