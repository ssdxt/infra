import json, urllib.request
d = json.load(urllib.request.urlopen("http://127.0.0.1:8000/openapi.json"))
s = d["components"]["schemas"]["Body_parse_pdf_file_parse_post"]
print(json.dumps(s, indent=1, ensure_ascii=False))
