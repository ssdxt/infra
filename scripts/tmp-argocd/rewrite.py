#!/usr/bin/env python3
import re, sys

MAPPING = {
    "quay.io/argoproj/argocd": "harbor.wuxing.local/argocd/argocd",
    "public.ecr.aws/docker/library/redis": "harbor.wuxing.local/argocd/redis",
    "docker.io/library/redis": "harbor.wuxing.local/argocd/redis",
    "ghcr.io/dexidp/dex": "harbor.wuxing.local/argocd/dex",
}

src = "/tmp/argocd-install.yaml"
dst = "/tmp/argocd-install-harbor.yaml"
pat = re.compile(r'^(\s*-?\s*image:\s*)(\S+)\s*$')
replaced = []
with open(src) as f, open(dst, "w") as out:
    for line in f:
        m = pat.match(line.rstrip("\n"))
        if m:
            img = m.group(2)
            repo, _, tag = img.rpartition(":")
            if repo in MAPPING:
                new = f"{MAPPING[repo]}:{tag}"
                out.write(f"{m.group(1)}{new}\n")
                replaced.append((img, new))
            else:
                out.write(line)
                print("UNMAPPED IMAGE:", img, file=sys.stderr)
        else:
            out.write(line)
seen = {}
for old, new in replaced:
    seen[old] = new
for old, new in sorted(seen.items()):
    print(f"{old} -> {new}  (x{sum(1 for o,_ in replaced if o==old)})")
