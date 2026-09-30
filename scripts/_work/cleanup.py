#!/usr/bin/env python3
"""混合版本包清理器 —— 默认 dry-run，只报告不删除。
用法: python3 cleanup.py            # dry-run
      python3 cleanup.py --apply    # 真正执行（会先备份到 BK）
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

def read_record(dist):
    recs = {}
    p = os.path.join(PKG, dist, "RECORD")
    try:
        with open(p, newline="") as f:
            for row in csv.reader(f):
                if row and row[0]:
                    recs[row[0]] = row[1] if len(row) > 1 else ""
    except Exception:
        pass
    return recs

def top_dirs(rec):
    """从 RECORD 提取顶层包目录名"""
    out = set()
    for k in rec:
        if k.endswith(".dist-info/RECORD") or k.startswith("..") or "/" not in k:
            continue
        out.add(k.split("/")[0])
    return {d for d in out if not d.endswith(".dist-info") and not d.endswith(".data")}

def scan_dir(d):
    files = set()
    if not os.path.isdir(d):
        return files
    for root, _, fs in os.walk(d):
        if "__pycache__" in root:
            continue
        for fn in fs:
            files.add(os.path.relpath(os.path.join(root, fn), PKG))
    return files

report, plan = [], []
for name, vers in sorted(groups.items()):
    if len(vers) < 2:
        continue
    infos = []
    for ver, dist in vers:
        rec = read_record(dist)
        tds = top_dirs(rec)
        files = set()
        for td in tds:
            files |= scan_dir(os.path.join(PKG, td))
        in_rec = files & set(rec)
        not_in = files - set(rec)
        infos.append((len(in_rec) - len(not_in), ver, dist, rec, tds, files, in_rec, not_in))
    infos.sort(key=lambda x: -x[0])
    keep = infos[0]
    drop = infos[1:]
    keep_score, keep_ver, keep_dist, keep_rec, keep_tds, disk_files, in_rec, not_in = keep
    drop_files, drop_dists = set(), []
    for _, dv, dd, drec, dtds, _, _, _ in drop:
        # 只删不在保留版本 RECORD 里的文件
        for d in dtds:
            for f in scan_dir(os.path.join(PKG, d)):
                if f not in keep_rec:
                    drop_files.add(f)
        drop_dists.append(dd)
    gone = [f for f in disk_files if f not in keep_rec]
    report.append((name, keep_ver, [d[1] for d in drop], len(gone), len(drop_dists)))
    plan.append({"name": name, "keep_ver": keep_ver, "keep_dist": keep_dist,
                 "drop_dists": drop_dists, "drop_files": sorted(set(gone) | drop_files)})

os.makedirs(BK, exist_ok=True)
with open(os.path.join(BK, "cleanup-plan.json"), "w") as f:
    json.dump(plan, f, indent=1, ensure_ascii=False)

print(f"{'包名':28} {'保留':16} {'剔除':16} {'删文件':>6} {'删dist':>6}")
print("-" * 78)
tf = td = 0
for name, kv, dv, nf, nd in report:
    print(f"{name:28} {kv:16} {','.join(dv):16} {nf:>6} {nd:>6}")
    tf += nf; td += nd
print("-" * 78)
print(f"合计: 删除 {tf} 个文件、{td} 个 dist-info")
print(f"计划已写入: {BK}/cleanup-plan.json")
print(f"模式: {'【APPLY 实际执行】' if APPLY else '【dry-run 只报告】'}")

if APPLY:
    done_f = done_d = 0
    for p in plan:
        for f in p["drop_files"]:
            src = os.path.join(PKG, f)
            if os.path.exists(src):
                dst = os.path.join(BK, "files", f)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                try:
                    shutil.move(src, dst); done_f += 1
                except Exception as e:
                    print("  移动失败:", f, e)
        for dd in p["drop_dists"]:
            src = os.path.join(PKG, dd)
            if os.path.isdir(src):
                try:
                    shutil.move(src, os.path.join(BK, "dists", dd)); done_d += 1
                except Exception as e:
                    print("  移动失败:", dd, e)
    print(f"\n已移动 {done_f} 个文件、{done_d} 个 dist-info 到 {BK}")
