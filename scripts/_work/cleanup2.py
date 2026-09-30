#!/usr/bin/env python3
"""混合版本包清理器 v2
判据: 优先「RECORD hash 全部匹配(bad=0)」，其次匹配数多 —— 即磁盘上完好的那套。
默认 dry-run；--apply 才真正移动文件（全部备份）。
"""
import os, re, csv, hashlib, base64, collections, sys, shutil, json

PKG = "/root/anaconda3/envs/recovery/lib/python3.8/site-packages"
BK  = "/deploy/cc/logs/pkg-backup-20260914-093505/mixed-cleanup"
APPLY = "--apply" in sys.argv
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

def analyse(dist):
    ok = bad = 0
    files = []
    try:
        rows = list(csv.reader(open(os.path.join(PKG, dist, "RECORD"), newline="")))
    except Exception:
        return (0, 0, [])
    for row in rows:
        if not row or not row[0] or row[0].endswith(".dist-info/RECORD"):
            continue
        rel = row[0]
        if rel.startswith("..") or rel.startswith("/"):
            continue
        files.append(rel)
        fp = os.path.join(PKG, rel)
        if not os.path.exists(fp):
            bad += 1
        elif len(row) > 1 and row[1].startswith("sha256="):
            if sha256(fp) == row[1]:
                ok += 1
            else:
                bad += 1
        else:
            ok += 1
    return (ok, bad, files)

plan, summary = [], []
for name, vers in sorted(groups.items()):
    vers = sorted(set(vers))
    if len(vers) < 2:
        continue
    res = []
    for v, d in vers:
        ok, bad, files = analyse(d)
        res.append({"ver": v, "dist": d, "ok": ok, "bad": bad, "files": files})
    # 判据: bad 升序, ok 降序
    res.sort(key=lambda r: (r["bad"], -r["ok"]))
    keep, drop = res[0], res[1:]
    keep_set = set(keep["files"])
    drop_files = set()
    for dd in drop:
        for f in dd["files"]:
            if f not in keep_set:
                drop_files.add(f)
    summary.append((name, keep["ver"], keep["bad"], ",".join(d["ver"] for d in drop),
                    len(drop_files), len(drop)))
    plan.append({"name": name, "keep_ver": keep["ver"], "keep_dist": keep["dist"],
                 "drop_dists": [d["dist"] for d in drop],
                 "drop_files": sorted(drop_files)})

os.makedirs(BK, exist_ok=True)
json.dump(plan, open(os.path.join(BK, "cleanup-plan-v2.json"), "w"), indent=1, ensure_ascii=False)

print(f"{'包名':26} {'保留':16} {'bad':>4} {'剔除':16} {'删文件':>6} {'删dist':>6}")
print("-" * 82)
tf = td = 0
for name, kv, kb, dv, nf, nd in summary:
    print(f"{name:26} {kv:16} {kb:>4} {dv:16} {nf:>6} {nd:>6}")
    tf += nf; td += nd
print("-" * 82)
print(f"合计 {len(plan)} 个包: 删除 {tf} 个文件、{td} 个 dist-info")
print(f"模式: {'【APPLY】' if APPLY else '【dry-run】'}")

if APPLY:
    mf = md = 0
    for p in plan:
        for f in p["drop_files"]:
            src = os.path.join(PKG, f)
            if os.path.exists(src):
                dst = os.path.join(BK, "files", f)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                try: shutil.move(src, dst); mf += 1
                except Exception as e: print("  文件移动失败:", f, e)
        for dd in p["drop_dists"]:
            src = os.path.join(PKG, dd)
            if os.path.isdir(src):
                try: shutil.move(src, os.path.join(BK, "dists", dd)); md += 1
                except Exception as e: print("  dist 移动失败:", dd, e)
    print(f"\n已移动 {mf} 个文件、{md} 个 dist-info -> {BK}")
    print("回滚: 把 files/ 和 dists/ 里的内容移回 site-packages 即可")
