#!/usr/bin/env python3
# 组装 infra 仓库：kk-full(消毒) + scripts(消毒) + cilium(占位)，git 初始化
import os, re, shutil, subprocess, sys

SRC = r"C:\Users\CC\Desktop\dsh"
REPO = r"C:\Users\CC\Desktop\dsh\infra-repo"

SECRETS = [
    ("<ROOT_PASSWORD>", "<ROOT_PASSWORD>"),
    ("<HARBOR_PASSWORD>", "<HARBOR_PASSWORD>"),
    ("<ARGOCD_INITIAL_PASSWORD>", "<ARGOCD_INITIAL_PASSWORD>"),
    ("<DINGTALK_TOKEN>", "<DINGTALK_TOKEN>"),
    ("<DINGTALK_SECRET>", "<DINGTALK_SECRET>"),
    ("<DINGTALK_TOKEN>", "<DINGTALK_TOKEN>"),
    ("<DINGTALK_SECRET>", "<DINGTALK_SECRET>"),
    ("admin / <GRAFANA_PASSWORD>", "admin / <GRAFANA_PASSWORD>"),
]

def sanitize(text):
    for a, b in SECRETS:
        text = text.replace(a, b)
    return text

# 1) 复制 kk-full（消毒）
dst_kk = os.path.join(REPO, "kk-full")
if os.path.exists(dst_kk): shutil.rmtree(dst_kk)
n = 0
for root, dirs, files in os.walk(os.path.join(SRC, "kk-full")):
    dirs[:] = [x for x in dirs if x not in (".git",)]
    rel = os.path.relpath(root, os.path.join(SRC, "kk-full"))
    target = os.path.join(dst_kk, rel)
    os.makedirs(target, exist_ok=True)
    for f in files:
        sp, dp = os.path.join(root, f), os.path.join(target, f)
        try:
            txt = open(sp, encoding="utf-8", errors="replace").read()
            open(dp, "w", encoding="utf-8", newline="\n").write(sanitize(txt))
        except Exception:
            shutil.copy2(sp, dp)
        n += 1
print(f"kk-full 已复制并消毒: {n} 个文件")

# 2) scripts（ssdxt 关键脚本消毒）
dst_sc = os.path.join(REPO, "scripts")
if os.path.exists(dst_sc): shutil.rmtree(dst_sc)
# 从本地已有的脚本里收集（工作区没有完整 ssdxt，取 D 盘工作区已有的 + 由用户后续补 /data1/ssdxt 全量）
count = 0
for root, dirs, files in os.walk(SRC):
    dirs[:] = [x for x in dirs if x not in (".git", "infra-repo", "kk-full", "oneclick")]
    for f in files:
        if not f.endswith((".sh", ".py", ".yaml", ".yml", ".json", ".md", ".conf", ".cmd")): continue
        sp = os.path.join(root, f)
        rel = os.path.relpath(sp, SRC)
        if rel.startswith(("attach", "oneclick")): continue
        dp = os.path.join(dst_sc, rel)
        os.makedirs(os.path.dirname(dp), exist_ok=True)
        try:
            txt = open(sp, encoding="utf-8", errors="replace").read()
            open(dp, "w", encoding="utf-8", newline="\n").write(sanitize(txt))
        except Exception:
            continue
        count += 1
print(f"scripts 已复制并消毒: {count} 个文件")

# 3) README
open(os.path.join(REPO, "README.md"), "w", encoding="utf-8").write(
"""# infra-full — 离线 K8s 集群完整部署与复刻仓库

- `kk-full/` —— 按技术栈分类的完整部署与调整手册（含全新环境端到端复刻手册 99-）
- `scripts/` —— 全部幂等脚本（每个脚本可重复执行，改动前自动备份）

> 凭据已脱敏为 `<占位符>`，真实值请从安全渠道获取。
> 端到端复刻入口：[kk-full/99-全新环境复刻手册.md](kk-full/99-全新环境复刻手册.md)
""")

# 4) git 初始化
def git(*a):
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True)

print(git("init", "-b", "main").stdout.strip() or "git init ok")
git("config", "user.name", "ssdxt")
git("config", "user.email", "ssdxt@users.noreply.github.com")
git("config", "http.proxy", "http://127.0.0.1:12450")
git("add", "-A")
r = git("commit", "-m", "init: kk-full 文档总集 + 幂等脚本（凭据已脱敏）")
print(r.stdout.strip()[:200] or r.stderr.strip()[:200])
git("remote", "add", "origin", "https://github.com/ssdxt/infra.git")
r = git("push", "-u", "origin", "main")
print("PUSH:", (r.stdout + r.stderr).strip()[:400])
