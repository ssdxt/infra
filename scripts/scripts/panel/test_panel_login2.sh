#!/bin/bash
python3 - <<'PYEOF'
import json, urllib.request
url = "http://127.0.0.1:9999/api/v1/auth/login"
data = json.dumps({"name": "admin", "password": "admin",
                   "authMethod": "password", "language": "zh"}).encode()
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read().decode()
        print("HTTP", r.status)
        print(body[:600])
except urllib.error.HTTPError as e:
    print("HTTP", e.code)
    print(e.read().decode()[:600])
except Exception as e:
    print("ERR", e)
PYEOF
