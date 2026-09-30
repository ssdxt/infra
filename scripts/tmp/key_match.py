import sys, yaml
sys.path.insert(0, "/ManualAI/OmniKnow/omniknow2/assistant")
from src.llms.llm import get_llm_by_type

llm = get_llm_by_type("basic")
key_used = None
for attr in ("root_client", "client", "openai_client", "_client"):
    c = getattr(llm, attr, None)
    if c is None:
        continue
    for sub in ("api_key",):
        k = getattr(c, sub, None)
        if k:
            key_used = k
            print("found at", attr, "-> api_key len", len(k), "head", k[:8])
            break
    if key_used:
        break

conf = yaml.safe_load(open("/ManualAI/OmniKnow/omniknow2/assistant/conf.yaml", encoding="utf-8"))
conf_key = conf["BASIC_MODEL"]["api_key"]
print("conf.api_key len", len(conf_key), "head", conf_key[:8])
print("MATCH =", (key_used == conf_key))
if key_used and key_used != conf_key:
    print("used != conf -> used:", str(key_used)[:20], "conf:", conf_key[:20])
