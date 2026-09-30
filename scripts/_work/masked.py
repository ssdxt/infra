#!/usr/bin/env python3
import json
d = json.load(open("/deploy/crash-recovery/inspect-bge-m3-npu.json"))[0]
hc = d["HostConfig"]
for k in ["Privileged", "SecurityOpt", "MaskedPaths", "ReadonlyPaths", "CapAdd", "CapDrop", "Devices"]:
    print(f"{k:16}: {hc.get(k)}")
print()
print("Config.User   :", d["Config"].get("User"))
print("AppArmorProfile:", hc.get("AppArmorProfile"))
print("SeccompMode   :", hc.get("SeccompMode"))
