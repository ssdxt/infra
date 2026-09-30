# -*- coding: utf-8 -*-
"""重新触发「试题/问答对生成」并等待结果（配合 regen_qa.sh 使用）

背景：knowledge_file.qa_status = 失败 的常见根因是 file_doc.doc_id 全为 NULL
（解析阶段写入的 metadata 与向量化阶段相比少一个 "id" 键，导致 update_docs_in_db()
匹配失败，doc_id 从未回填，KBService.list_docs() 返回空，generate_test_cases()
判为「未找到文档块」并把 qa_status 置为「失败」）。

修复步骤：
  1) 代码修复：server/db/repository/knowledge_file_repository.py 的 update_docs_in_db()
     已改为 key 子集匹配（备份 .bak-docid-20260918）；
  2) 历史数据回填：先跑 fix_doc_id.sh fix --apply [kb_name]；
  3) 本脚本：登录拿到 JWT -> 调用 /train/generate_test_cases -> 轮询 qa_status 直至终态。

用法：
  python regen_qa.py <kb_name> <file_name> [--user admin] [--password Abcd1234]
  # 不传 --user/--password 默认 admin / Abcd1234
"""

import argparse
import base64
import json
import os
import sys
import time

import pymysql
import requests
import urllib3

urllib3.disable_warnings()

BASE = os.getenv("API_BASE", "https://127.0.0.1:8261")


def _db_conf_from_env():
    """统一配置：优先解析环境变量 DB_URI（/deploy/deploy.env 注入），否则用默认值。"""
    uri = os.getenv("DB_URI", "")
    if uri.startswith("mysql"):
        from urllib.parse import urlparse, unquote
        u = urlparse(uri)
        return dict(host=u.hostname or "127.0.0.1",
                    port=u.port or 2881,
                    user=unquote(u.username or "root@test"),
                    password=unquote(u.password or "12345"),
                    database=(u.path or "/chat_doc").lstrip("/") or "chat_doc",
                    charset="utf8mb4")
    return dict(host="127.0.0.1", port=2881, user="root@test",
                password="12345", database="chat_doc", charset="utf8mb4")


DB_CONF = _db_conf_from_env()
POLL_INTERVAL = 5
MAX_WAIT = 3600


def login(username, password):
    ts = int(time.time() * 1000)
    enc = base64.b64encode(("%s_%s_%d" % (username, password, ts)).encode("utf-8")).decode("utf-8")
    r = requests.post(BASE + "/user/login",
                      json={"username": username, "password": enc}, verify=False, timeout=30)
    print("[login] http=%s" % r.status_code)
    if r.status_code != 200:
        print("[login] body=%s" % r.text[:500])
        sys.exit(2)
    d = r.json()
    if d.get("code") != 200:
        print("[login] code=%s msg=%s" % (d.get("code"), d.get("msg")))
        sys.exit(2)
    return d["data"]["token"]


def trigger(token, kb_name, file_name):
    h = {"token": token}
    payload = {"kb_name": kb_name, "file_name": file_name}
    t0 = time.time()
    r = requests.post(BASE + "/train/generate_test_cases", json=payload,
                      headers=h, verify=False, timeout=MAX_WAIT)
    print("[trigger] http=%s elapsed=%.1fs" % (r.status_code, time.time() - t0))
    print("[trigger] body=%s" % r.text[:800])


def wait_status(kb_name, file_name):
    conn = pymysql.connect(**DB_CONF)
    cur = conn.cursor()
    last = None
    deadline = time.time() + MAX_WAIT
    while time.time() < deadline:
        cur.execute("select qa_status, qa_count from knowledge_file "
                    "where kb_name=%s and file_name=%s",
                    (kb_name, file_name))
        row = cur.fetchone()
        if row is None:
            print("[wait] knowledge_file row not found for %s / %s" % (kb_name, file_name))
            break
        status, count = row
        if status != last:
            print("[wait] qa_status=%s qa_count=%s" % (status, count))
            last = status
        if status in ("已生成", "失败"):
            conn.close()
            return status, count
        time.sleep(POLL_INTERVAL)
    conn.close()
    return last, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kb_name")
    ap.add_argument("file_name")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", default="Abcd1234")
    args = ap.parse_args()

    token = login(args.user, args.password)
    trigger(token, args.kb_name, args.file_name)
    status, count = wait_status(args.kb_name, args.file_name)
    print("=== FINAL qa_status=%s qa_count=%s ===" % (status, count))
    if status == "已生成":
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
