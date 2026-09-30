#!/usr/bin/env python3
# v2：限定 scripts 范围 + subprocess 用 utf-8 解码 + 尝试推送
import os, re, shutil, subprocess

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
def sanitize(t):
    for a, b in SECRETS: t = t.replace(a, b)
    return t

def run(args, cwd=None):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "") + (r.stderr or "")

# 1) 清掉误收的 scripts，改为白名单复制
sc = os.path.join(REPO, "scripts")
if os.path.exists(sc): shutil.rmtree(sc)
ALLOW_PREFIX = ("etcd-", "fix-", "loki", "plant01", "install-", "remove-", "restore-",
                "expose-", "verify-", "diag-", "check-", "build-", "make-", "compose-",
                "emergency", "05-", "04-", "03-", "02-", "01-")
count = 0
for f in sorted(os.listdir(SRC)):
    if not f.endswith((".sh", ".py", ".md")): continue
    if not f.startswith(ALLOW_PREFIX): continue
    dp = os.path.join(sc, f)
    os.makedirs(sc, exist_ok=True)
    txt = open(os.path.join(SRC, f), encoding="utf-8", errors="replace").read()
    open(dp, "w", encoding="utf-8", newline="\n").write(sanitize(txt))
    count += 1
# logging 目录（loki/adapter 资产）
logging_src = os.path.join(SRC, "logging")
logging_dst = os.path.join(REPO, "logging")
if os.path.exists(logging_dst): shutil.rmtree(logging_dst)
shutil.copytree(logging_src, logging_dst)
for root, _, files in os.walk(logging_dst):
    for f in files:
        p = os.path.join(root, f)
        if f.endswith((".md", ".py", ".sh", ".yaml", ".json")):
            open(p, "w", encoding="utf-8", newline="\n").write(sanitize(open(p, encoding="utf-8", errors="replace").read()))
print(f"scripts(白名单)={count}  logging 目录已收编")

# 2) git 提交 + 推送
r = run(["git", "add", "-A"], REPO)
r = run(["git", "commit", "-m", "init: kk-full 文档总集 + 运维脚本集（凭据已脱敏）"], REPO)
print("commit:", (r or "").strip().splitlines()[-1] if r else "ok")
r = run(["git", "remote", "remove", "origin"], REPO)
r = run(["git", "remote", "add", "origin", "https://github.com/ssdxt/infra.git"], REPO)
r = run(["git", "config", "http.proxy", "http://127.0.0.1:12450"], REPO)
r = run(["git", "push", "-u", "origin", "main"], REPO)
print("PUSH 结果:")
print((r or "(空)").strip()[:500])
if "Authentication" in r or "403" in r or "could not read" in r.lower():
    print("\n👉 需要 GitHub 授权：Settings → Developer settings → PAT(Fine-grained) 授权 ssdxt/infra 写权限，")
    print("   然后执行：git -C C:\\Users\\CC\\Desktop\\dsh\\infra-repo push -u origin main  （浏览器弹窗登录即可）")
