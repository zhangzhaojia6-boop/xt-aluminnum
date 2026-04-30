import json
import urllib.request

ROLES_TO_TEST = [
    ("XT-ZR2-EN", "electrician"),
    ("XT-ZR2-MT", "mechanic"),
    ("XT-ZR2-HY", "hydraulic"),
    ("XT-ZR2-1-OP", "operator"),
]

for qr, label in ROLES_TO_TEST:
    body = json.dumps({"qr_code": qr}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/auth/qr-login",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    token = data["access_token"]

    req2 = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/mobile/entry-fields",
        headers={"Authorization": "Bearer " + token},
    )
    try:
        resp2 = urllib.request.urlopen(req2)
        fields = json.loads(resp2.read())
        print("=== %s (%s) ===" % (label, data["user"]["role"]))
        print("  mode:", fields.get("mode"))
        print("  role_label:", fields.get("role_label"))
        for g in fields.get("groups", []):
            names = [f["name"] for f in g["fields"]]
            print("  [%s] %s" % (g["label"], ", ".join(names)))
        ro = fields.get("readonly_fields", [])
        if ro:
            print("  readonly:", [f["name"] for f in ro])
        print()
    except urllib.error.HTTPError as e:
        print("ERROR %s: %s %s" % (label, e.code, e.read().decode()[:200]))
