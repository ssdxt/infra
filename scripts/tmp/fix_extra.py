import io, sys

path = "/ManualAI/OmniKnow/omniknow2/assistant/conf.yaml"
with io.open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

fixed = False
out = []
for ln in lines:
    if ln.startswith("  extra_body:"):
        out.append('  extra_body: {"thinking": {"type": "disabled"}}\n')
        fixed = True
    else:
        out.append(ln)

if not fixed:
    # insert after the BASIC_MODEL block's max_retries line
    for i, ln in enumerate(lines):
        if ln.startswith("  max_retries:") and i + 1 < len(lines) and not lines[i+1].strip():
            out = []
            for j, l2 in enumerate(lines):
                out.append(l2)
                if j == i:
                    out.append('  extra_body: {"thinking": {"type": "disabled"}}\n')
            fixed = True
            break

with io.open(path, "w", encoding="utf-8") as f:
    f.writelines(out)

import yaml
d = yaml.safe_load(open(path, encoding="utf-8"))
bm = d.get("BASIC_MODEL", {})
print("fixed =", fixed)
print("BASIC_MODEL =", bm)
