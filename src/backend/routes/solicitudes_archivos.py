import os
import uuid
from typing import Optional

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from ..auth import auth_required, get_current_user, get_current_user_id
from ..db import get_connection
from ..roles import has_role

bp = Blueprint("sol_adjuntos", __name__, url_prefix="/api")
ALLOWED = {"pdf", "png", "jpg", "jpeg", "xlsx", "csv", "docx", "txt"}
_DANGEROUS_EXTENSIONS = {"php", "exe", "sh", "bat", "cmd", "js", "html"}


def _get_upload_dir() -> str:
    root = current_app.config.get(
        "UPLOAD_DIR", os.path.abspath(os.path.join(current_app.root_path, "..", "..", "uploads"))
    )
    os.makedirs(root, exist_ok=True)
    return root


def _allowed(name: str) -> bool:
    if not name or "." not in name:
        return False
    base = os.path.basename(name)
    parts = base.split(".")
    if len(parts) < 2:
        return False
    ext = parts[-1].lower()
    if ext not in ALLOWED:
        return False
    return not any(part.lower() in _DANGEROUS_EXTENSIONS for part in parts[:-1])


def _is_admin(user: Optional[dict]) -> bool:
    if not user:
        return False
    return has_role(user, "admin", "administrador")


def _assert_owner_or_admin(solicitud_id: int) -> bool:
    uid = get_current_user_id()
    if not uid:
        return False
    if _is_admin(get_current_user()):
        return True
    try:
        with get_connection() as con:
            row = con.execute(
                "SELECT 1 FROM solicitudes WHERE id = ? AND user_id = ? LIMIT 1",
                (solicitud_id, uid),
            ).fetchone()
            return bool(row)
    except Exception as exc:  # pragma: no cover - defensive
        current_app.logger.warning("Fallo validando permisos de adjuntos para %s: %s", solicitud_id, exc)
        return False


@bp.route("/solicitudes/<int:sid>/archivos", methods=["POST"])
@auth_required
def upload_adjuntos(sid: int):
    if not _assert_owner_or_admin(sid):
        return jsonify(error="forbidden"), 403
    files = request.files.getlist("files[]")
    if not files:
        return jsonify(error="no_files"), 400
    if len(files) > 10:
        return jsonify(error="too_many_files"), 400

    max_each = int(current_app.config.get("UPLOAD_MAX_EACH", 10 * 1024 * 1024))
    max_total = int(current_app.config.get("UPLOAD_MAX_TOTAL", 40 * 1024 * 1024))
    total = 0
    saved = []
    root = _get_upload_dir()
    target_dir = os.path.join(root, str(sid))
    os.makedirs(target_dir, exist_ok=True)

    try:
        for f in files:
            fname = f.filename or ""
            if not _allowed(fname):
                return jsonify(error="extension_not_allowed"), 400
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(0)
            total += size
            if size > max_each:
                return jsonify(error="file_too_large"), 413
            if total > max_total:
                return jsonify(error="request_too_large"), 413
            safe = secure_filename(fname)
            name = f"{uuid.uuid4().hex}-{safe}"
            path = os.path.join(target_dir, name)
            f.save(path)
            saved.append(
                {
                    "name": safe,
                    "size": size,
                    "content_type": f.mimetype or "application/octet-stream",
                    "url": f"/api/solicitudes/{sid}/archivos/{name}",
                }
            )
    except Exception as exc:  # pragma: no cover - best effort
        current_app.logger.exception("Error guardando adjuntos para solicitud %s: %s", sid, exc)
        return jsonify(error="upload_failed"), 500

    return jsonify(ok=True, count=len(saved), files=saved)


@bp.route("/solicitudes/<int:sid>/archivos/<path:fname>", methods=["GET"])
@auth_required
def serve_adjunto(sid: int, fname: str):
    if not _assert_owner_or_admin(sid):
        return jsonify(error="forbidden"), 403
    root = _get_upload_dir()
    directory = os.path.join(root, str(sid))
    try:
        return send_from_directory(directory, fname, as_attachment=True)
    except FileNotFoundError:
        return jsonify(error="not_found"), 404
    except Exception as exc:  # pragma: no cover - defensive
        current_app.logger.exception("Error enviando adjunto %s/%s: %s", sid, fname, exc)
        return jsonify(error="download_failed"), 500
