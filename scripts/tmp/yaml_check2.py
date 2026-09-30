import yaml
d = yaml.safe_load(open("/ManualAI/OmniKnow/omniknow2/assistant/conf.yaml"))
bm = d.get("BASIC_MODEL", {})
print("YAML OK")
print("base_url =", bm.get("base_url"))
print("model =", bm.get("model"))
print("api_key_len =", len(bm.get("api_key", "")))
print("top_keys =", sorted(d.keys()))
