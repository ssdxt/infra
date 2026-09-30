#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# perf_test1.py - model layer benchmark: GLM / embed / rerank, concurrency=10
import base64, json, time, threading, statistics, sys
import requests

GLM_URL = "http://127.0.0.1:10006/v1/chat/completions"
GLM_HDR = {"Authorization": "Bearer cc", "Content-Type": "application/json"}
EMB_URL = "http://127.0.0.1:8105/v1/embeddings"
EMB_HDR = {"Authorization": "Bearer cc", "Content-Type": "application/json"}
RRK_URL = "http://127.0.0.1:8106/rerank"
RRK_HDR = {"Authorization": "Bearer cc", "Content-Type": "application/json"}

# Chinese prompt via base64 (ASCII-safe transport)
PROMPT = base64.b64decode(
    "6K+355So5LiA5Y+l6K+d5LuL57uN5L2g6Ieq5bex77yM5bm26K+05piO5L2g6IO95biu5Yqp57u05L+u5Lq65ZGY5YGa5LuA5LmI44CC"
).decode()

STOP = False
def resource_sampler():
    import subprocess
    rows = []
    while not STOP:
        try:
            npu = subprocess.run(["npu-smi", "info"], capture_output=True, text=True, timeout=5).stdout
            aic = [l for l in npu.splitlines() if "310P3" in l]
            usage = [l for l in npu.splitlines() if "AICore" in l or "/" in l]
            mem = []
            with open("/proc/loadavg") as f: load = f.read().split()[0]
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemAvailable"): mem = line.split()[1]
        except Exception:
            load, mem = "-1", "-1"
        rows.append({"t": time.time(), "load": load, "memKB": mem})
        time.sleep(2)
    return rows

def glm_one(max_tokens=128):
    t0 = time.time()
    try:
        r = requests.post(GLM_URL, headers=GLM_HDR, timeout=300, json={
            "model": "glm-4", "stream": False, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": PROMPT}]})
        dt = time.time() - t0
        j = r.json()
        ct = j.get("usage", {}).get("completion_tokens", 0)
        return {"ok": True, "lat": dt, "tokens": ct}
    except Exception as e:
        return {"ok": False, "lat": time.time() - t0, "err": str(e)[:120]}

def emb_one(n_texts=5):
    t0 = time.time()
    try:
        r = requests.post(EMB_URL, headers=EMB_HDR, timeout=120,
                          json={"input": ["%s text sample %d" % (PROMPT[:20], i) for i in range(n_texts)],
                                "model": "embed"})
        return {"ok": True, "lat": time.time() - t0}
    except Exception as e:
        return {"ok": False, "lat": time.time() - t0, "err": str(e)[:120]}

def rrk_one(n_texts=10):
    t0 = time.time()
    try:
        r = requests.post(RRK_URL, headers=RRK_HDR, timeout=120, json={
            "query": PROMPT[:30],
            "texts": ["doc %d: some knowledge content about maintenance" % i for i in range(n_texts)]})
        return {"ok": True, "lat": time.time() - t0}
    except Exception as e:
        return {"ok": False, "lat": time.time() - t0, "err": str(e)[:120]}

def run_stage(name, fn, concurrency, rounds):
    lats, oks, toks = [], 0, 0
    t0 = time.time()
    for rd in range(rounds):
        results = [None] * concurrency
        ths = []
        for i in range(concurrency):
            def work(idx=i):
                results[idx] = fn()
            th = threading.Thread(target=work); th.start(); ths.append(th)
        for th in ths: th.join()
        for r in results:
            if r and r.get("ok"):
                oks += 1; lats.append(r["lat"])
                if "tokens" in r: toks += r["tokens"]
    total_t = time.time() - t0
    rep = {"stage": name, "concurrency": concurrency, "rounds": rounds,
           "success": oks, "fail": concurrency * rounds - oks,
           "total_sec": round(total_t, 1)}
    if lats:
        rep["lat_avg"] = round(statistics.mean(lats), 2)
        rep["lat_p50"] = round(statistics.median(lats), 2)
        rep["lat_max"] = round(max(lats), 2)
        rep["qps"] = round(oks / total_t, 2)
    if toks:
        rep["completion_tokens"] = toks
        rep["tok_per_sec"] = round(toks / total_t, 1)
    return rep

def main():
    global STOP
    sampler = threading.Thread(target=resource_sampler, daemon=True)
    sampler.start()

    out = []
    print("== Stage 1: GLM single-request baseline x3 ==", flush=True)
    base = []
    for i in range(3):
        r = glm_one(128)
        print("  run%d: lat=%.2fs tokens=%s ok=%s" % (i + 1, r["lat"], r.get("tokens"), r["ok"]), flush=True)
        if r["ok"]: base.append(r)
    if base:
        out.append({"stage": "glm_baseline", "runs": len(base),
                    "lat_avg": round(statistics.mean([b["lat"] for b in base]), 2),
                    "tok_per_sec_single": round(statistics.mean([b["tokens"] / b["lat"] for b in base]), 1),
                    "tokens_avg": round(statistics.mean([b["tokens"] for b in base]))})

    print("== Stage 2: GLM concurrency=10, 2 rounds (20 reqs total) ==", flush=True)
    out.append(run_stage("glm_concurrent_10", lambda: glm_one(128), 10, 2))

    print("== Stage 3: embed, concurrency=10 (5 texts each), 3 rounds ==", flush=True)
    out.append(run_stage("embed_concurrent_10", lambda: emb_one(5), 10, 3))

    print("== Stage 4: rerank, concurrency=10 (10 docs each), 3 rounds ==", flush=True)
    out.append(run_stage("rerank_concurrent_10", lambda: rrk_one(10), 10, 3))

    STOP = True
    time.sleep(1)
    print(json.dumps(out, ensure_ascii=False, indent=2), flush=True)
    print("== RESOURCE SAMPLES (load) ==", flush=True)

if __name__ == "__main__":
    main()
