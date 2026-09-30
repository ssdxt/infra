#!/bin/bash
python3 - <<'PYEOF'
import json, urllib.request, sqlite3

url = "http://127.0.0.1:9999/api/v1/auth/login"
for am in ["otp", "webauthn", "local", ""]:
    body = json.dumps({"name": "admin", "password": "admin",
                       "authMethod": am, "language": "zh"}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            print(f"authMethod={am!r:12} -> HTTP {r.status} {r.read().decode()[:200]}")
    except urllib.error.HTTPError as e:
        print(f"authMethod={am!r:12} -> HTTP {e.code} {e.read().decode()[:200]}")
    except Exception as e:
        print(f"authMethod={am!r:12} -> ERR {e}")

print("\n=== settings 表内容 ===")
con = sqlite3.connect('/opt/1panel/db/1Panel.db')
cur = con.cursor()
cur.execute("SELECT key, value FROM settings")
for k, v in cur.fetchall():
    print(f"{k} = {v}")
con.close()
PYEOF
