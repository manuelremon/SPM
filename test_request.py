import subprocess
import time
import requests

# Start the server in a subprocess
server = subprocess.Popen(["python", "-m", "src.backend.app"])

# Wait for the server to start
time.sleep(2)

# Make the request
response = requests.get("http://127.0.0.1:10000/")

print(f"Status: {response.status_code}")
print(f"Content-Type: {response.headers.get('Content-Type')}")
print(f"Text length: {len(response.text)}")
print(f"First 200 chars: {response.text[:200]}")

# Kill the server
server.terminate()
