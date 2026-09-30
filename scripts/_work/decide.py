#!/usr/bin/env python3
"""用 RECORD 的 sha256 匹配数判定每个混装包「磁盘上实际是哪个版本」。只读。"""
import os, re, csv, hashlib, base64, collections

PKG = "/root/anaconda3/envs/recovery/lib/python3.8/site-packages"
pat = re.compile(r"^(?P<name>.+?)-(?P<ver>\d[^-]*)\.dist-info$")
groups = collections.defaultdict(list)
for d in os.listdir(PKG):
    m = pat.match(d)
    if m:
        groups[m.group("name").lower().replace("_", "-")].append((m.group("ver"), d))

def sha256(p):
    h = hashlib.sha256()
    try:
        with open(p, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
    except Exception:
        return None
    return "sha256=" + base64.urlsafe_b64encode(h.digest()).decode().rstrip("=")

def score(dist):
    """返回 (hash匹配数, 存在但hash不符, 缺失, 记录总数)"""
    ok = bad = miss = 0
    p = os.path.join(PKG, dist, "RECORD")
    try:
        rows = list(csv.reader(open(p, newline="")))
    except Exception:
        return (0, 0, 0, 0)
    for row in rows:
        if not row or not row[0] or row[0].endswith(".dist-info/RECORD"):
            continue
        rel = row[0]
        if rel.startswith("..") or rel.startswith("/"):
            continue
        fp = os.path.join(PKG, rel)
        if not os.path.exists(fp):
            miss += 1
        elif len(row) > 1 and row[1].startswith("sha256="):
            if sha256(fp) == row[1]:
                ok += 1
            else:
                bad += 1
        else:
            ok += 1     # 无 hash 记录，按存在计
    return (ok, bad, miss, ok + bad + miss)

print(f"{'包名':26} {'版本':16} {'hash匹配':>8} {'不符':>6} {'缺失':>6} {'记录':>6}  判定")
print("-" * 92)
decisions = {}
for name, vers in sorted(groups.items()):
    if len(vers) < 2:
        continue
    vers = sorted(set(vers))          # 去掉重复目录名
    if len(vers) < 2:
        continue
    res = [(score(d), v, d) for v, d in vers]
    res.sort(key=lambda x: (-x[0][0], x[0][2]))
    best = res[0]
    decisions[name] = best[2]
    for i, (sc, v, d) in enumerate(res):
        mark = "  <== 保留" if i == 0 else ""
        print(f"{name if i==0 else '':26} {v:16} {sc[0]:>8} {sc[1]:>6} {sc[2]:>6} {sc[3]:>6}{mark}")

import json
json.dump(decisions, open("/tmp/decisions.json", "w"), indent=1)
print(f"\n共判定 {len(decisions)} 个包，结果写入 /tmp/decisions.json")
