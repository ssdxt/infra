import sys, asyncio
sys.path.insert(0, "/ManualAI/OmniKnow/omniknow2/assistant")
from src.llms.llm import get_llm_by_type

async def main():
    llm = get_llm_by_type("basic")
    n_content = 0
    n_reason = 0
    total = 0
    parts_content = []
    for chunk in llm.stream("你好，用一句话自我介绍"):
        total += 1
        c = getattr(chunk, "content", None)
        ak = getattr(chunk, "additional_kwargs", {}) or {}
        r = ak.get("reasoning_content")
        if c:
            n_content += 1
            parts_content.append(c)
        if r:
            n_reason += 1
    print("total_chunks =", total)
    print("chunks_with_content =", n_content, "| chunks_with_reasoning =", n_reason)
    print("joined_content =", "".join(parts_content)[:200])

asyncio.run(main())
