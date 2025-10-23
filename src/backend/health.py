from __future__ import annotations

import copy
import json
import os
import platform
import shutil
import socket
import subprocess
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Tuple

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - fallback when requests is unavailable
    requests = None

from .config import Settings
from .db import get_connection

try:
    import urllib.request
    import urllib.error
except Exception:  # pragma: no cover
    urllib = None  # type: ignore

PROCESS_STARTED_AT = datetime.now(timezone.utc)
PROCESS_STARTED_MONOTONIC = time.perf_counter()

STATUS_TIMEOUT_SECONDS = max(0.1, Settings.STATUS_TIMEOUT_MS / 1000)
STATUS_CACHE_SECONDS = max(5, Settings.STATUS_CACHE_SECS)

_CACHE_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {"expires_at": 0.0, "payload": None}
_VERSION_CACHE: Dict[str, str] = {}

STATUS_ORDER = ("ERROR", "WARN", "OK", "N/A")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _short_error(error: BaseException | str) -> str:
    message = str(error)
    if len(message) > 220:
        return message[:217] + "..."
    return message or error.__class__.__name__


def _http_get_json(url: str, timeout: float, headers: Dict[str, str] | None = None) -> Dict[str, Any]:
    headers = headers or {}
    if requests:
        response = requests.get(url, timeout=timeout, headers=headers)
        response.raise_for_status()
        return response.json()
    if urllib is None:  # pragma: no cover - unlikely
        raise RuntimeError("No HTTP client available")
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status >= 400:
            raise RuntimeError(f"HTTP {resp.status} for {url}")
        return json.loads(resp.read().decode("utf-8"))


def _http_head(url: str, timeout: float) -> int:
    if requests:
        response = requests.head(url, timeout=timeout)
        return response.status_code
    if urllib is None:  # pragma: no cover
        raise RuntimeError("No HTTP client available")
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status


def _get_version() -> str:
    cached = _VERSION_CACHE.get("version")
    if cached:
        return cached
    version = "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            version = result.stdout.strip()
    except Exception:
        version = "unknown"
    _VERSION_CACHE["version"] = version or "unknown"
    return _VERSION_CACHE["version"]


def _uptime_seconds() -> float:
    return max(0.0, time.perf_counter() - PROCESS_STARTED_MONOTONIC)


def check_backend() -> Dict[str, Any]:
    uptime_seconds = _uptime_seconds()
    uptime = timedelta(seconds=int(uptime_seconds))
    details = {
        "version": _get_version(),
        "env": Settings.ENV,
        "debug": Settings.DEBUG,
        "python_version": platform.python_version(),
        "uptime_seconds": round(uptime_seconds, 2),
        "uptime_human": str(uptime),
    }
    return {"status": "OK", "details": details}


def check_db() -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        with get_connection() as con:
            con.execute("SELECT 1;")
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {"status": "OK", "latency_ms": latency_ms, "details": {"message": "Conexión exitosa"}}
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "status": "ERROR",
            "latency_ms": latency_ms,
            "details": {"error": _short_error(exc)},
        }


def check_disk() -> Dict[str, Any]:
    try:
        usage = shutil.disk_usage(Settings.DATA_DIR if hasattr(Settings, "DATA_DIR") else os.getcwd())
        free_gb = round(usage.free / (1024 ** 3), 2)
        total_gb = round(usage.total / (1024 ** 3), 2)
        percent_free = round((usage.free / usage.total) * 100, 2) if usage.total else 0.0
        status = "OK"
        if percent_free < 10:
            status = "WARN"
        if percent_free < 5:
            status = "ERROR"
        details = {
            "free_gb": free_gb,
            "total_gb": total_gb,
            "percent_free": percent_free,
        }
        return {"status": status, "details": details}
    except Exception as exc:
        return {"status": "ERROR", "details": {"error": _short_error(exc)}}


def check_logs() -> Dict[str, Any]:
    log_path = Path(Settings.LOG_PATH)
    if not log_path.exists():
        return {
            "status": "WARN",
            "details": {
                "log_file_present": False,
                "message": "El archivo de logs aún no se ha generado",
            },
        }
    try:
        size_mb = round(log_path.stat().st_size / (1024 ** 2), 2)
        status = "OK"
        if size_mb > 50:
            status = "WARN"
        if size_mb > 200:
            status = "ERROR"
        details = {
            "log_file_present": True,
            "size_mb": size_mb,
            "last_modified": _to_iso(datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc)),
        }
        return {"status": status, "details": details}
    except Exception as exc:
        return {"status": "ERROR", "details": {"error": _short_error(exc)}}


