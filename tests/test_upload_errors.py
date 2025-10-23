from __future__ import annotations

import io

import pytest
from werkzeug.datastructures import FileStorage

from src.backend import auth as auth_module
from src.backend.routes import solicitudes_archivos as uploads
from tests.auth_utils import authenticate_client


def test_upload_failure_hides_internal_details(app, client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(auth_module, "load_user_by_id", lambda user_id: {"id": user_id, "id_spm": user_id, "rol": "admin"})
    monkeypatch.setattr(uploads, "_assert_owner_or_admin", lambda sid: True)

    authenticate_client(app, client, "tester", rol="admin")

    def boom(self: FileStorage, dst: str, *args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(FileStorage, "save", boom)

    data = {"files[]": (io.BytesIO(b"hello"), "test.txt")}
    response = client.post(
        "/api/solicitudes/1/archivos",
        data=data,
        content_type="multipart/form-data",
    )

    assert response.status_code == 500
    body = response.get_json()
    assert body == {"error": "upload_failed"}
    assert "disk full" not in response.get_data(as_text=True)
