from __future__ import annotations

from confluent_kafka import Producer
from mcp.server.fastmcp import FastMCP

from app.card_client import CardApiClient
from app.config import Settings
from app.events.instrumentation import with_tool_event
from app.policy import authorize_tool

# Distinct from HasCard=false (a real customer with no card product, reported by
# core-bancario-mock itself) - "found" is false only when the CPF didn't resolve to a customer at
# all (malformed or unknown), so the agent can tell the two "nothing to report" cases apart in its
# reply instead of conflating "you have no card" with "I couldn't find you".
_NOT_FOUND_LIMIT: dict = {"found": False, "HasCard": False, "TotalLimit": None, "AvailableLimit": None}
_NOT_FOUND_INVOICE: dict = {"found": False, "HasCard": False, "CurrentAmount": None, "DueDate": None, "Closed": False}


def create_mcp_server(settings: Settings, client: CardApiClient, producer: Producer) -> FastMCP:
    mcp = FastMCP(
        name="tool-service-cartao-credito",
        host=settings.mcp_host,
        port=settings.mcp_port,
    )

    @mcp.tool(description="Consulta o limite total e o limite disponivel do cartao de credito do cliente pelo CPF.")
    @with_tool_event("consultar_limite_cartao", producer, settings)
    async def consultar_limite_cartao(cpf: str) -> dict:
        authorize_tool("consultar_limite_cartao")
        result = await client.get_limit(cpf)
        return result if result is not None else _NOT_FOUND_LIMIT

    @mcp.tool(description="Consulta o valor atual da fatura do cartao de credito do cliente pelo CPF.")
    @with_tool_event("consultar_fatura_cartao", producer, settings)
    async def consultar_fatura_cartao(cpf: str) -> dict:
        authorize_tool("consultar_fatura_cartao")
        result = await client.get_invoice(cpf)
        return result if result is not None else _NOT_FOUND_INVOICE

    return mcp
