#!/usr/bin/env python3
"""
Loki 日志便捷查询工具（在本机或 control-01 上运行，自动走 kubectl exec）

用法:
  python3 logq.py '<LogQL>' [条数] [起始时间]
  python3 logq.py -s '<统计LogQL>' [时间窗]

例子:
  python3 logq.py '{namespace="kube-system"} |= "error"'
  python3 logq.py '{namespace="longhorn-system", stream="stderr"}' 20 2h
  python3 logq.py -s 'sum by (pod) (count_over_time({namespace="kube-system"} |= "error" [5m]))' 1h
  python3 logq.py -l                                        # 列出所有标签
  python3 logq.py -n                                        # 各命名空间日志量
"""
import datetime, json, subprocess, sys, urllib.parse

NS, POD, CONTAINER = "logging", "loki-0", "loki"
BASE = "http://localhost:3100"


def api(path, params=None):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    r = subprocess.run(
        ["kubectl", "-n", NS, "exec", POD, "-c", CONTAINER, "--", "wget", "-qO-", url],
        capture_output=True, text=True)
    if not r.stdout.strip():
        print("查询返回空。stderr:", r.stderr.strip()[:200]); sys.exit(1)
    try:
        return json.loads(r.stdout)
    except Exception:
        print("解析失败，原始输出:", r.stdout[:300]); sys.exit(1)


def ns_ago(s):
    n, unit = int(s[:-1]), s[-1]
    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
    return int((datetime.datetime.now().timestamp() - n * mult) * 1e9)


def fmt_ts(ns):
    return datetime.datetime.fromtimestamp(int(ns) / 1e9).strftime("%m-%d %H:%M:%S")


def show_logs(query, limit=20, since="1h"):
    d = api("/loki/api/v1/query_range", {
        "query": query, "limit": limit,
        "start": ns_ago(since), "end": int(datetime.datetime.now().timestamp() * 1e9),
    })
    res = d.get("data", {}).get("result", [])
    if not res:
        print("（没有匹配的日志；试试放宽时间范围，例如把 1h 改成 24h）"); return
    total = 0
    for s in res[:limit]:
        m = s["stream"]
        print("\n\033[36m[%s/%s/%s] node=%s stream=%s\033[0m" % (
            m.get("namespace"), m.get("pod"), m.get("container"),
            m.get("node", "-"), m.get("stream", "-")))
        for v in s["values"][:3]:
            print("  %s  %s" % (fmt_ts(v[0]), v[1][:300]))
            total += 1
    print("\n共展示 %d 条（查询: %s，时间范围: 最近 %s）" % (total, query, since))


def show_stats(query, window="5m"):
    d = api("/loki/api/v1/query", {"query": query, "time": int(datetime.datetime.now().timestamp())})
    res = d.get("data", {}).get("result", [])
    if not res:
        print("（无统计结果）"); return
    print("统计结果（%s）:" % query)
    rows = []
    for r in res:
        label = ",".join("%s=%s" % (k, v) for k, v in sorted(r["metric"].items())) or "(total)"
        try:
            val = float(r["value"][1])
        except Exception:
            val = 0.0
        rows.append((val, label))
    for val, label in sorted(rows, reverse=True):
        print("  %-52s %s" % (label, ("%.0f" % val) if val == int(val) else val))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(0)
    if a[0] == "-l":
        d = api("/loki/api/v1/labels")
        print("可用标签:", ", ".join(d.get("data", [])))
    elif a[0] == "-n":
        show_stats('sum(count_over_time({namespace=~".+"}[5m])) by (namespace)')
    elif a[0] == "-s":
        show_stats(a[1], a[2] if len(a) > 2 else "5m")
    else:
        show_logs(a[0], int(a[1]) if len(a) > 1 else 20, a[2] if len(a) > 2 else "1h")
