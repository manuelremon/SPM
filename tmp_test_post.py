import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from backend.app import create_app
app = create_app()
client = app.test_client()
resp = client.post('/api/notificaciones/centros/1/decision', json={'accion':'aprobar'})
print('status', resp.status_code)
print('data', resp.data)
