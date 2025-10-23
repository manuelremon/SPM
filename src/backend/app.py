from __future__ import annotations

from logging.handlers import RotatingFileHandler
from pathlib import Path
import logging
import os

from dotenv import load_dotenv
from flask import Flask, abort, current_app, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import safe_join

from .config import Settings, Config
from .routes.auth import bp as auth_bp
from .routes.catalogos import bp as catalogos_bp, almacenes_bp
from .routes.preferences import bp as preferences_bp
from .routes.solicitudes import bp as solicitudes_bp
from .routes.solicitudes_archivos import bp as bp_up
from ..ai_assistant.api import bp as ai_bp
from .export_solicitudes import bp as export_bp
from .files import files_bp
from .jwt_utils import verify_token
from .db import get_db

load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
HTML_DIR = FRONTEND_DIR
ASSETS_DIR = FRONTEND_DIR / "assets"
_CLIENT_LOGS: list[dict[str, str | None]] = []


def _setup_logging(app: Flask) -> None:
    Settings.ensure_dirs()
    handler = RotatingFileHandler(
        Settings.LOG_PATH, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.DEBUG)


def _serve_frontend(filename: str):
    safe_path = safe_join(str(HTML_DIR), filename)
    if not safe_path or not os.path.isfile(safe_path):
        current_app.logger.error("HTML not found: %s (HTML_DIR=%s)", filename, HTML_DIR)
        abort(404)
    return send_from_directory(HTML_DIR, filename)

def _print_routes_once(app: Flask) -> None:
    if getattr(app, "_routes_printed", False):
        return
    with app.app_context():
        app.logger.info("SPM dev server -> http://127.0.0.1:10000  |  API base -> /api  |  Single-origin ON")
        app.logger.info("FRONTEND_DIR=%s", HTML_DIR)
        for rule in sorted(app.url_map.iter_rules(), key=lambda x: x.rule):
            if str(rule).startswith(("/", "/api")):
                methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
                app.logger.info("ROUTE %-32s %s", rule.rule, methods)
    app._routes_printed = True


