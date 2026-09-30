#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# perf_test3.py - stair load test: find the ceiling. GLM c=10/16/24/32, RAG c=5/10/16
import base64, json, time, threading, statistics
import requests, ssl, warnings

warnings.filterwarnings("ignore")
GLM = "http://127.0.0.1:10006/v1/chat/completions"
GLM_HDR = {"Authorization": "Bearer cc", "Content-Type": "application/json"}
API = "https://127.0.0.1:8261"
PROMPT = base64.b64decode(
    "6K+355So5LiA5Y+l6K+d5LuL57uN5L2g6Ieq5bex77yM5bm26K+05piO5L2g6IO95biu5Yqp57u05L+u5Lq65ZGY5YGa5LuA5LmI44CC"
).decode()
STOP = False

def sampler():
    rows = []
    while not STOP:
        try:
            load = open("/proc/loadavg").read().split()[0]
            memavail = 0
            for line in open("/proc/meminfo"):
                if line.startswith("MemAvailable"):
                    memavail = int(line.split()[1]) // 1024
            rows.append((round(time.time()), load, memavail))
        except Exception:
            pass
        time.sleep(2)
    return rows

def glm_one(max_tokens=128):
    t0 = time.time()
    try:
        r = requests.post(GLM, headers=GLM_HDR, timeout=300, json={
            "model": "glm-4", "stream": False, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": PROMPT}]})
        return {"ok": r.status_code == 200, "lat": time.time() - t0,
                "tok": r.json().get("usage", {}).get("completion_tokens", 0)}
    except Exception as e:
        return {"ok": False, "lat": time.time() - t0, "err": str(e)[:80]}

class Biz:
    def __init__(self):
        ts = str(int(time.time() * 1000))
        pw = base64.b64encode(("admin_Abcd1234_" + ts).encode()).decode()
        r = requests.post(API + "/user/login", verify=False, timeout=30,
                          json={"username": "admin", "password": pw})
        self.token = (r.json().get("data") or {}).get("token", "")
    def rag_one(self):
        t0 = time.time()
        try:
            r = requests.post(API + "/chat/knowledge_base_chat", verify=False, timeout=300,
                              headers={"token": self.token},
                              json={"query": "请介绍文档的主要内容", "knowledge_base_name": "test",
                                    "stream": False, "max_tokens": 128, "history": []})
            return {"ok": r.status_code == 200, "lat": time.time() - t0}
        except Exception as e:
            return {"ok": False, "lat": time.time() - t0, "err": str(e)[:80]}

def stage(name, fn, c):
    results = [None] * c
    ths = []
    t0 = time.time()
    for i in range(c):
        def work(idx=i):
            results[idx] = fn()
        th = threading.Thread(target=work); th.start(); ths.append(th)
    for th in ths: th.join()
    dt = time.time() - t0
    oks = [r for r in results if r and r.get("ok")]
    lats = [r["lat"] for r in oks]
    toks = sum(r.get("tok", 0) for r in oks)
    rep = {"case": name, "concurrency": c, "sent": c, "ok": len(oks), "fail": c - len(oks),
           "wall_sec": round(dt, 1)}
    if lats:
        rep["lat_avg"] = round(statistics.mean(lats), 2)
        rep["lat_p50"] = round(statistics.median(lats), 2)
        rep["lat_max"] = round(max(lats), 2)
        rep["req_per_sec"] = round(len(oks) / dt, 2)
        if toks: rep["tok_per_sec"] = round(toks / dt, 1)
    return rep

def main():
    global STOP
    st = threading.Thread(target=sampler, daemon=True); st.start()
    out = []
    for c in (10, 16, 24, 32):
        out.append(stage("glm_direct", lambda: glm_one(128), c))
        print("glm c=%d done" % c, flush=True)
        time.sleep(8)
    biz = Biz()
    for c in (5, 10, 16):
        out.append(stage("rag_full_chain", lambda: biz.rag_one(), c))
        print("rag c=%d done" % c, flush=True)
        time.sleep(8)
    STOP = True
    time.sleep(1)
    print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)

if __name__ == "__main__":
    main()