def check_workers() -> Dict[str, Any]:
    return {
        "status": "N/A",
        "details": {"message": "Sin workers locales configurados"},
    }


def check_ollama() -> Dict[str, Any]:
    if not Settings.STATUS_CHECK_OLLAMA:
        return {
            "status": "N/A",
            "details": {"enabled": False},
        }
    endpoint = Settings.OLLAMA_ENDPOINT.rstrip("/") + "/api/tags"
    started = time.perf_counter()
    try:
        payload = _http_get_json(endpoint, timeout=STATUS_TIMEOUT_SECONDS)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        models = [model.get("name") for model in payload.get("models", []) if isinstance(model, dict)]
        details = {"models": models, "count": len(models)}
        status = "OK" if models else "WARN"
        if not models:
            details["message"] = "Servicio disponible pero sin modelos listados"
        return {"status": status, "latency_ms": latency_ms, "details": details}
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "status": "ERROR",
            "latency_ms": latency_ms,
            "details": {"endpoint": endpoint, "error": _short_error(exc)},
        }


def check_envvars() -> Dict[str, Any]:
    critical = ("SPM_SECRET_KEY", "SPM_DB_PATH", "PORT")
    found = {var: bool(os.getenv(var)) for var in critical}
    missing = [var for var, present in found.items() if not present]
    status = "OK" if not missing else "WARN"
    details = {"variables": found, "missing": missing}
    return {"status": status, "details": details}


def check_errors_recent() -> Dict[str, Any]:
    log_path = Path(Settings.LOG_PATH)
    if not log_path.exists():
        return {"status": "WARN", "details": {"message": "Sin archivo de log disponible"}}
    try:
        errors: List[Tuple[datetime, str]] = []
        with log_path.open("r", encoding="utf-8", errors="ignore") as fh:
            fh.seek(0, os.SEEK_END)
            file_size = fh.tell()
            # leer últimos 64 KB para analizar errores recientes
            offset = max(file_size - 64 * 1024, 0)
            fh.seek(offset)
            if offset:
                fh.readline()
            for line in fh:
                if "ERROR" in line or "CRITICAL" in line:
                    timestamp_text = line.split(" ", 1)[0]
                    try:
                        ts = datetime.fromisoformat(timestamp_text.replace("Z", "+00:00"))
                    except ValueError:
                        try:
                            ts = datetime.strptime(timestamp_text, "%Y-%m-%d")
                        except ValueError:
                            continue
                    errors.append((ts.astimezone(timezone.utc), line.strip()))
        if not errors:
            return {"status": "OK", "details": {"errors_last_15m": 0, "last_error": None}}
        now = _now_utc()
        recent = [ts for ts, _ in errors if now - ts <= timedelta(minutes=15)]
        last_error = max(errors, key=lambda item: item[0])[0]
        status = "OK"
        if recent:
            status = "WARN"
        details = {
            "errors_last_15m": len(recent),
            "last_error_at": _to_iso(last_error),
        }
        return {"status": status, "details": details}
    except Exception as exc:
        return {"status": "ERROR", "details": {"error": _short_error(exc)}}


def check_connectivity() -> Dict[str, Any]:
    host = "example.org"
    started = time.perf_counter()
    try:
        socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        dns_latency = round((time.perf_counter() - started) * 1000, 2)
    except socket.gaierror as exc:
        return {
            "status": "ERROR",
            "details": {"error": _short_error(exc), "stage": "dns"},
        }
    try:
        status_code = _http_head("https://example.org", timeout=STATUS_TIMEOUT_SECONDS)
        total_latency = round((time.perf_counter() - started) * 1000, 2)
        details = {"http_status": status_code, "dns_latency_ms": dns_latency, "total_latency_ms": total_latency}
        status = "OK" if status_code < 400 else "WARN"
        return {"status": status, "latency_ms": total_latency, "details": details}
    except Exception as exc:
        total_latency = round((time.perf_counter() - started) * 1000, 2)
        return {
            "status": "WARN",
            "latency_ms": total_latency,
            "details": {"error": _short_error(exc), "stage": "http"},
        }


