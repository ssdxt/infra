#!/bin/bash
python3 - <<'PYEOF'
import json, urllib.request

def try_login(am, password="admin", extra=None):
    body = {"name": "admin", "password": password, "authMethod": am, "language": "zh"}
    if extra: body.update(extra)
    data = json.dumps(body).encode()
    req = urllib.request.Request("http://127.0.0.1:9999/api/v1/auth/login",
                                 data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status, r.read().decode()[:300]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]
    except Exception as e:
        return "ERR", str(e)

for am in ["session", "jwt"]:
    print(f"authMethod={am!r}:", try_login(am))
PYEOF
