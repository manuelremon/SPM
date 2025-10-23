import requests
import json

# Login
r = requests.post('http://127.0.0.1:10000/api/login', json={'username':'demo','password':'demo123'})
print('LOGIN ->', r.status_code)
if r.status_code == 200:
    # Ask
    s = requests.get('http://127.0.0.1:10000/api/ai/status', cookies=r.cookies)
    print('STATUS ->', s.status_code)
    if s.status_code == 200:
        resp = s.json()
        print('Status:', resp)
    else:
        print('STATUS failed:', s.text)
else:
    print('Login failed')
