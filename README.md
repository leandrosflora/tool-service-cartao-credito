# tool-service-cartao-credito

MCP tool-service for the credit card invoice/limit skill, consumed by `agent-runtime-fatura-cartao`.
Exposes two governed, read-only tools over MCP (and a REST mirror for docs/manual testing):

- `consultar_limite_cartao(cpf)` - total and available credit limit.
- `consultar_fatura_cartao(cpf)` - current invoice amount, due date, and whether it's closed.

## Why this is thinner than tool-service-renegotiation

Both tools are stateless, read-only lookups - there's no multi-step journey, no irreversible
action (nothing like `confirmar_acordo`), so there's nothing to gate by stage. `app/policy.py`
only checks *which service* is allowed to call these tools, not *when* in a journey. Calls go
straight to `core-bancario-mock` (or the real core banking system) - there's no intermediate
business-logic service, since there's no business logic beyond "fetch and return" in this domain.
If that changes (e.g. a real rule gets layered on top of the raw core banking data), extract one
then - don't build it preemptively.

## Running locally

```
pip install -r requirements-dev.txt
python -m app.main
```

MCP server on `:8410`, REST docs/health/metrics on `:8411`. Requires `core-bancario-mock` running
and reachable at `CORE_BANCARIO_BASE_URL` (defaults to `http://localhost:9405`).

## Tests

```
pytest
```