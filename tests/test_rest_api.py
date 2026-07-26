from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.rest_api import create_rest_api
from tests.test_tools import FakeClient, authorize


def make_client(fake: FakeClient) -> TestClient:
    app = create_rest_api(Settings(), fake, MagicMock())
    return TestClient(app, raise_server_exceptions=False)


def test_swagger_ui_is_served():
    client = make_client(FakeClient())

    response = client.get("/docs")

    assert response.status_code == 200


def test_openapi_schema_lists_both_operations():
    client = make_client(FakeClient())

    schema = client.get("/openapi.json").json()

    assert set(schema["paths"]) == {"/clients/{cpf}/card/limit", "/clients/{cpf}/card/invoice"}


def test_consultar_limite_cartao_success(monkeypatch: pytest.MonkeyPatch):
    authorize(monkeypatch)
    client = make_client(FakeClient(responses={"get_limit": {"HasCard": True, "TotalLimit": 5000, "AvailableLimit": 3200}}))

    response = client.get("/clients/11111111111/card/limit")

    assert response.status_code == 200
    assert response.json() == {"HasCard": True, "TotalLimit": 5000, "AvailableLimit": 3200}


def test_consultar_fatura_cartao_success(monkeypatch: pytest.MonkeyPatch):
    authorize(monkeypatch)
    client = make_client(FakeClient(responses={"get_invoice": {"HasCard": True, "CurrentAmount": 850.0, "DueDate": "2026-08-06", "Closed": False}}))

    response = client.get("/clients/11111111111/card/invoice")

    assert response.status_code == 200
    assert response.json() == {"HasCard": True, "CurrentAmount": 850.0, "DueDate": "2026-08-06", "Closed": False}


def test_consultar_limite_cartao_propagates_error_when_service_unavailable():
    client = make_client(FakeClient(fail=True))

    response = client.get("/clients/11111111111/card/limit")

    assert response.status_code == 500
