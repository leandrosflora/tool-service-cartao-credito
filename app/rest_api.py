from __future__ import annotations

from confluent_kafka import Producer
from fastapi import FastAPI

from app.card_client import CardApiClient
from app.config import Settings
from app.events.instrumentation import with_tool_event
from app.mcp_server import _NOT_FOUND_INVOICE, _NOT_FOUND_LIMIT
from app.policy import authorize_tool


def create_rest_api(settings: Settings, client: CardApiClient, producer: Producer) -> FastAPI:
    app = FastAPI(
        title="tool-service-cartao-credito (REST docs)",
        description="REST mirror of the same governed MCP tools. Signed execution context is mandatory.",
    )

    @app.get("/clients/{cpf}/card/limit", summary="Consulta o limite total e disponivel do cartao de credito")
    @with_tool_event("consultar_limite_cartao", producer, settings)
    async def consultar_limite_cartao(cpf: str) -> dict:
        authorize_tool("consultar_limite_cartao")
        result = await client.get_limit(cpf)
        return result if result is not None else _NOT_FOUND_LIMIT

    @app.get("/clients/{cpf}/card/invoice", summary="Consulta o valor atual da fatura do cartao de credito")
    @with_tool_event("consultar_fatura_cartao", producer, settings)
    async def consultar_fatura_cartao(cpf: str) -> dict:
        authorize_tool("consultar_fatura_cartao")
        result = await client.get_invoice(cpf)
        return result if result is not None else _NOT_FOUND_INVOICE

    return app
