#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# perf_test2.py - business layer: login + knowledge_base_chat (RAG full chain), concurrency=10
import base64, json, time, threading, statistics
import requests

API = "https://127.0.0.1:8261"
KB = "test"
QUERY = "what is the main topic of the documents"  # placeholder, replaced below
QUERY_B64 = "5ZGo5aW9MQ=="  # replaced at upload time if needed

import ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def b64s(s):
    return base64.b64encode(s.encode()).decode()

def do_login():
    # payload: base64(username_password_timestamp)
    ts = str(int(time.time() * 1000))
    pw = b64s("admin_Abcd1234_" + ts)
    t0 = time.time()
    try:
        r = requests.post(API + "/user/login", verify=False, timeout=30,
                          json={"username": "admin", "password": pw})
        dt = time.time() - t0
        j = r.json()
        tok = (j.get("data") or {}).get("token", "")
        return {"ok": r.status_code == 200 and bool(tok), "lat": dt, "token": tok}
    except Exception as e:
        return {"ok": False, "lat": time.time() - t0, "err": str(e)[:100]}

def do_chat(token, query, max_tokens=128):
    hdr = {"token": token, "Content-Type": "application/json"}
    t0 = time.time()
    try:
        r = requests.post(API + "/chat/knowledge_base_chat", verify=False, timeout=300,
                          headers=hdr,
                          json={"query": query, "knowledge_base_name": KB,
                                "stream": False, "max_tokens": max_tokens, "history": []})
        dt = time.time() - t0
        body = r.text[:200]
        return {"ok": r.status_code == 200, "lat": dt, "preview": body}
    except Exception as e:
        return {"ok": False, "lat": time.time() - t0, "err": str(e)[:100]}

def run_stage(name, fn, concurrency, rounds):
    lats, oks = [], 0
    t0 = time.time()
    for rd in range(rounds):
        results = [None] * concurrency
        ths = []
        for i in range(concurrency):
            def work(idx=i):
                results[idx] = fn(idx)
            th = threading.Thread(target=work); th.start(); ths.append(th)
        for th in ths: th.join()
        for r in results:
            if r and r.get("ok"):
                oks += 1; lats.append(r["lat"])
    total_t = time.time() - t0
    rep = {"stage": name, "concurrency": concurrency, "rounds": rounds,
           "success": oks, "fail": concurrency * rounds - oks,
           "total_sec": round(total_t, 1)}
    if lats:
        rep["lat_avg"] = round(statistics.mean(lats), 2)
        rep["lat_p50"] = round(statistics.median(lats), 2)
        rep["lat_max"] = round(max(lats), 2)
        rep["qps"] = round(oks / total_t, 2)
    return rep

def main():
    print("== Smoke: single login ==", flush=True)
    lg = do_login()
    print("  login ok=%s lat=%.2fs" % (lg["ok"], lg["lat"]), flush=True)
    if not lg["ok"]:
        print("LOGIN FAILED, abort", flush=True); return
    token = lg["token"]

    print("== Smoke: single knowledge_base_chat ==", flush=True)
    ch = do_chat(token, QUERY_B64 and "请介绍文档的主要内容", 128)
    print("  chat ok=%s lat=%.2fs preview=%s" % (ch["ok"], ch["lat"], ch.get("preview", ch.get("err", ""))[:150]), flush=True)

    out = []
    if ch["ok"]:
        print("== Stage A: login concurrency=10 x3 ==", flush=True)
        out.append(run_stage("login_concurrent_10", lambda i: do_login(), 10, 3))
        print("== Stage B: RAG chat concurrency=10 x2 (max_tokens=128) ==", flush=True)
        out.append(run_stage("rag_chat_concurrent_10", lambda i: do_chat(token, "请介绍文档的主要内容", 128), 10, 2))
    else:
        print("chat smoke failed, skip stages", flush=True)
        out.append({"stage": "chat_smoke", "result": "failed", "detail": str(ch)[:300]})

    print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)

if __name__ == "__main__":
    main()
