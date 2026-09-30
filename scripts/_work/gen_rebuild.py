#!/usr/bin/env python3
# 从 docker inspect 备份生成等价的 docker run 命令
import json, os, glob, shlex

OUT = "/deploy/crash-recovery"

def gen(path):
    d = json.load(open(path))[0]
    name = d["Name"].lstrip("/")
    hc = d.get("HostConfig", {})
    cfg = d.get("Config", {})
    lines = [f"# ===== {name} =====", "# 由 docker inspect 备份自动生成"]
    cmd = ["docker", "run", "-d", "--name", name]

    # 镜像
    img = cfg.get("Image")
    # 重启策略
    rp = hc.get("RestartPolicy", {})
    if rp.get("Name"):
        cmd += ["--restart", rp["Name"] + (":" + str(rp["MaximumRetryCount"]) if rp.get("MaximumRetryCount") else "")]

    # 网络
    nets = (d.get("NetworkSettings") or {}).get("Networks") or {}
    nm = hc.get("NetworkMode")
    if nm and nm not in ("default",):
        cmd += ["--network", nm]
        for n, v in nets.items():
            ip = v.get("IPAddress")
            if ip and n != "host":
                cmd += ["--ip", ip]

    if hc.get("Privileged"):
        cmd += ["--privileged"]
    if hc.get("Runtime") and hc["Runtime"] != "runc":
        cmd += ["--runtime", hc["Runtime"]]
    if cfg.get("User"):
        cmd += ["--user", cfg["User"]]
    if cfg.get("WorkingDir"):
        cmd += ["-w", cfg["WorkingDir"]]

    for g in (hc.get("GroupAdd") or []):
        cmd += ["--group-add", str(g)]
    for s in (hc.get("SecurityOpt") or []):
        cmd += ["--security-opt", s]
    if hc.get("ShmSize"):
        cmd += ["--shm-size", str(hc["ShmSize"])]
    for u in (hc.get("Ulimits") or []):
        cmd += ["--ulimit", f"{u['Name']}={u['Soft']}:{u['Hard']}"]
    for dev in (hc.get("Devices") or []):
        cmd += ["--device", f"{dev['PathOnHost']}:{dev['PathInContainer']}"]

    # 端口
    for cp, binds in (hc.get("PortBindings") or {}).items():
        for b in binds:
            hp = b.get("HostPort")
            cmd += ["-p", f"{hp}:{cp}"] if hp else ["-p", cp]

    # 环境变量
    for e in (cfg.get("Env") or []):
        if e.split("=")[0] in ("PATH", "LD_LIBRARY_PATH"):
            continue
        cmd += ["-e", e]

    # 挂载
    for b in (hc.get("Binds") or []):
        parts = b.split(":")
        mode = parts[2] if len(parts) > 2 else "rw"
        cmd += ["-v", f"{parts[0]}:{parts[1]}:{mode}"]

    # 入口/命令
    if cfg.get("Entrypoint"):
        ep = cfg["Entrypoint"]
        cmd += ["--entrypoint", ep[0] if isinstance(ep, list) else ep]
    if cfg.get("Cmd"):
        c = cfg["Cmd"]
        cmd += c if isinstance(c, list) else [c]

    lines.append(" \\\n  ".join(shlex.quote(x) if (" " in x or "'" in x) else x for x in cmd))
    return "\n".join(lines), name, img

out = []
for f in sorted(glob.glob(os.path.join(OUT, "inspect-*.json"))):
    txt, name, img = gen(f)
    out.append(txt)
    print(f"已生成: {name}  <- {img}")

open(os.path.join(OUT, "rebuild-commands.sh"), "w").write(
    "#!/bin/bash\n# 容器重建命令（数据均在宿主机 bind mount，不受影响）\n\n" + "\n\n".join(out) + "\n")
print("\n已写入:", os.path.join(OUT, "rebuild-commands.sh"))
