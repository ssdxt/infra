import sys
sys.path.insert(0, "/ManualAI/OmniKnow/omniknow2/assistant")
import logging
logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
from langchain_core.callbacks import BaseCallbackHandler
from src.llms.llm import get_llm_by_type

class H(BaseCallbackHandler):
    def on_llm_start(self, serializer, prompts, **kw):
        print("CB-START url-hint", flush=True)
    def on_llm_end(self, response, **kw):
        try:
            t = response.generations[0][0].text
            print("CB-END text:", t[:50], flush=True)
        except Exception as e:
            print("CB-END err", e, flush=True)

h = H()
llm = get_llm_by_type("basic")
llm.callbacks = [h]
print("== invoke ==", flush=True)
r = llm.invoke("请只回复两个字：收到")
print("RESULT:", (r.content or "")[:30], flush=True)
