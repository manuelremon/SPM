from __future__ import annotations

import os

from flask import Flask, jsonify

from .config import Settings
from .db import health_ok

app = Flask(__name__, static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend")))

app.config["DEBUG"] = Settings.DEBUG
app.config["JSON_AS_ASCII"] = False

@app.get("/api/health")
def health():
    print("health called")
    return "test"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=Settings.DEBUG)
