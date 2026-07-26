import json
from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from app import policy
from app.card_client import CoreBancarioUnavailableError
from app.config import Settings
from app.events import publisher as events_publisher
from app.mcp_server import create_mcp_server
from app.platform import ToolExecutionContext

TENANT_ID = "00000000-0000-0000-0000-000000000001"


def authorize(
    monkeypatch: pytest.MonkeyPatch,
    *,
    caller: str = "agent-runtime-fatura-cartao",
    message_id: str = "wamid-1",
) -> None:
    """Stands in for the signed execution context PlatformMiddleware would populate from a
    verified JWT (see app/platform.py) - these tests call tools directly, bypassing HTTP.
    Also stubs current_tenant_id() for app.events.publisher, since with_tool_event's finally
    block publishes a tool.executed Kafka event (tagged with the tenant) after every call."""
    context = ToolExecutionContext(
        tenant_id=TENANT_ID,
        caller_service=caller,
        conversation_id="conversation-1",
        message_id=message_id,
    )
    monkeypatch.setattr(policy, "current_execution_context", lambda: context)
    monkeypatch.setattr(events_publisher, "current_tenant_id", lambda: TENANT_ID)


class FakeClient:
    def __init__(self, responses: dict | None = None, fail: bool = False) -> None:
        self._responses = responses or {}
        self._fail = fail

    async def _resolve(self, key: str) -> dict | None:
        if self._fail:
            raise CoreBancarioUnavailableError("unavailable")
        return self._responses.get(key)

    async def get_limit(self, cpf: str) -> dict | None:
        return await self._resolve("get_limit")

    async def get_invoice(self, cpf: str) -> dict | None:
        return await self._resolve("get_invoice")


def make_settings() -> Settings:
    return Settings()


async def call(mcp, name: str, args: dict) -> dict:
    result = await mcp.call_tool(name, args)
    return json.loads(result[0].text)


async def test_all_tools_registered_with_schema():
    mcp = create_mcp_server(make_settings(), FakeClient(), MagicMock())

    tools = await mcp.list_tools()

    names = {t.name for t in tools}
    assert names == {"consultar_limite_cartao", "consultar_fatura_cartao"}
    for tool in tools:
        assert tool.description
        assert tool.inputSchema


async def test_consultar_limite_cartao_success(monkeypatch: pytest.MonkeyPatch):
    authorize(monkeypatch)
    client = FakeClient(responses={"get_limit": {"HasCard": True, "TotalLimit": 5000, "AvailableLimit": 3200}})
    mcp = create_mcp_server(make_settings(), client, MagicMock())

    result = await call(mcp, "consultar_limite_cartao", {"cpf": "11111111111"})

    assert result == {"HasCard": True, "TotalLimit": 5000, "AvailableLimit": 3200}


async def test_consultar_fatura_cartao_success(monkeypatch: pytest.MonkeyPatch):
    authorize(monkeypatch)
    client = FakeClient(responses={"get_invoice": {"HasCard": True, "CurrentAmount": 850.0, "DueDate": "2026-08-06", "Closed": False}})
    mcp = create_mcp_server(make_settings(), client, MagicMock())

    result = await call(mcp, "consultar_fatura_cartao", {"cpf": "11111111111"})

    assert result == {"HasCard": True, "CurrentAmount": 850.0, "DueDate": "2026-08-06", "Closed": False}


async def test_consultar_limite_cartao_not_found_reports_found_false(monkeypatch: pytest.MonkeyPatch):
    authorize(monkeypatch)
    client = FakeClient(responses={"get_limit": None})
    mcp = create_mcp_server(make_settings(), client, MagicMock())

    result = await call(mcp, "consultar_limite_cartao", {"cpf": "00000000000"})

    assert result["found"] is False
    assert result["HasCard"] is False


async def test_consultar_fatura_cartao_not_found_reports_found_false(monkeypatch: pytest.MonkeyPatch):
    authorize(monkeypatch)
    client = FakeClient(responses={"get_invoice": None})
    mcp = create_mcp_server(make_settings(), client, MagicMock())

    result = await call(mcp, "consultar_fatura_cartao", {"cpf": "00000000000"})

    assert result["found"] is False
    assert result["HasCard"] is False


async def test_tool_denies_an_unrecognized_caller(monkeypatch: pytest.MonkeyPatch):
    authorize(monkeypatch, caller="some-other-service")
    mcp = create_mcp_server(make_settings(), FakeClient(), MagicMock())

    with pytest.raises(ToolError):
        await mcp.call_tool("consultar_limite_cartao", {"cpf": "11111111111"})


@pytest.mark.parametrize(
    "tool_name,args",
    [
        ("consultar_limite_cartao", {"cpf": "11111111111"}),
        ("consultar_fatura_cartao", {"cpf": "11111111111"}),
    ],
)
async def test_tool_propagates_error_when_service_unavailable(
    monkeypatch: pytest.MonkeyPatch, tool_name: str, args: dict
):
    authorize(monkeypatch)
    mcp = create_mcp_server(make_settings(), FakeClient(fail=True), MagicMock())

    with pytest.raises(ToolError):
        await mcp.call_tool(tool_name, args)
