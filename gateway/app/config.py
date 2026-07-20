from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Auth
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # MCP server (stdio transport)
    mcp_server_command: str = "node"
    mcp_server_args: str = "/absolute/path/to/meditourbuddy/packages/clinic-registry-mcp/dist/index.js"
    database_url: str = "postgresql://..."

    # Gateway DB (users/cases/reports) — defaults to the same Supabase
    # instance as `database_url` (different schema), so most deployments
    # never need to set this separately. Override only if the gateway DB
    # ever moves to its own instance.
    gateway_database_url: str = ""

    # Agent orchestration
    anthropic_api_key: str = ""
    case_timeout_seconds: float = 60.0

    # CORS
    allowed_origins: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def mcp_server_args_list(self) -> list[str]:
        return self.mcp_server_args.split()

    @property
    def gateway_database_url_resolved(self) -> str:
        """The gateway DB URL, rewritten to the asyncpg driver scheme."""
        url = self.gateway_database_url or self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
