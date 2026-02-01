"""
Configuration management for Canva-NotebookLM integration system.

All configuration is loaded from environment variables via Pydantic Settings.
Secrets must be stored in .env file (development) or Vault (production).
No secrets are hardcoded in this file.

Usage:
    from src.config import settings
    print(settings.database_url)
    print(settings.environment)
"""

import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, SecretStr, validator
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration."""

    host: str = Field("127.0.0.1", description="PostgreSQL host (use host.docker.internal on macOS/Windows if needed)")
    port: int = Field(55432, description="PostgreSQL port (host-mapped; container listens on 5432)")
    username: str = Field("canva_user", description="PostgreSQL username")
    password: SecretStr = Field(default="canva_password_dev", description="PostgreSQL password (secret; dev default)")
    database: str = Field("canva_notebooklm_db", description="PostgreSQL database name")
    pool_size: int = Field(10, description="Connection pool size")
    pool_pre_ping: bool = Field(True, description="Enable connection health checks")
    echo: bool = Field(False, description="Enable SQL query logging")

    @property
    def url(self) -> str:
        """Build PostgreSQL or SQLite connection URL based on host."""
        # Support SQLite for testing (when host contains :memory: or is a .db path)
        if self.host == ":memory:" or self.host.endswith(".db"):
            return f"sqlite+aiosqlite:///{self.host}"
        # PostgreSQL
        return (
            f"postgresql+asyncpg://{self.username}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    class Config:
        env_prefix = "DATABASE_"


class RedisSettings(BaseSettings):
    """Redis configuration for caching and task queue."""

    host: str = Field("localhost", description="Redis host")
    port: int = Field(6379, description="Redis port")
    db: int = Field(0, description="Redis database number")
    password: Optional[SecretStr] = Field(None, description="Redis password (optional)")
    ssl: bool = Field(False, description="Enable SSL/TLS connection")
    decode_responses: bool = Field(False, description="Auto-decode responses")

    @property
    def url(self) -> str:
        """Build Redis connection URL."""
        scheme = "rediss" if self.ssl else "redis"
        auth = f":{self.password.get_secret_value()}@" if self.password else ""
        return f"{scheme}://{auth}{self.host}:{self.port}/{self.db}"

    class Config:
        env_prefix = "REDIS_"


class CanvaSettings(BaseSettings):
    """Canva API credentials and configuration."""

    client_id: SecretStr = Field(default="dev_client_id", description="Canva OAuth 2.0 client ID (dev default; set CANVA_CLIENT_ID for production)")
    client_secret: SecretStr = Field(default="dev_client_secret", description="Canva OAuth 2.0 client secret (dev default; set CANVA_CLIENT_SECRET for production)")
    redirect_uri: str = Field(
        "http://127.0.0.1:8000/api/v1/auth/canva/callback",
        description="Canva OAuth redirect URI",
    )
    api_base_url: str = Field(
        "https://api.canva.com", description="Canva API base URL"
    )
    rate_limit_requests: int = Field(100, description="Requests per rate_limit_window")
    rate_limit_window_seconds: int = Field(
        60, description="Rate limit window in seconds"
    )
    max_retries: int = Field(3, description="Maximum retry attempts")
    retry_backoff_initial_ms: int = Field(100, description="Initial backoff in ms")
    retry_backoff_multiplier: float = Field(2.0, description="Backoff multiplier")
    retry_backoff_max_ms: int = Field(30000, description="Max backoff in ms")

    class Config:
        env_prefix = "CANVA_"


class NotebookLMSettings(BaseSettings):
    """NotebookLM API credentials and configuration."""

    api_key: SecretStr = Field(default="dev_api_key", description="NotebookLM API key (dev default; set NOTEBOOKLM_API_KEY for production)")
    api_base_url: str = Field(
        "https://notebooklm.google.com/api",
        description="NotebookLM API base URL",
    )
    poll_interval_seconds: int = Field(5, description="Status polling interval")
    poll_timeout_seconds: int = Field(600, description="Max polling duration (10 min)")
    rate_limit_requests: int = Field(50, description="Requests per rate_limit_window")
    rate_limit_window_seconds: int = Field(60, description="Rate limit window")
    max_retries: int = Field(5, description="Maximum retry attempts")
    retry_backoff_initial_ms: int = Field(200, description="Initial backoff in ms")
    retry_backoff_multiplier: float = Field(2.0, description="Backoff multiplier")
    retry_backoff_max_ms: int = Field(60000, description="Max backoff in ms")

    class Config:
        env_prefix = "NOTEBOOKLM_"


class LLMSettings(BaseSettings):
    """LLM provider configuration (OpenAI, Claude, etc.)."""

    provider: str = Field("openai", description="LLM provider (openai, claude, custom)")
    api_key: SecretStr = Field(default="dev_api_key", description="LLM API key (dev default; set LLM_API_KEY for production)")
    model: str = Field("gpt-4", description="Model name/ID")
    api_base_url: Optional[str] = Field(
        None, description="Custom API endpoint (for self-hosted)"
    )
    timeout_seconds: int = Field(30, description="API request timeout")
    max_tokens: int = Field(2000, description="Max tokens in response")
    temperature: float = Field(0.7, description="Temperature for sampling")

    @validator("temperature")
    def validate_temperature(cls, v: float) -> float:
        """Ensure temperature is in valid range."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v

    class Config:
        env_prefix = "LLM_"


