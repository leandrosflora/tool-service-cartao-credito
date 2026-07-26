from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8410
    docs_port: int = 8411

    # core-bancario-mock has no auth of its own (unlike renegotiation-service) - this is a direct,
    # unauthenticated internal call, no service token involved. See card_client.py.
    core_bancario_base_url: str = "http://localhost:9405"
    core_bancario_retry_attempts: int = 2

    kafka_bootstrap_servers: str = "localhost:29092"
    kafka_tool_events_topic: str = "tool.executed"
    otel_otlp_endpoint: str = "http://localhost:4317"

    internal_auth_enabled: bool = True
    internal_auth_issuer: str = "conversational-ai-platform"
    internal_auth_service_name: str = "tool-service-cartao-credito"
    internal_auth_outbound_secrets: dict[str, str] = {}
    internal_auth_inbound_secrets: dict[str, str] = {}
    internal_auth_token_ttl_seconds: int = 300


def get_settings() -> Settings:
    return Settings()
