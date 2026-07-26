from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from app.config import Settings
from app.platform import create_service_token, current_tenant_id

logger = logging.getLogger(__name__)

CORE_BANCARIO_AUDIENCE = "core-bancario-mock"


class CoreBancarioUnavailableError(Exception):
    """Raised when core-bancario-mock (or the real core banking system) cannot be reached."""


class CardApiClient:
    # core-bancario-mock has no auth middleware of its own (unlike renegotiation-service's
    # downstream, which sits behind PlatformMiddleware) - it does not validate the token this
    # client attaches. We sign and send one anyway, for parity with every other synchronous hop
    # in the platform: nothing has to change here once core-bancario-mock gains real validation.
    def __init__(self, settings: Settings, timeout: float = 5.0) -> None:
        self._settings = settings
        self._base_url = settings.core_bancario_base_url
        self._retry_attempts = settings.core_bancario_retry_attempts
        self._timeout = timeout

    async def get_limit(self, cpf: str) -> dict[str, Any] | None:
        return await self._get(f"/clients/{cpf}/card/limit")

    async def get_invoice(self, cpf: str) -> dict[str, Any] | None:
        return await self._get(f"/clients/{cpf}/card/invoice")

    async def _get(self, path: str) -> dict[str, Any] | None:
        # A malformed/unrecognized CPF is a normal "not found" business outcome (core-bancario-mock
        # 404s it), not an upstream failure - conflating the two here would be the exact bug
        # already found and fixed in renegotiation-service's EligibilityApiClient: a 404 turned
        # into a scary "service unavailable" that implies retrying might help, when the real
        # problem is the identifier itself. A customer *with* a card but nothing to report (e.g.
        # zero invoice) is a normal 200 - see core-bancario-mock's HasCard field for the
        # "identified but has no card at all" case, which is also a 200, not a 404.
        tenant_id = current_tenant_id()
        token = create_service_token(self._settings, CORE_BANCARIO_AUDIENCE, tenant_id)
        headers = {"Authorization": f"Bearer {token}", "X-Tenant-Id": tenant_id}

        @retry(stop=stop_after_attempt(self._retry_attempts + 1), wait=wait_fixed(0.2), reraise=True)
        async def _call() -> httpx.Response:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
                response = await client.get(path, headers=headers)
                if response.status_code == httpx.codes.NOT_FOUND:
                    return response
                response.raise_for_status()
                return response

        try:
            response = await _call()
        except Exception as exc:
            logger.warning("core-bancario-mock call failed after retries (%s)", type(exc).__name__)
            raise CoreBancarioUnavailableError("core-bancario-mock unavailable") from exc

        if response.status_code == httpx.codes.NOT_FOUND:
            return None
        return response.json()
