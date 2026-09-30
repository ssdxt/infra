#!/usr/bin/env python3
import json, glob, os
OUT = "/deploy/crash-recovery"
for f in sorted(glob.glob(os.path.join(OUT, "inspect-*.json"))):
    d = json.load(open(f))[0]
    n = d["Name"].lstrip("/")
    cfg = d["Config"]; hc = d["HostConfig"]
    print(f"===== {n} =====")
    print("  Image      :", cfg.get("Image"))
    print("  Entrypoint :", cfg.get("Entrypoint"))
    print("  Cmd        :", cfg.get("Cmd"))
    print("  User       :", cfg.get("User"))
    print("  WorkingDir :", cfg.get("WorkingDir"))
    print("  NetworkMode:", hc.get("NetworkMode"))
    nets = (d.get("NetworkSettings") or {}).get("Networks") or {}
    print("  Networks   :", {k: v.get("IPAddress") for k, v in nets.items()})
    print("  Privileged :", hc.get("Privileged"))
    print("  Runtime    :", hc.get("Runtime"))
    print("  Binds      :", len(hc.get("Binds") or []))
    print()
