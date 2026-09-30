import logging, sys
sys.path.insert(0, "/ManualAI/OmniKnow/omniknow2/assistant")
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s", stream=sys.stdout)
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.INFO)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("LiteLLM").setLevel(logging.INFO)

from src.llms.llm import get_llm_by_type
llm = get_llm_by_type("basic")
print("== LLM object base_url/api_key ==", flush=True)
try:
    print("base_url:", getattr(llm, "openai_api_base", getattr(llm, "base_url", "?")))
    k = getattr(llm, "openai_api_key", "?")
    print("api_key:", (str(k)[:10] + "..." + str(k)[-4:]) if len(str(k)) > 14 else k)
except Exception as e:
    print("attr err:", e)

print("== now invoke (watch HTTP Request + authorization) ==", flush=True)
r = llm.invoke("请只回复两个字：收到")
print("RESULT:", r.content[:100])
