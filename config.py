"""Configuration management for the OzBargain deal agent."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    # Targets
    target_url: str = os.getenv(
        "TARGET_URL",
        "https://www.ozbargain.com.au/tag/gift-card",
    )

    # Runtime
    scrape_interval: int = int(os.getenv("SCRAPE_INTERVAL", "1800"))
    headless: bool = os.getenv("HEADLESS", "true").lower() in {
        "1",
        "true",
        "yes",
        "y",
    }
    debug: bool = os.getenv("DEBUG", "false").lower() in {
        "1",
        "true",
        "yes",
        "y",
    }
    user_agent: str = os.getenv("USER_AGENT", "")

    # Persistence
    sqlite_path: str = os.getenv("SQLITE_PATH", "deals.db")

    # LLM
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai").lower()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv(
        "ANTHROPIC_MODEL",
        "claude-3-5-haiku-latest",
    )

    # Notifications
    discord_webhook_url: str = os.getenv("DISCORD_WEBHOOK_URL", "")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Logging
    log_file: str = os.getenv("LOG_FILE", "agent.log")
