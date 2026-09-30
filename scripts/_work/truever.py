#!/usr/bin/env python3
"""读取每个混装包在磁盘上的真实版本（不依赖 dist-info）"""
import os, re, glob

PKG = "/root/anaconda3/envs/recovery/lib/python3.8/site-packages"

TARGETS = ["transformers","tokenizers","torch","torchvision","langchain","langchain-core",
           "langchain-community","starlette","pydantic","fastapi","charset-normalizer",
           "numpy","requests","huggingface-hub","sentence-transformers","faiss-cpu",
           "langsmith","sqlalchemy","openai","pymupdf","ultralytics","opencv-python",
           "cryptography","paddlepaddle","lmdb","lxml","packaging","python-multipart"]

VER_RE = re.compile(r"""^__version__\s*=\s*['"]([^'"]+)['"]""", re.M)

def find_version(name):
    base = name.lower().replace("-", "_")
    for cand in (base, name.replace("-", "_"), name):
        d = os.path.join(PKG, cand)
        if not os.path.isdir(d):
            continue
        for fn in ("__init__.py", "version.py", "_version.py", "VERSION"):
            p = os.path.join(d, fn)
            if os.path.isfile(p):
                try:
                    txt = open(p, encoding="utf-8", errors="ignore").read()
                except Exception:
                    continue
                m = VER_RE.search(txt)
                if m:
                    return f"{m.group(1)}   ({cand}/{fn})"
                m2 = re.search(r"""version\s*=\s*['"]([^'"]+)['"]""", txt)
                if m2 and fn != "__init__.py":
                    return f"{m2.group(1)}   ({cand}/{fn})"
        # 特殊: transformers/utils/versions.py 里的 __version__
        for sub in ("utils/versions.py",):
            p = os.path.join(d, sub)
            if os.path.isfile(p):
                txt = open(p, encoding="utf-8", errors="ignore").read()
                m = VER_RE.search(txt)
                if m:
                    return f"{m.group(1)}   ({cand}/{sub})"
    return "<无法确定>"

print(f"{'包名':26} {'磁盘上的真实版本':30} {'dist-info 版本'}")
print("-" * 96)
for t in TARGETS:
    infos = sorted(os.path.basename(p)[:-len(".dist-info")]
                   for p in glob.glob(os.path.join(PKG, t.replace("-", "_") + "-*.dist-info"))
                   + glob.glob(os.path.join(PKG, t + "-*.dist-info")))
    print(f"{t:26} {find_version(t):30} {infos}")

print()
print("=== transformers 对 tokenizers 的要求 ===")
for f in ("dependency_versions_table.py", "utils/versions.py"):
    p = os.path.join(PKG, "transformers", f)
    if os.path.isfile(p):
        for line in open(p, encoding="utf-8", errors="ignore"):
            if "tokenizers" in line and ("0." in line or ">" in line):
                print(f"  [{f}] {line.strip()[:120]}")
