import requests  # type: ignore
r = requests.get('http://127.0.0.1:10000/home.html')
print('Status:', r.status_code)
if r.status_code != 200:
    print('Error:', r.text[:200])
