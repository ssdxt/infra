# -*- coding: utf-8 -*-
# Patch llm.py: attach a logging callback so every LLM call logs url + response
import io, shutil

P = "/ManualAI/OmniKnow/omniknow2/assistant/src/llms/llm.py"
shutil.copyfile(P, P + ".bak-0907-llmlog")
with io.open(P, "r", encoding="utf-8") as f:
    src = f.read()

# 1) insert import + handler class after logger line
anchor_logger = "logger = logging.getLogger(__name__)"
handler_code = (
    "logger = logging.getLogger(__name__)\n"
    "\n"
    "class _LLMCallLogHandler(BaseCallbackHandler):\n"
    "    \"\"\"Log each real LLM call: request url + response text (to assistant.log).\"\"\"\n"
    "    def __init__(self, base_url: str, model: str):\n"
    "        b = (base_url or '').rstrip('/')\n"
    "        self.url = (b + '/chat/completions') if b else 'unknown'\n"
    "        self.model = model or '?'\n"
    "    def on_llm_start(self, serializer, prompts, **kwargs):\n"
    "        logger.info('[LLM-CALL] url=%s model=%s', self.url, self.model)\n"
    "    def on_llm_end(self, response, **kwargs):\n"
    "        try:\n"
    "            gens = getattr(response, 'generations', None)\n"
    "            text = gens[0][0].text if gens and gens[0] else ''\n"
    "            if text:\n"
    "                logger.info('[LLM-RESP] url=%s -> %s', self.url, text[:1500])\n"
    "        except Exception:\n"
    "            pass\n"
)
assert src.count(anchor_logger) == 1, "logger anchor not unique"
src = src.replace(anchor_logger, handler_code, 1)

# ensure BaseCallbackHandler imported
if "from langchain_core.callbacks import BaseCallbackHandler" not in src:
    # add near other langchain_core import
    src = src.replace(
        "from langchain_core.language_models import BaseChatModel",
        "from langchain_core.language_models import BaseChatModel\nfrom langchain_core.callbacks import BaseCallbackHandler",
        1,
    )

# 2) inject attach logic before caching in get_llm_by_type
anchor_cache = "    _llm_cache[llm_type] = llm\n    return llm"
attach_code = (
    "    # attach call-log handler\n"
    "    try:\n"
    "        cfg_key = _get_llm_type_config_keys().get(llm_type, '')\n"
    "        _cc = conf.get(cfg_key, {}) if cfg_key else {}\n"
    "        _b = _cc.get('base_url') or _cc.get('api_base') or ''\n"
    "        _m = _cc.get('model') or llm_type\n"
    "        _prev = list(getattr(llm, 'callbacks', None) or [])\n"
    "        llm.callbacks = _prev + [_LLMCallLogHandler(_b, _m)]\n"
    "    except Exception:\n"
    "        logger.warning('attach LLM call log handler failed', exc_info=True)\n"
    "    _llm_cache[llm_type] = llm\n"
    "    return llm"
)
assert src.count(anchor_cache) == 1, "cache anchor not unique"
src = src.replace(anchor_cache, attach_code, 1)

with io.open(P, "w", encoding="utf-8") as f:
    f.write(src)
print("PATCHED OK")

# syntax check
import py_compile
py_compile.compile(P, doraise=True)
print("SYNTAX OK")
