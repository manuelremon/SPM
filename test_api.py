import requests

try:
    r = requests.get('http://127.0.0.1:10000/api/almacenes?centro=1500', timeout=5)
    print('Status:', r.status_code)
    if r.status_code == 200:
        data = r.json()
        print('Success! Got', len(data), 'almacenes')
        if data:
            print('First item:', data[0])
    else:
        print('Error:', r.text)
except Exception as e:
    print('Exception:', e)
