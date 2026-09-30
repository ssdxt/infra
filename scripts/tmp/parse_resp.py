import json, sys

full_text = []
reason = []
with open("/tmp/neo_resp.txt", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("data: "):
            try:
                d = json.loads(line[6:])
            except Exception:
                continue
            if "content" in d and d["content"]:
                full_text.append(d["content"])
            if d.get("reasoning_content"):
                reason.append(d["reasoning_content"])

print("content pieces =", len(full_text))
print("joined_content =", "".join(full_text)[:500])
print("reasoning pieces =", len(reason), "reason_preview =", "".join(reason)[:200])
