#!/bin/bash
# 证明 assistant(BASIC_MODEL) 调用的是 conf.yaml 里的 MaaS 端点与 key
# 输出两个证据：1) 真实出站 HTTP 请求行  2) SDK 实际 key 与 conf.yaml key 比对
cat > /tmp/verify_basic_llm.py <<'PYEOF'
import logging, sys, yaml
sys.path.insert(0, "/ManualAI/OmniKnow/omniknow2/assistant")
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s", stream=sys.stdout)
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.INFO)
logging.getLogger("openai").setLevel(logging.WARNING)
from src.llms.llm import get_llm_by_type

llm = get_llm_by_type("basic")
print("== LLM base_url ==", getattr(llm, "openai_api_base", "?"))
print("== send one request (watch HTTP Request line) ==")
r = llm.invoke("请只回复两个字：收到")
print("RESULT:", (r.content or "")[:60])

key_used = None
for attr in ("root_client", "client", "openai_client", "_client"):
    c = getattr(llm, attr, None)
    if c:
        key_used = getattr(c, "api_key", None)
        if key_used:
            break
conf = yaml.safe_load(open("/ManualAI/OmniKnow/omniknow2/assistant/conf.yaml", encoding="utf-8"))
ck = conf["BASIC_MODEL"]["api_key"]
print("== key used head ==", str(key_used)[:12], "len", len(str(key_used)))
print("== conf key head ==", ck[:12], "len", len(ck))
print("MATCH =", str(key_used) == ck)
PYEOF
docker cp /tmp/verify_basic_llm.py assistant:/tmp/verify_basic_llm.py
docker exec -e PYTHONPATH=/ManualAI/OmniKnow/omniknow2/assistant assistant /root/anaconda3/envs/assistant/bin/python /tmp/verify_basic_llm.py 2>&1 \
  | grep -iE 'HTTP Request|base_url|key head|conf key|MATCH|RESULT'