class ObservabilitySettings(BaseSettings):
    """Logging, tracing, and metrics configuration."""

    log_level: str = Field("INFO", description="Root logger level")
    log_format: str = Field(
        "json", description="Log format (json or text)"
    )
    json_log_indent: Optional[int] = Field(
        None, description="JSON log indentation (None for compact)"
    )
    enable_request_logging: bool = Field(True, description="Log HTTP requests/responses")
    enable_tracing: bool = Field(False, description="Enable distributed tracing")
    jaeger_enabled: bool = Field(False, description="Export traces to Jaeger")
    jaeger_agent_host: str = Field("localhost", description="Jaeger agent host")
    jaeger_agent_port: int = Field(6831, description="Jaeger agent port")
    metrics_enabled: bool = Field(True, description="Enable Prometheus metrics")
    metrics_port: int = Field(8001, description="Prometheus metrics port")
    sentry_enabled: bool = Field(False, description="Enable Sentry error tracking")
    sentry_dsn: Optional[SecretStr] = Field(None, description="Sentry DSN URL")

    class Config:
        env_prefix = "OBSERVABILITY_"


class AuthSettings(BaseSettings):
    """API authentication and authorization."""

    jwt_secret: SecretStr = Field(default="dev_jwt_secret_unsafe_demo_only", description="JWT signing secret (dev default; set AUTH_JWT_SECRET for production)")
    jwt_algorithm: str = Field("HS256", description="JWT algorithm (HS256, RS256)")
    jwt_expiration_hours: int = Field(24, description="JWT token expiration")
    oauth_state_timeout_seconds: int = Field(600, description="OAuth state timeout")
    enable_api_key_auth: bool = Field(True, description="Enable API key authentication")

    class Config:
        env_prefix = "AUTH_"


class VaultSettings(BaseSettings):
    """HashiCorp Vault configuration (production secrets)."""

    enabled: bool = Field(False, description="Enable Vault integration")
    address: str = Field("http://localhost:8200", description="Vault server address")
    token: Optional[SecretStr] = Field(None, description="Vault authentication token")
    namespace: str = Field("secret", description="Vault namespace/path")
    role: Optional[str] = Field(None, description="Vault role for K8s auth")

    class Config:
        env_prefix = "VAULT_"


class Settings(BaseSettings):
    """Main application settings."""

    # Environment
    environment: str = Field("development", description="Environment (development, staging, production)")
    debug: bool = Field(False, description="Enable debug mode")
    project_name: str = Field(
        "canva-notebooklm-agent", description="Project name"
    )
    version: str = Field("0.1.0", description="Application version")

    # Server
    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8000, description="Server port")
    workers: int = Field(1, description="Gunicorn workers")
    reload: bool = Field(False, description="Auto-reload on code change")

    # Subsystems
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    canva: CanvaSettings = Field(default_factory=CanvaSettings)
    notebooklm: NotebookLMSettings = Field(default_factory=NotebookLMSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    vault: VaultSettings = Field(default_factory=VaultSettings)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("environment")
    def validate_environment(cls, v: str) -> str:
        """Ensure valid environment."""
        valid = {"development", "staging", "production"}
        if v not in valid:
            raise ValueError(f"Environment must be one of {valid}")
        return v

    @validator("debug", pre=True, always=True)
    def set_debug_mode(cls, v: bool, values: dict) -> bool:
        """Debug defaults to True only in development."""
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        environment = values.get("environment", "development")
        return environment == "development" if v is None else v

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"

    @property
    def REDIS_URL(self) -> str:
        """Get Redis connection URL (backward compatibility property)."""
        return self.redis.url

    @property
    def DATABASE_URL(self) -> str:
        """Get database connection URL (backward compatibility property)."""
        return self.database.url


# Load .env file explicitly before creating settings instance
load_dotenv(".env")

# Global settings instance
settings = Settings()

# Configure logging based on settings
def setup_logging() -> None:
    """Configure root logger based on settings."""
    logging.basicConfig(
        level=getattr(logging, settings.observability.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        if settings.observability.log_format == "text"
        else None,
    )