def create_app() -> Flask:

    app = Flask(__name__, static_folder=None, static_url_path="")
    app.config.from_object(Config)
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["FRONTEND_ORIGIN"] = Config.FRONTEND_ORIGIN
    app.config["COOKIE_NAME"] = Config.COOKIE_NAME
    app.config["COOKIE_SAMESITE"] = Config.COOKIE_SAMESITE
    app.config["COOKIE_SECURE"] = Config.COOKIE_SECURE
    app.config["DEBUG"] = Config.DEBUG
    app.config["JSON_AS_ASCII"] = False
    app.config["JSONIFY_MIMETYPE"] = "application/json; charset=utf-8"
    app.config["MAX_CONTENT_LENGTH"] = getattr(Config, "MAX_CONTENT_LENGTH", 16*1024*1024)
    app.config.setdefault("ACCESS_TOKEN_TTL", Settings.ACCESS_TOKEN_TTL)
    app.config.setdefault("TOKEN_TTL", Settings.TOKEN_TTL)
    app.config.setdefault("COOKIE_ARGS", dict(Settings.COOKIE_ARGS))
    app.config.setdefault("COOKIE_SECURE", Settings.COOKIE_ARGS["secure"])
    app.config.setdefault("COOKIE_SAMESITE", Settings.COOKIE_ARGS["samesite"])
    app.config.setdefault("SESSION_COOKIE_SECURE", Settings.COOKIE_ARGS["secure"])
    app.config.setdefault("SESSION_COOKIE_SAMESITE", Settings.COOKIE_ARGS["samesite"])
    app.config.setdefault("UPLOAD_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads")))
    app.config.setdefault("UPLOAD_MAX_EACH", 10 * 1024 * 1024)   # 10 MiB
    app.config.setdefault("UPLOAD_MAX_TOTAL", 40 * 1024 * 1024)  # 40 MiB

    # CORS con credenciales para el origen del frontend
    CORS(app,
         supports_credentials=True,
         resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}})

    @app.after_request
    def _set_dev_headers(resp):
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type and "charset" not in content_type.lower():
            resp.headers["Content-Type"] = "application/json; charset=utf-8"
        if "text/html" in content_type:
            if "charset" not in content_type.lower():
                resp.headers["Content-Type"] = "text/html; charset=utf-8"
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return resp

    app.register_blueprint(catalogos_bp)
    app.register_blueprint(almacenes_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(preferences_bp)
    app.register_blueprint(solicitudes_bp)
    app.register_blueprint(bp_up)
    app.register_blueprint(ai_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(files_bp)

    @app.get("/api/health")
    def health():
        return jsonify(ok=True, app="SPM")

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    @app.post("/api/client-logs")
    def client_logs():
        try:
            data = request.get_json(silent=True) or {}
            entry = {
                "page": data.get("page"),
                "message": data.get("message"),
                "stack": data.get("stack"),
                "href": data.get("href"),
                "userAgent": data.get("userAgent"),
            }
            _CLIENT_LOGS.append(entry)
            del _CLIENT_LOGS[:-100]
        except Exception as exc:  # pragma: no cover - defensive
            current_app.logger.warning("client-log intake failed: %s", exc)
        return jsonify(ok=True)

    @app.route("/")
    def page_index():
        return _serve_frontend("index.html")

    @app.route("/home")
    @app.route("/home.html")
    def page_home():
        return _serve_frontend("home.html")

    @app.route("/mi-cuenta.html")
    def page_mi_cuenta():
        return _serve_frontend("mi-cuenta.html")

    @app.route("/crear-solicitud.html")
    def page_crear_solicitud():
        return _serve_frontend("crear-solicitud.html")

    @app.route("/preferencias.html")
    def page_preferencias():
        return _serve_frontend("preferencias.html")

    @app.route("/admin-usuarios.html")
    def page_admin_usuarios():
        return _serve_frontend("admin-usuarios.html")

    @app.route("/admin-materiales.html")
    def page_admin_materiales():
        return _serve_frontend("admin-materiales.html")

    @app.route("/<string:page>.html")
    def page_any_html(page: str):
        return _serve_frontend(f"{page}.html")

    @app.route("/styles.css")
    def styles():
        return _serve_frontend("styles.css")

    @app.route("/app.js")
    def app_js():
        return _serve_frontend("app.js")

    @app.route("/boot.js")
    def boot_js():
        return _serve_frontend("boot.js")

    @app.route("/api_client.js")
    def api_client_js():
        return _serve_frontend("api_client.js")

    @app.route("/assets/<path:fname>")
    def assets(fname: str):
        asset_path = ASSETS_DIR / fname
        if not asset_path.is_file():
            abort(404)
        return send_from_directory(ASSETS_DIR, fname)

    @app.errorhandler(404)
    def not_found(e):
        try:
            htmls = sorted(f.name for f in FRONTEND_DIR.glob("*.html"))
        except Exception:  # pragma: no cover - defensive
            htmls = []
        current_app.logger.warning(
            "404 for %s. FRONTEND_DIR=%s available=%s",
            request.path,
            FRONTEND_DIR,
            ",".join(htmls),
        )
        return "Not Found", 404

    @app.put('/api/users/me')
    def update_me():
        token = request.cookies.get('spm_token')
        payload = verify_token(token) if token else None
        if not payload:
            return jsonify({'error':'unauthorized'}), 401
        data = request.get_json() or {}
        email = (data.get('email') or '').strip()
        display_name = (data.get('display_name') or '').strip()
        if email and '@' not in email:
            return jsonify({'error':'invalid_email'}), 400
        db = get_db()
        db.execute('UPDATE users SET email=?, display_name=? WHERE username=?',
                   (email or None, display_name or None, payload['sub']))
        db.commit()
        return jsonify({'ok': True}), 200

    _print_routes_once(app)

    return app



# Expose app for import (for tests)
app = create_app()

def _print_banner():
    print(
        "SPM dev server -> http://127.0.0.1:10000  |  API base -> /api  |  Single-origin ON"
    )

if __name__ == "__main__":
    from .config import Config
    _print_banner()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5001"))
    app.run(host=host, port=port, debug=Config.DEBUG, use_reloader=False, threaded=False)

