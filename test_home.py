import subprocess
import requests
import time

# Start server
proc = subprocess.Popen(['python', '-m', 'src.backend.app'], cwd=r'e:\GitHub\SPM-2')
time.sleep(5)  # Wait for server to start

try:
    r = requests.get('http://127.0.0.1:10000/home.html')
    print('Status:', r.status_code)
    if r.status_code == 200:
        print('Success: home.html served')
    else:
        print('Error:', r.text[:200])
except Exception as e:
    print('Exception:', e)
finally:
    proc.terminate()
    input("Press enter to exit")
