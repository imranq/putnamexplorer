import os, json, urllib.request
api_key = os.environ["GEMINI_API_KEY"]
batch_name = "batches/5ckcm2nkajbmjile0sg9ogp365teu29oe14g"
url = f"https://generativelanguage.googleapis.com/v1beta/{batch_name}"
req = urllib.request.Request(url, headers={"x-goog-api-key": api_key})
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read().decode("utf-8"))
print(json.dumps(data, indent=2)[:12000])
