#!/bin/bash
python3 - <<'PYEOF'
import urllib.request, re, json

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode("utf-8", "ignore")

try:
    html = get("http://127.0.0.1:9999/")
    print("index.html len:", len(html))
    # 找 JS 资源
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
    print("scripts:", scripts[:10])
    # 也直接在整个 html 里找 authMethod 相关
    for m in re.finditer(r'.{80}authMethod.{120}', html, re.S):
        print("HTML:", m.group(0)[:200].replace("\n", " "))
        break
    for s in scripts:
        url = s if s.startswith("http") else "http://127.0.0.1:9999" + ("" if s.startswith("/") else "/") + s
        js = get(url)
        print(f"\n== {s} len={len(js)} ==")
        for m in re.finditer(r'.{60}authMethod.{100}', js, re.S):
            txt = m.group(0).replace("\n", " ")
            print("  JS:", txt[:180])
            if len(list(re.finditer(r'authMethod', js))) > 0:
                pass
        hits = re.findall(r'oneof[^\"]{0,60}|webauthn|"otp"|"totp"|"2fa"|"mfa"', js)
        for h in set(hits):
            print("  HIT:", h[:80])
except Exception as e:
    print("ERR:", e)
PYEOF
