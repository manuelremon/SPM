from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any

from flask import Blueprint, jsonify, request, send_file
from werkzeug.utils import secure_filename

from ..auth import auth_required, get_current_user_id
from ..config import Settings
from ..db import get_connection

bp = Blueprint("archivos", __name__, url_prefix="/api")


def _json_error(code: str, message: str, status: int = 400):
    return jsonify({"ok": False, "error": {"code": code, "message": message}}), status


def _allowed_file(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in Settings.ALLOWED_EXTENSIONS


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@bp.route("/archivos/upload/<int:solicitud_id>", methods=["POST"])
@auth_required
def upload_archivo(solicitud_id: int):
    user_id = get_current_user_id()
    if not user_id:
        return _json_error("auth_required", "Autenticacion requerida", 401)

    if "file" not in request.files:
        return _json_error("no_file", "No se proporciono ningun archivo")

    file = request.files["file"]
    if file.filename == "":
        return _json_error("no_file", "No se selecciono ningun archivo")

    if not _allowed_file(file.filename):
        allowed = ", ".join(Settings.ALLOWED_EXTENSIONS)
        return _json_error("invalid_file", f"Tipo de archivo no permitido. Extensiones permitidas: {allowed}")

    try:
        with get_connection() as con:
            solicitud = con.execute(
                "SELECT id, id_usuario FROM solicitudes WHERE id = ?",
                (solicitud_id,),
            ).fetchone()
            if not solicitud:
                return _json_error("not_found", "Solicitud no encontrada", 404)
            if solicitud["id_usuario"].lower() != user_id.lower():
                return _json_error("forbidden", "No tienes permisos para adjuntar archivos a esta solicitud", 403)

            original_filename = secure_filename(file.filename)
            file_extension = original_filename.rsplit(".", 1)[1].lower() if "." in original_filename else ""
            unique_filename = f"{uuid.uuid4().hex}.{file_extension}" if file_extension else uuid.uuid4().hex

            os.makedirs(Settings.UPLOADS_DIR, exist_ok=True)
            file_path = os.path.join(Settings.UPLOADS_DIR, unique_filename)
            file.save(file_path)

            file_size = os.path.getsize(file_path)
            created_at = _utcnow_iso()

            cursor = con.execute(
                """
                INSERT INTO archivos_adjuntos
                (solicitud_id, nombre_archivo, nombre_original, tipo_mime, tamano_bytes, ruta_archivo, usuario_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    solicitud_id,
                    unique_filename,
                    original_filename,
                    file.content_type or "application/octet-stream",
                    file_size,
                    file_path,
                    user_id,
                    created_at,
                ),
            )
            archivo_id = cursor.lastrowid
            con.commit()

        return jsonify(
            {
                "ok": True,
                "archivo": {
                    "id": archivo_id,
                    "nombre_original": original_filename,
                    "tipo_mime": file.content_type or "application/octet-stream",
                    "tamano_bytes": file_size,
                    "created_at": created_at,
                },
            }
        )
    except Exception as exc:
        return _json_error("upload_error", f"Error al subir el archivo: {exc}", 500)


@bp.route("/archivos/solicitud/<int:solicitud_id>", methods=["GET"])
@auth_required
def listar_archivos(solicitud_id: int):
    user_id = get_current_user_id()
    if not user_id:
        return _json_error("auth_required", "Autenticacion requerida", 401)

    try:
        with get_connection() as con:
            solicitud = con.execute(
                "SELECT id, id_usuario FROM solicitudes WHERE id = ?",
                (solicitud_id,),
            ).fetchone()
            if not solicitud:
                return _json_error("not_found", "Solicitud no encontrada", 404)
            if solicitud["id_usuario"].lower() != user_id.lower():
                return _json_error("forbidden", "No tienes permisos para ver los archivos de esta solicitud", 403)

            archivos = con.execute(
                """
                SELECT id, nombre_original, tipo_mime, tamano_bytes, created_at
                FROM archivos_adjuntos
                WHERE solicitud_id = ?
                ORDER BY created_at DESC
                """,
                (solicitud_id,),
            ).fetchall()
            return jsonify({"ok": True, "archivos": [dict(archivo) for archivo in archivos]})
    except Exception as exc:
        return _json_error("list_error", f"Error al listar archivos: {exc}", 500)


@bp.route("/archivos/download/<int:archivo_id>", methods=["GET"])
@auth_required
def descargar_archivo(archivo_id: int):
    user_id = get_current_user_id()
    if not user_id:
        return _json_error("auth_required", "Autenticacion requerida", 401)

    try:
        with get_connection() as con:
            archivo = con.execute(
                """
                SELECT a.*, s.id_usuario as solicitud_usuario
                FROM archivos_adjuntos a
                JOIN solicitudes s ON a.solicitud_id = s.id
                WHERE a.id = ?
                """,
                (archivo_id,),
            ).fetchone()
            if not archivo:
                return _json_error("not_found", "Archivo no encontrado", 404)
            if archivo["solicitud_usuario"].lower() != user_id.lower():
                return _json_error("forbidden", "No tienes permisos para descargar este archivo", 403)
            if not os.path.exists(archivo["ruta_archivo"]):
                return _json_error("file_not_found", "Archivo fisico no encontrado", 404)
            return send_file(
                archivo["ruta_archivo"],
                as_attachment=True,
                download_name=archivo["nombre_original"],
                mimetype=archivo["tipo_mime"],
            )
    except Exception as exc:
        return _json_error("download_error", f"Error al descargar archivo: {exc}", 500)


@bp.route("/archivos/delete/<int:archivo_id>", methods=["DELETE"])
@auth_required
def eliminar_archivo(archivo_id: int):
    user_id = get_current_user_id()
    if not user_id:
        return _json_error("auth_required", "Autenticacion requerida", 401)

    try:
        with get_connection() as con:
            archivo = con.execute(
                """
                SELECT a.*, s.id_usuario as solicitud_usuario
                FROM archivos_adjuntos a
                JOIN solicitudes s ON a.solicitud_id = s.id
                WHERE a.id = ?
                """,
                (archivo_id,),
            ).fetchone()
            if not archivo:
                return _json_error("not_found", "Archivo no encontrado", 404)
            if archivo["solicitud_usuario"].lower() != user_id.lower():
                return _json_error("forbidden", "No tienes permisos para eliminar este archivo", 403)

            con.execute("DELETE FROM archivos_adjuntos WHERE id = ?", (archivo_id,))
            con.commit()

        try:
            if os.path.exists(archivo["ruta_archivo"]):
                os.unlink(archivo["ruta_archivo"])
        except Exception:
            pass

        return jsonify({"ok": True, "message": "Archivo eliminado correctamente"})
    except Exception as exc:
        return _json_error("delete_error", f"Error al eliminar archivo: {exc}", 500)
