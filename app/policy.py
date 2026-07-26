from __future__ import annotations

from dataclasses import dataclass

from app.platform import ToolExecutionContext, current_execution_context


class ToolPolicyDeniedError(PermissionError):
    pass


# Unlike tool-service-renegotiation's policy.py, there's no journey_stage to gate here: both
# tools are stateless, read-only lookups with no dangerous or irreversible sequence to protect
# (nothing like confirmar_acordo exists in this domain). The only thing worth authorizing is
# "which service is allowed to call these tools at all".
GOVERNED_TOOLS = frozenset({"consultar_limite_cartao", "consultar_fatura_cartao"})


@dataclass(frozen=True)
class PolicyDecision:
    context: ToolExecutionContext


def authorize_tool(tool_name: str) -> PolicyDecision:
    context = current_execution_context()

    if context.caller_service != "agent-runtime-fatura-cartao":
        raise ToolPolicyDeniedError("Only agent-runtime-fatura-cartao may execute governed tools.")

    if tool_name not in GOVERNED_TOOLS:
        raise ToolPolicyDeniedError(f"Tool '{tool_name}' is not registered in the policy.")

    return PolicyDecision(context)
