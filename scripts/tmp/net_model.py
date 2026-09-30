import json
d = json.load(open("/tmp/home-apps-config.json"))
models = d.get("model", [])
for grp in models:
    print("GROUP:", grp.get("label"), "| value:", grp.get("value"))
    for ch in grp.get("children", []):
        print("   -", ch.get("label"), "=> value:", ch.get("value"))
