import yaml, sys
d = yaml.safe_load(open("/app/conf.yaml"))
bm = d.get("BASIC_MODEL", {})
print("YAML OK")
print("BASIC_MODEL.base_url =", bm.get("base_url"))
print("BASIC_MODEL.model =", bm.get("model"))
print("api_key len =", len(bm.get("api_key", "")))