def check_github_status() -> Dict[str, Any]:
    if not Settings.STATUS_CHECK_GITHUB:
        return {"status": "N/A", "details": {"enabled": False}}
    started = time.perf_counter()
    try:
        status_json = _http_get_json("https://www.githubstatus.com/api/v2/status.json", timeout=STATUS_TIMEOUT_SECONDS)
        incidents_json = _http_get_json("https://www.githubstatus.com/api/v2/incidents/unresolved.json", timeout=STATUS_TIMEOUT_SECONDS)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        overall = status_json.get("status", {}).get("indicator", "unknown").upper()
        incidents = incidents_json.get("incidents", []) if isinstance(incidents_json, dict) else []
        status = "OK" if overall in {"NONE", "NO", "OPERATIONAL"} and not incidents else "WARN"
        normalized_incidents = [
            {
                "name": incident.get("name"),
                "status": incident.get("status"),
                "created_at": incident.get("created_at"),
            }
            for incident in incidents
            if isinstance(incident, dict)
        ]
        details = {
            "overall": overall,
            "incidents_open": len(normalized_incidents),
            "incidents": normalized_incidents[:5],
        }
        return {"status": status, "latency_ms": latency_ms, "details": details}
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "status": "WARN",
            "latency_ms": latency_ms,
            "details": {"error": _short_error(exc)},
        }


def check_render_status() -> Dict[str, Any]:
    if not Settings.STATUS_CHECK_RENDER:
        return {"status": "N/A", "details": {"enabled": False}}
    started = time.perf_counter()
    try:
        status_json = _http_get_json("https://status.render.com/api/v2/status.json", timeout=STATUS_TIMEOUT_SECONDS)
        incidents_json = _http_get_json("https://status.render.com/api/v2/incidents/unresolved.json", timeout=STATUS_TIMEOUT_SECONDS)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        overall = status_json.get("status", {}).get("indicator", "unknown").upper()
        incidents = incidents_json.get("incidents", []) if isinstance(incidents_json, dict) else []
        status = "OK" if overall in {"NONE", "NO", "OPERATIONAL"} and not incidents else "WARN"
        normalized_incidents = [
            {
                "name": incident.get("name"),
                "status": incident.get("status"),
                "created_at": incident.get("created_at"),
            }
            for incident in incidents
            if isinstance(incident, dict)
        ]
        details = {
            "overall": overall,
            "incidents_open": len(normalized_incidents),
            "incidents": normalized_incidents[:5],
        }
        return {"status": status, "latency_ms": latency_ms, "details": details}
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "status": "WARN",
            "latency_ms": latency_ms,
            "details": {"error": _short_error(exc)},
        }


CHECKS: List[Tuple[str, str, Callable[[], Dict[str, Any]]]] = [
    ("backend", "API Backend", check_backend),
    ("database", "Base de Datos", check_db),
    ("disk", "Almacenamiento", check_disk),
    ("logs", "Archivos de Logs", check_logs),
    ("workers", "Workers locales", check_workers),
    ("ollama", "Servicio IA / Ollama", check_ollama),
    ("env", "Variables críticas", check_envvars),
    ("errors", "Errores recientes", check_errors_recent),
    ("connectivity", "DNS / Conectividad", check_connectivity),
    ("github", "GitHub Status", check_github_status),
    ("render", "Render Status", check_render_status),
]


def _normalize_status(value: str | None) -> str:
    if not value:
        return "N/A"
    value = value.upper()
    if value in {"OK", "WARN", "WARNING", "ERROR", "N/A"}:
        return "WARN" if value == "WARNING" else value
    return "N/A"


def _run_check(func: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        result = func() or {}
    except Exception as exc:  # pragma: no cover - defensive
        result = {"status": "ERROR", "details": {"error": _short_error(exc)}}
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    if "latency_ms" not in result:
        result["latency_ms"] = latency_ms
    result["status"] = _normalize_status(result.get("status"))
    if "details" not in result:
        result["details"] = {}
    return result


def _summarize(statuses: Iterable[str]) -> str:
    normalized = [_normalize_status(status) for status in statuses]
    if any(status == "ERROR" for status in normalized):
        return "ERROR"
    if any(status == "WARN" for status in normalized):
        return "WARN"
    if all(status == "N/A" for status in normalized):
        return "N/A"
    return "OK"


def get_system_status(force: bool = False) -> Dict[str, Any]:
    now = time.time()
    with _CACHE_LOCK:
        if not force and _CACHE["payload"] and _CACHE["expires_at"] > now:
            return copy.deepcopy(_CACHE["payload"])

    items: List[Dict[str, Any]] = []
    for check_id, name, func in CHECKS:
        result = _run_check(func)
        result["id"] = check_id
        result["name"] = name
        items.append(result)

    summary = _summarize(item.get("status") for item in items)
    payload = {
        "ok": True,
        "generated_at": _to_iso(_now_utc()),
        "summary": summary,
        "items": items,
    }

    with _CACHE_LOCK:
        _CACHE["payload"] = copy.deepcopy(payload)
        _CACHE["expires_at"] = now + STATUS_CACHE_SECONDS

    return payload
