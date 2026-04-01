"""Main orchestrator for the agentic OzBargain freebie monitor."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import requests

from brain import DealBrain
from config import Config
from database import DealDatabase
from scraper import Deal, OzBargainScraper


def setup_logger(log_file: str) -> logging.Logger:
    """Configure file logger for long-running agent process."""
    logger = logging.getLogger("ozbargain_agent")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger


def send_discord_alert(webhook_url: str, deal: Deal) -> bool:
    """Dispatch a Discord webhook alert for a valid deal."""
    if not webhook_url:
        return False
    payload = {"content": f"New OzBargain freebie detected!\n**{deal.title}**\n{deal.link}\n"}
    response = requests.post(webhook_url, json=payload, timeout=15)
    return response.ok


def send_telegram_alert(bot_token: str, chat_id: str, deal: Deal) -> bool:
    """Dispatch a Telegram bot message alert for a valid deal."""
    if not bot_token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": f"New OzBargain freebie detected!\n{deal.title}\n{deal.link}"}
    response = requests.post(url, json=payload, timeout=15)
    return response.ok


def notify(config: Config, deal: Deal, logger: logging.Logger) -> None:
    """Send alerts to available channels with graceful failure logging."""
    sent_discord = send_discord_alert(config.discord_webhook_url, deal)
    sent_telegram = send_telegram_alert(config.telegram_bot_token, config.telegram_chat_id, deal)
    if sent_discord or sent_telegram:
        logger.info("Notification sent for deal_id=%s", deal.deal_id)
    else:
        logger.warning("No notification channel configured or send failed for deal_id=%s", deal.deal_id)


def process_deal(
    deal: Deal,
    db: DealDatabase,
    brain: DealBrain,
    config: Config,
    logger: logging.Logger,
) -> None:
    """Run complete agentic evaluation + action pipeline for one deal."""
    if db.has_seen(deal.deal_id):
        logger.info("Skipping seen deal_id=%s", deal.deal_id)
        return

    if not DealBrain.keyword_prefilter(deal.title, deal.description):
        logger.info("Prefilter rejected deal_id=%s", deal.deal_id)
        return

    decision = brain.classify(deal.title, deal.description)
    logger.info("LLM decision for deal_id=%s: %s", deal.deal_id, decision)
    if decision == "TRUE":
        notify(config, deal, logger)
        db.mark_seen(deal.deal_id, deal.title, deal.link)
        logger.info("Stored deal_id=%s", deal.deal_id)


def run_once(
    scraper: OzBargainScraper,
    db: DealDatabase,
    brain: DealBrain,
    config: Config,
    logger: logging.Logger,
) -> Optional[bool]:
    """Execute one scrape-filter-action cycle; returns forbidden flag."""
    deals, forbidden = asyncio.run(scraper.fetch_freebie_deals())
    logger.info("Scraped %d deals; forbidden=%s", len(deals), forbidden)
    if forbidden:
        return True

    for deal in deals:
        process_deal(deal, db, brain, config, logger)
    return False


def main() -> None:
    """Continuous agent loop with resilience, backoff, and logging."""
    config = Config()
    logger = setup_logger(config.log_file)
    db = DealDatabase(config.sqlite_path)
    headless = False if config.debug else config.headless
    scraper = OzBargainScraper(
        target_url=config.target_url,
        headless=headless,
        user_agent=config.user_agent,
    )
    brain = DealBrain(config)

    backoff_seconds = config.scrape_interval
    logger.info("Agent started. headless=%s interval=%s", headless, config.scrape_interval)

    while True:
        try:
            forbidden = run_once(scraper, db, brain, config, logger)
            if forbidden:
                backoff_seconds = min(backoff_seconds * 2, 6 * 3600)
                logger.warning("403 detected. Backoff increased to %s seconds", backoff_seconds)
            else:
                backoff_seconds = config.scrape_interval
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unhandled error in main loop: %s", exc)

        time.sleep(backoff_seconds)


if __name__ == "__main__":
    main()
