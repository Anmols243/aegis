"""Settings, loaded from environment variables and an optional `.env` file.

Secrets (API keys, webhook secret) are only ever read here and never logged.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",
                                      extra="ignore")

    # --- service ---
    aegis_env: str = "dev"
    aegis_api_key: str | None = None          # required on every non-public route when set
    database_url: str = "sqlite+aiosqlite:///./data/aegis.db"
    data_dir: str = "data"
    cors_origins: Annotated[list[str], NoDecode] = []  # comma-separated; empty = no CORS
    trust_proxy_headers: bool = False         # honour X-Forwarded-For from an authenticated proxy
    public_base_url: str = ""                 # e.g. https://aegis.example; used in share links
    aegis_secret_key: str | None = None       # 32 bytes base64url; encrypts mailbox credentials

    # --- privacy ---
    private_retention_days: int = 7           # pasted / inbox mail: body purged after this
    inbox_public: bool = False                # list AgentBoxD-forwarded mail publicly (demo only)
    mailbox_poll_interval_s: int = 60
    mailbox_max_per_poll: int = 20

    # --- Sign in with Google (Gmail API). Unset = the button is hidden. ---
    google_client_id: str | None = None
    google_client_secret: str | None = None
    # Must match the OAuth client exactly; it is the frontend origin + this path.
    google_redirect_uri: str = "http://localhost:3000/api/v1/oauth/google/callback"

    # --- Sign in with Microsoft (Outlook, Hotmail, Live, Microsoft 365). Unset = hidden. ---
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    microsoft_redirect_uri: str = "http://localhost:3000/api/v1/oauth/microsoft/callback"

    # --- limits ---
    max_upload_bytes: int = 2 * 1024 * 1024
    max_webhook_bytes: int = 5 * 1024 * 1024
    submit_rate_per_min: float = 12.0
    submit_burst: int = 10
    general_rate_per_min: float = 240.0
    general_burst: int = 120

    # --- workers ---
    worker_concurrency: int = 2
    max_attempts: int = 3

    # --- LLM (Featherless, OpenAI-compatible) ---
    featherless_api_key: str | None = None
    llm_base_url: str = "https://api.featherless.ai/v1"
    llm_max_concurrency: int = 2
    llm_timeout_s: float = 120.0
    model_triage: str = "moonshotai/Kimi-K3"
    model_forensic: str = "moonshotai/Kimi-K3"
    model_vision: str = "Qwen/Qwen3-VL-30B-A3B-Instruct"

    # --- stages ---
    vision_enabled: bool = True
    sandbox_enabled: bool = True

    # --- AgentBoxD ---
    agentboxd_api_key: str | None = None
    agentboxd_webhook_secret: str | None = None
    agentboxd_inbox_id: str | None = None
    agentboxd_inbox_address: str | None = None
    # long-poll the inbox for new mail; unset = on unless a webhook secret is configured
    agentboxd_poll: bool | None = None
    agentboxd_auto_reply: bool = True         # reply in-thread with the verdict card
    # In a workspace that screens agent mail, take mail before its check finishes (no
    # permission needed) and, with a key that has messages:release, mail it held.
    agentboxd_include_unscreened: bool = True
    agentboxd_include_held: bool = False
    agentboxd_base_url: str = "https://api.agentboxd.com"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def llm_configured(self) -> bool:
        return bool(self.featherless_api_key)

    @property
    def google_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    def oauth_client(self, provider: str) -> tuple[str, str, str] | None:
        """(client id, secret, redirect URI) for a sign-in provider, or None if unset."""
        cid = getattr(self, f"{provider}_client_id", None)
        secret = getattr(self, f"{provider}_client_secret", None)
        if not (cid and secret):
            return None
        return cid, secret, getattr(self, f"{provider}_redirect_uri")

    @property
    def agentboxd_configured(self) -> bool:
        return bool(self.agentboxd_api_key and self.agentboxd_inbox_id)

    @property
    def agentboxd_polling(self) -> bool:
        """Check the inbox ourselves: explicit AGENTBOXD_POLL, else whenever no webhook delivers mail."""
        if not self.agentboxd_configured:
            return False
        if self.agentboxd_poll is not None:
            return self.agentboxd_poll
        return not self.agentboxd_webhook_secret


@lru_cache
def get_settings() -> Settings:
    return Settings()
