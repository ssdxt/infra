#!/bin/bash
echo "=== python3 是否可用 ==="
which python3
echo "=== /opt/1panel/db 内容 ==="
ls -la /opt/1panel/db/
echo "=== /opt/1panel/conf 内容 ==="
ls -la /opt/1panel/conf/
echo "=== app.yaml 关键配置 ==="
grep -vE '^\s*#|^\s*$' /opt/1panel/conf/app.yaml 2>/dev/null | head -60
echo "=== /usr/local/bin 下 1p 相关 ==="
ls -la /usr/local/bin/ | grep -i '1p\|panel'
echo "=== 1panel 数据库 users 表 ==="
python3 - <<'PYEOF'
import sqlite3, os
p = '/opt/1panel/db/1Panel.db'
print("db exists:", os.path.exists(p))
try:
    con = sqlite3.connect(p)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print("tables:", [r[0] for r in cur.fetchall()])
    cur.execute("SELECT id,username,email,role,status FROM users")
    for row in cur.fetchall():
        print("USER:", row)
    cur.execute("PRAGMA table_info(users)")
    print("users cols:", [r[1] for r in cur.fetchall()])
    con.close()
except Exception as e:
    print("ERROR:", e)
PYEOF
echo "=== 各应用 .env 中的账号密码类配置 ==="
for f in /opt/1panel/apps/local/holaros/holaros/.env /opt/1panel/apps/local/holarkanban/HolarKanban/.env /opt/1panel/apps/local/holartts/holartts/.env /data/aippt/.env /root/apps/docker/holarchat/.env /root/work/holarvm/.env /root/asr_work/holarasr_online/.env; do
  echo "--- $f ---"
  grep -iE 'pass|user|account|secret|token|key|pwd|login|admin' "$f" 2>/dev/null | sed 's/^/    /'
done
