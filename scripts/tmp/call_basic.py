import sys, asyncio
sys.path.insert(0, "/ManualAI/OmniKnow/omniknow2/assistant")
from src.llms.llm import get_llm_by_type, get_configured_llm_models

print("configured models =", get_configured_llm_models())

async def main():
    llm = get_llm_by_type("basic")
    print("LLM type=basic ->", type(llm).__name__)
    r = await llm.ainvoke("用一句话回答：中国首都是哪座城市？")
    content = getattr(r, "content", r)
    print("RESULT:", content)

asyncio.run(main())
