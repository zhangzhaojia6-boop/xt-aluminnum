import json
import urllib.request

body = json.dumps({"qr_code": "XT-ZR2-EN"}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/auth/qr-login",
    data=body,
    headers={"Content-Type": "application/json"},
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
token = data["access_token"]
print("Login OK:", data["user"]["username"], data["user"]["name"])

req2 = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/mobile/current-shift",
    headers={"Authorization": "Bearer " + token},
)
try:
    resp2 = urllib.request.urlopen(req2)
    shift_data = json.loads(resp2.read())
    print("Shift:", json.dumps(shift_data, ensure_ascii=False, indent=2)[:800])
except urllib.error.HTTPError as e:
    print("Shift error:", e.code, e.read().decode()[:500])
