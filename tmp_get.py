import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from backend.app import create_app
app = create_app()
client = app.test_client()
resp = client.get('/api/notificaciones/centros/1/decision')
print(resp.status_code)
print(resp.data)
