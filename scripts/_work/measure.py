#!/usr/bin/env python3
"""对每个多版本 dist-info 的包，用【基线版本 RECORD】做白名单，统计污染规模。
只读，不删任何文件。"""
import os, re, csv, hashlib, collections

PKG = "/root/anaconda3/envs/recovery/lib/python3.8/site-packages"
pat = re.compile(r"^(?P<name>.+?)-(?P<ver>\d[^-]*)\.dist-info$")

groups = collections.defaultdict(list)
for d in os.listdir(PKG):
    m = pat.match(d)
    if m:
        groups[m.group("name").lower().replace("_", "-")].append((m.group("ver"), d))

def read_record(dist):
    recs = {}
    p = os.path.join(PKG, dist, "RECORD")
    try:
        with open(p, newline="") as f:
            for row in csv.reader(f):
                if row and row[0] and not row[0].endswith(".dist-info/RECORD"):
                    recs[row[0]] = row[1] if len(row) > 1 else ""
    except Exception:
        pass
    return recs

def sha256(p):
    h = hashlib.sha256()
    try:
        with open(p, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        import base64
        return "sha256=" + base64.urlsafe_b64encode(h.digest()).decode().rstrip("=")
    except Exception:
        return None

rows = []
tot_extra = tot_changed = 0
for name, vers in sorted(groups.items()):
    if len(vers) < 2:
        continue
    # 基线 = dist-info 目录 mtime 最早的那个
    vers_sorted = sorted(vers, key=lambda v: os.path.getmtime(os.path.join(PKG, v[1])))
    base_ver, base_dist = vers_sorted[0]
    new_vers = [v for v, _ in vers_sorted[1:]]

    base_rec = read_record(base_dist)
    base_files = {p for p in base_rec
                  if p.startswith(name.replace("-", "_") + "/") or p.startswith(name + "/")}

    # 包目录
    pkgdirs = [os.path.join(PKG, name.replace("-", "_")), os.path.join(PKG, name)]
    pkgdir = next((d for d in pkgdirs if os.path.isdir(d)), None)

    extra = changed = 0
    if pkgdir:
        for root, _, files in os.walk(pkgdir):
            if "__pycache__" in root:
                continue
            for fn in files:
                fp = os.path.join(root, fn)
                rel = os.path.relpath(fp, PKG)
                if rel not in base_files:
                    extra += 1
                else:
                    want = base_rec.get(rel, "")
                    if want.startswith("sha256="):
                        got = sha256(fp)
                        if got and got != want:
                            changed += 1
    rows.append((name, base_ver, ",".join(new_vers), extra, changed))
    tot_extra += extra
    tot_changed += changed

print(f"{'包名':30} {'基线':14} {'新版':18} {'多余文件':>8} {'被覆盖':>7}")
print("-" * 84)
for name, bv, nv, ex, ch in rows:
    flag = "  <<<" if (ex or ch) else ""
    print(f"{name:30} {bv:14} {nv:18} {ex:>8} {ch:>7}{flag}")
print("-" * 84)
print(f"共 {len(rows)} 个包，多余文件 {tot_extra} 个，被新版覆盖的文件 {tot_changed} 个")
