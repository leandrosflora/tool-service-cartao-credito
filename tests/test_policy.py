from __future__ import annotations

import pytest

from app import policy
from app.platform import ToolExecutionContext


def _context(*, caller: str = "agent-runtime-fatura-cartao", message_id: str = "wamid-1") -> ToolExecutionContext:
    return ToolExecutionContext(
        tenant_id="00000000-0000-0000-0000-000000000001",
        caller_service=caller,
        conversation_id="conversation-1",
        message_id=message_id,
    )


def test_authorize_tool_allows_the_configured_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy, "current_execution_context", lambda: _context())

    decision = policy.authorize_tool("consultar_limite_cartao")

    assert decision.context.caller_service == "agent-runtime-fatura-cartao"


def test_authorize_tool_allows_both_governed_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy, "current_execution_context", lambda: _context())

    policy.authorize_tool("consultar_limite_cartao")
    policy.authorize_tool("consultar_fatura_cartao")


def test_authorize_tool_denies_an_unrecognized_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy, "current_execution_context", lambda: _context(caller="some-other-service"))

    with pytest.raises(policy.ToolPolicyDeniedError, match="Only agent-runtime-fatura-cartao"):
        policy.authorize_tool("consultar_limite_cartao")


def test_authorize_tool_denies_an_unregistered_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(policy, "current_execution_context", lambda: _context())

    with pytest.raises(policy.ToolPolicyDeniedError, match="not registered"):
        policy.authorize_tool("consultar_algo_inexistente")
