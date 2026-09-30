#!/usr/bin/env python3
import json, subprocess, urllib.parse, datetime, re, collections, time

def loki(path, params=None):
    url = "http://localhost:3100" + path + ("?" + urllib.parse.urlencode(params) if params else "")
    r = subprocess.run(["kubectl","-n","logging","exec","loki-0","-c","loki","--","wget","-qO-",url],
                       capture_output=True, text=True)
    try: return json.loads(r.stdout)
    except Exception: return {"data":{"result":[]}}

NOW = int(datetime.datetime.now().timestamp()*1e9)

print("===== 1. tetragon 608条/5m 错误内容分类（修正解析）=====")
d = loki("/loki/api/v1/query_range", {
    "query": '{namespace="tetragon"} |~ "(?i)error"',
    "start": NOW - 600*10**9, "end": NOW, "limit": 100})
try:
    cnt = collections.Counter(); sample = {}
    for s in d["data"]["result"]:
        st = s.get("stream", {})
        pod = st.get("pod", "?"); con = st.get("container", "?")
        for ts, line in s["values"]:
            m = re.search(r'(msg="[^"]{0,70}|level=\w+[^"]{0,60}|"error"[^}]{0,60})', line)
            key = re.sub(r"[\d.]{5,}", "N", (m.group(1) if m else line[:60]))
            cnt[(con, key)] += 1
            sample.setdefault((con, key), line[:150])
    for (con, key), n in cnt.most_common(6):
        print("  %4d 条  [%s/%s] %s" % (n, con, pod if False else "", key))
        print("           例:", sample[(con,key)][:140])
except Exception as e: print("  失败:", e, str(d)[:120])

print("")
print("===== 2. CoreDNS 根治：外部域名 NXDOMAIN 秒回 =====")
raw = subprocess.run(["kubectl","-n","kube-system","get","cm","coredns","-o","json"],
                     capture_output=True, text=True).stdout
d = json.loads(raw)
corefile = d["data"]["Corefile"]
if "template IN ANY" in corefile:
    print("  已是 NXDOMAIN 模式，跳过")
else:
    ts = datetime.datetime.now().strftime("%m%d-%H%M")
    subprocess.run(["kubectl","-n","kube-system","get","cm","coredns","-o","yaml"],
                   capture_output=True, text=True,
                   stdout=open(f"/tmp/coredns-bak-{ts}.yaml","w"))
    new = corefile.replace(
        "        forward . /etc/resolv.conf",
        "        template IN ANY . {\n"
        "          rcode NXDOMAIN\n"
        "          authority \"offline.cluster\"\n"
        "        }")
    if new == corefile:
        print("  ⚠️ 未匹配到 forward 行，Corefile 原文（前30行）：")
        print("\n".join(corefile.split("\n")[:30]))
    else:
        d["data"]["Corefile"] = new
        json.dump(d, open("/tmp/coredns-new.json","w"), ensure_ascii=False)
        r = subprocess.run(["kubectl","apply","-f","/tmp/coredns-new.json"],
                           capture_output=True, text=True)
        print(" ", (r.stdout or r.stderr).strip())

print("")
print("===== 3. 等 40 秒（CoreDNS reload）后验证 =====")
subprocess.run(["kubectl","-n","kube-system","rollout","restart","deploy/coredns"])
subprocess.run(["kubectl","-n","kube-system","rollout","status","deploy/coredns","--timeout=180s"],
               capture_output=True, text=True)
time.sleep(5)

# 集群内 DNS 正常验证
r = subprocess.run(["kubectl","-n","default","run","dnstest","--rm","-i","--restart=Never",
                    "--image=harbor.wuxing.local/library/nginx:1.27-alpine","--command","--","sh","-c",
                    "nslookup kubernetes.default.svc.cluster.local; nslookup www.baidu.com; echo DONE"],
                   capture_output=True, text=True, timeout=120)
for ln in r.stdout.split("\n"):
    if any(k in ln for k in ["Address", "NXDOMAIN", "server can", "DONE", "Serv"]):
        print("  ", ln.strip())

print("")
print("===== 4. 等 60 秒看错误是否消失 =====")
time.sleep(60)
NOW2 = int(datetime.datetime.now().timestamp()*1e9)
d = loki("/loki/api/v1/query", {"query": 'sum by (pod) (count_over_time({namespace="kube-system"} |~ "(?i)error" [2m]))'})
try:
    res = d["data"]["result"]
    if not res: print("  ✅ kube-system 错误 = 0")
    for r in res[:5]:
        print("  %-42s %6.0f 条/2min" % (r["metric"].get("pod"), float(r["value"][1])))
except Exception as e: print("  失败", e)