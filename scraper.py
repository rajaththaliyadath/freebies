"""Playwright scraping logic for OzBargain freebies pages."""

from __future__ import annotations

import asyncio
import random
import re
from dataclasses import dataclass
from typing import List
from urllib.parse import urljoin

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

try:
    from playwright_stealth import stealth_async
except ImportError:  # pragma: no cover - compatibility for newer package API
    stealth_async = None
    from playwright_stealth import Stealth

OZBARGAIN_BASE_URL = "https://www.ozbargain.com.au"
DEFAULT_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
]


@dataclass(frozen=True)
class Deal:
    """Single OzBargain deal item normalized for downstream processing."""

    deal_id: str
    title: str
    link: str
    description: str


def extract_deal_id(link: str) -> str:
    """Extract numeric deal ID from OzBargain URL path."""
    match = re.search(r"/node/(\d+)", link)
    return match.group(1) if match else link.rstrip("/").split("/")[-1]


class OzBargainScraper:
    """Scraper wrapper with stealth and anti-detection behaviors."""

    def __init__(self, target_url: str, headless: bool, user_agent: str = "") -> None:
        self.target_url = target_url
        self.headless = headless
        self.user_agent = user_agent

    async def _new_context(self, browser: Browser) -> BrowserContext:
        ua = self.user_agent or random.choice(DEFAULT_USER_AGENTS)
        return await browser.new_context(
            user_agent=ua,
            viewport={"width": 1366, "height": 768},
            locale="en-AU",
            timezone_id="Australia/Sydney",
        )

    async def _human_pause(self) -> None:
        await asyncio.sleep(random.uniform(3, 7))

    async def _apply_stealth(self, page: Page) -> None:
        """Apply stealth hooks across supported playwright-stealth versions."""
        if stealth_async is not None:
            await stealth_async(page)
            return
        await Stealth().apply_stealth_async(page)

    async def fetch_freebie_deals(self) -> tuple[List[Deal], bool]:
        """
        Fetch deals and indicate if a likely 403 block occurred.

        Returns:
            tuple[List[Deal], bool]: (deals, forbidden_detected)
        """
        deals: List[Deal] = []
        forbidden_detected = False

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.headless)
            context = await self._new_context(browser)
            page = await context.new_page()

            try:
                await self._apply_stealth(page)
                await self._human_pause()

                response = await page.goto(self.target_url, wait_until="domcontentloaded")
                if response and response.status == 403:
                    forbidden_detected = True
                    return deals, forbidden_detected

                # OzBargain pages can keep background requests open; avoid strict networkidle waits.
                await page.wait_for_timeout(3500)
                await self._human_pause()

                title_nodes = page.locator("h2.title a")
                count = await title_nodes.count()
                for index in range(count):
                    anchor = title_nodes.nth(index)
                    title = (await anchor.inner_text()).strip()
                    href = await anchor.get_attribute("href")
                    if not href:
                        continue

                    absolute_link = urljoin(OZBARGAIN_BASE_URL, href)
                    deal_id = extract_deal_id(absolute_link)

                    wrapper = anchor.locator("xpath=ancestor::div[contains(@class, 'node')]")
                    description_node = wrapper.locator("div.content")
                    description = ""
                    if await description_node.count() > 0:
                        description = (await description_node.first.inner_text()).strip()

                    deals.append(
                        Deal(
                            deal_id=deal_id,
                            title=title,
                            link=absolute_link,
                            description=description,
                        )
                    )
            finally:
                await context.close()
                await browser.close()

        return deals, forbidden_detected
