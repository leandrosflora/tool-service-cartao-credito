import pytest
import respx
from httpx import Response

from app import card_client as card_client_module
from app.card_client import CardApiClient, CoreBancarioUnavailableError
from app.config import Settings

BASE_URL = "http://core-bancario.test"
TENANT_ID = "00000000-0000-0000-0000-000000000001"


def make_client(monkeypatch: pytest.MonkeyPatch, retry_attempts: int = 1) -> CardApiClient:
    # Stands in for the tenant context PlatformMiddleware would populate from a verified JWT -
    # these tests call the client directly, bypassing HTTP (see test_tools.py's `authorize` for
    # the same pattern applied to tool execution).
    monkeypatch.setattr(card_client_module, "current_tenant_id", lambda: TENANT_ID)
    settings = Settings(
        core_bancario_base_url=BASE_URL,
        core_bancario_retry_attempts=retry_attempts,
        internal_auth_outbound_secrets={"core-bancario-mock": "x" * 32},
    )
    return CardApiClient(settings)


@respx.mock
async def test_get_limit_success(monkeypatch: pytest.MonkeyPatch):
    respx.get(f"{BASE_URL}/clients/11111111111/card/limit").mock(
        return_value=Response(200, json={"HasCard": True, "TotalLimit": 5000, "AvailableLimit": 3200})
    )

    result = await make_client(monkeypatch).get_limit("11111111111")

    assert result == {"HasCard": True, "TotalLimit": 5000, "AvailableLimit": 3200}


@respx.mock
async def test_get_invoice_success(monkeypatch: pytest.MonkeyPatch):
    respx.get(f"{BASE_URL}/clients/11111111111/card/invoice").mock(
        return_value=Response(200, json={"HasCard": True, "CurrentAmount": 850.0, "DueDate": "2026-08-06", "Closed": False})
    )

    result = await make_client(monkeypatch).get_invoice("11111111111")

    assert result == {"HasCard": True, "CurrentAmount": 850.0, "DueDate": "2026-08-06", "Closed": False}


@respx.mock
async def test_get_limit_not_found_returns_none_not_an_error(monkeypatch: pytest.MonkeyPatch):
    # A 404 (malformed/unrecognized CPF) is a normal "not found" business outcome, not an upstream
    # failure - the same bug class already found and fixed in renegotiation-service's
    # EligibilityApiClient.
    respx.get(f"{BASE_URL}/clients/00000000000/card/limit").mock(return_value=Response(404))

    result = await make_client(monkeypatch).get_limit("00000000000")

    assert result is None


@respx.mock
async def test_get_invoice_not_found_returns_none_not_an_error(monkeypatch: pytest.MonkeyPatch):
    respx.get(f"{BASE_URL}/clients/00000000000/card/invoice").mock(return_value=Response(404))

    result = await make_client(monkeypatch).get_invoice("00000000000")

    assert result is None


@respx.mock
async def test_transient_failure_then_success_recovers_on_retry(monkeypatch: pytest.MonkeyPatch):
    route = respx.get(f"{BASE_URL}/clients/11111111111/card/limit")
    route.side_effect = [Response(503), Response(200, json={"HasCard": True, "TotalLimit": 5000, "AvailableLimit": 3200})]

    result = await make_client(monkeypatch, retry_attempts=2).get_limit("11111111111")

    assert result == {"HasCard": True, "TotalLimit": 5000, "AvailableLimit": 3200}
    assert route.call_count == 2


@respx.mock
async def test_persistent_failure_raises_unavailable_error(monkeypatch: pytest.MonkeyPatch):
    respx.get(f"{BASE_URL}/clients/11111111111/card/limit").mock(return_value=Response(503))

    with pytest.raises(CoreBancarioUnavailableError):
        await make_client(monkeypatch, retry_attempts=1).get_limit("11111111111")


@respx.mock
async def test_request_carries_service_token_and_tenant_header(monkeypatch: pytest.MonkeyPatch):
    route = respx.get(f"{BASE_URL}/clients/11111111111/card/limit").mock(
        return_value=Response(200, json={"HasCard": True, "TotalLimit": 5000, "AvailableLimit": 3200})
    )

    await make_client(monkeypatch).get_limit("11111111111")

    sent_headers = route.calls.last.request.headers
    assert sent_headers["Authorization"].startswith("Bearer ")
    assert sent_headers["X-Tenant-Id"] == TENANT_ID
