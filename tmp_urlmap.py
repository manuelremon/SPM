import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from backend.app import create_app
app = create_app()
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
    methods = ",".join(sorted(rule.methods))
    print(f"{rule.rule} -> {methods}")
