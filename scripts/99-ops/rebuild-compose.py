#!/usr/bin/env python3
# 按运行中的容器事实，反向重建 plant01 的 docker-compose.yaml
# 输出: /data1/apps/wxq-plant01-monitor/docker-compose.reconstructed.yaml
import json, subprocess, sys

PROJ = "wxq-monitor"
OUT  = "/data1/apps/wxq-plant01-monitor/docker-compose.reconstructed.yaml"

def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True).stdout

def q(v):
    s = str(v)
    if s == "" or any(c in s for c in " :#{}[]&*!|>'\"%@`,"):
        return "'" + s.replace("'", "''") + "'"
    return s

# 收集容器
names = sh("docker","ps","-a","--format","{{.Names}}").split()
objs, missing_label = [], []
for n in names:
    try:
        d = json.loads(sh("docker","inspect",n))[0]
    except Exception:
        continue
    labs = d.get("Config",{}).get("Labels") or {}
    if labs.get("com.docker.compose.project") == PROJ:
        objs.append(d)
    elif n.startswith("wxq-"):
        missing_label.append(n)
        objs.append(d)   # 按名字兜底纳入（如被手工重建后丢了 compose 标签的）

print("发现 wxq-monitor 容器 %d 个" % len(objs))
if missing_label:
    print("⚠️ 这些容器已丢失 compose 标签（多半是被手工重建过）: %s" % ", ".join(missing_label))

vols, lines = {}, []
lines.append("name: %s" % PROJ)
lines.append("")
lines.append("services:")

for d in sorted(objs, key=lambda x: x["Name"]):
    cname = d["Name"].lstrip("/")
    labs  = d.get("Config",{}).get("Labels") or {}
    svc   = labs.get("com.docker.compose.service") or cname.replace("wxq-","",1)
    L = []
    L.append("")
    L.append("  %s:" % svc)
    L.append("    image: %s" % d["Config"]["Image"])
    L.append("    container_name: %s" % cname)

    args = [a for a in (d.get("Args") or []) if a]
    cmd  = [c for c in (d["Config"].get("Cmd") or []) if c]
    eff  = args if args else cmd
    if eff:
        L.append("    command:")
        for a in eff:
            L.append("      - %s" % q(a))

    env = []
    for e in (d["Config"].get("Env") or []):
        k = e.split("=",1)[0]
        if k in ("PATH","HOSTNAME","HOME","TERM"):
            continue
        env.append(e)
    if env:
        L.append("    environment:")
        for e in sorted(env):
            k,_,v = e.partition("=")
            L.append("      %s: %s" % (k, q(v)))

    # 端口
    pb = d["HostConfig"].get("PortBindings") or {}
    ports = []
    for cport, binds in sorted(pb.items()):
        for b in (binds or []):
            hp = b.get("HostPort")
            if hp:
                proto = cport.split("/")[-1] if "/" in cport else "tcp"
                cp = cport.split("/")[0]
                ports.append('"%s:%s"' % (hp, cp) if proto=="tcp" else '"%s:%s/%s"' % (hp,cp,proto))
    if ports:
        L.append("    ports:")
        for p in sorted(set(ports)):
            L.append("      - %s" % p)

    # 卷
    vlist = []
    for m in (d.get("Mounts") or []):
        if m.get("Type") == "bind":
            v = "%s:%s" % (m["Source"], m["Destination"])
            if not m.get("RW", True):
                v += ":ro"
            vlist.append(v)
        elif m.get("Type") == "volume":
            vname = m.get("Name") or ""
            vols[vname] = True
            short = vname.replace(PROJ+"_","",1)
            v = "%s:%s" % (short, m["Destination"])
            vlist.append(v)
    if vlist:
        L.append("    volumes:")
        for v in sorted(vlist):
            L.append("      - %s" % v)

    rp = (d["HostConfig"].get("RestartPolicy") or {}).get("Name")
    if rp:
        L.append("    restart: %s" % rp)

    # 网络 + 自定义别名
    nets = d.get("NetworkSettings",{}).get("Networks") or {}
    if nets:
        netname = list(nets.keys())[0]
        aliases = [a for a in (nets[netname].get("Aliases") or [])
                   if a not in (cname, cname.split("_")[0], svc)]
        if aliases:
            L.append("    networks:")
            L.append("      monitoring:")
            L.append("        aliases:")
            for a in sorted(set(aliases)):
                L.append("          - %s" % a)
        else:
            L.append("    networks: [monitoring]")
    lines += L

lines.append("")
lines.append("volumes:")
for v in sorted(vols):
    short = v.replace(PROJ+"_","",1)
    lines.append("  %s:" % short)
    lines.append("    name: %s" % v)
lines.append("")
lines.append("networks:")
lines.append("  monitoring:")
lines.append("    name: %s" % PROJ)

open(OUT,"w").write("\n".join(lines) + "\n")
print("已生成: %s (%d 行)" % (OUT, len(lines)))
