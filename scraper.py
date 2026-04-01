import json
import random
import re
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TARGET_URLS = [
    "https://www.ozbargain.com.au/deals/freebies",
    "https://www.ozbargain.com.au/freebies",
    "https://www.ozbargain.com.au/tag/freebie",
]
DEALS_FILE = Path("deals.json")
SCRAPE_META_FILE = Path("scrape_meta.json")
STATE_CODES = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


def random_delay(low: float = 0.8, high: float = 2.3) -> None:
    time.sleep(random.uniform(low, high))


def parse_vote_count(raw_text: str) -> int:
    if not raw_text:
        return 0
    match = re.search(r"-?\d+", raw_text.replace(",", ""))
    return int(match.group()) if match else 0


def load_existing_deals() -> List[Dict]:
    if not DEALS_FILE.exists():
        return []
    try:
        with DEALS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def load_scrape_meta() -> Dict:
    if not SCRAPE_META_FILE.exists():
        return {}
    try:
        with SCRAPE_META_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_deals(deals: List[Dict]) -> None:
    with DEALS_FILE.open("w", encoding="utf-8") as f:
        json.dump(deals, f, indent=2, ensure_ascii=False)


def save_scrape_meta(meta: Dict) -> None:
    with SCRAPE_META_FILE.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def parse_posted_at(article: BeautifulSoup) -> str:
    submitted = article.select_one(".submitted")
    submitted_text = submitted.get_text(" ", strip=True) if submitted else ""
    match = re.search(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}:\d{2})", submitted_text)
    if not match:
        return ""
    try:
        dt = datetime.strptime(f"{match.group(1)} {match.group(2)}", "%d/%m/%Y %H:%M")
        return dt.isoformat()
    except ValueError:
        return ""


def extract_locations(text: str) -> List[str]:
    upper = (text or "").upper()
    found = [state for state in STATE_CODES if re.search(rf"\b{state}\b", upper)]
    return sorted(set(found))


def detect_expired(title: str, content: str, article: BeautifulSoup) -> bool:
    classes = " ".join(article.get("class", []))
    haystack = f"{title} {content} {classes}".lower()
    expiry_keywords = ["expired", "ended", "no longer", "deal over", "finished"]
    return any(keyword in haystack for keyword in expiry_keywords)


def verify_expired_from_deal_page(link: str) -> bool:
    try:
        req = urllib.request.Request(
            link,
            headers={"User-Agent": random.choice(USER_AGENTS)},
        )
        with urllib.request.urlopen(req, timeout=18) as response:
            html = response.read().decode("utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text(" ", strip=True).lower()
        strong_signals = [
            "this deal has expired",
            "deal expired",
            "expired deal",
            "offer expired",
            "no longer available",
        ]
        if any(signal in page_text for signal in strong_signals):
            return True
        return False
    except Exception:
        return False


def scrape_freebies() -> List[Dict]:
    ua = random.choice(USER_AGENTS)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=ua,
            viewport={"width": 1400, "height": 900},
            locale="en-AU",
        )
        page = context.new_page()

        random_delay(1.0, 2.0)
        html = ""
        for target_url in TARGET_URLS:
            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            random_delay(1.2, 2.8)
            page.mouse.wheel(0, random.randint(400, 1200))
            random_delay(0.7, 1.5)
            html = page.content()
            if "node-ozbdeal" in html and "404 Not Found" not in page.title():
                break

        context.close()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    scraped: List[Dict] = []

    for article in soup.select("div.node-ozbdeal"):
        title_tag = article.select_one("h2.title a")
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        link = title_tag.get("href", "").strip()
        if link and link.startswith("/"):
            link = f"https://www.ozbargain.com.au{link}"

        image_tag = article.select_one(".foxshot-container img")
        image_url = ""
        if image_tag:
            image_url = (
                image_tag.get("src")
                or image_tag.get("data-src")
                or image_tag.get("data-original")
                or ""
            ).strip()
            if image_url and image_url.startswith("//"):
                image_url = f"https:{image_url}"

        category_tag = article.select_one(".links .tag a")
        category = category_tag.get_text(strip=True) if category_tag else "General"
        content_text = article.select_one(".content").get_text(" ", strip=True) if article.select_one(".content") else ""

        vote_tag = article.select_one(".n-vote .nvb.voteup span:last-child")
        vote_count = parse_vote_count(vote_tag.get_text(" ", strip=True) if vote_tag else "")
        posted_at = parse_posted_at(article)
        locations = extract_locations(title + " " + content_text)
        is_expired = detect_expired(title, content_text, article)
        if not is_expired:
            is_expired = verify_expired_from_deal_page(link)

        if not link:
            continue

        scraped.append(
            {
                "title": title,
                "link": link,
                "image_url": image_url,
                "category": category,
                "votes": vote_count,
                "posted_at": posted_at,
                "locations": locations,
                "is_expired": is_expired,
            }
        )

    return scraped


def deduplicate_deals(existing: List[Dict], new_deals: List[Dict]) -> Tuple[List[Dict], int]:
    existing_by_link = {deal.get("link"): deal for deal in existing if deal.get("link")}
    fresh_count = 0

    for old in existing_by_link.values():
        old["is_new"] = False

    for deal in new_deals:
        link = deal.get("link")
        if not link:
            continue
        if link in existing_by_link:
            prev = existing_by_link[link]
            deal["discovered_at"] = prev.get("discovered_at", deal.get("posted_at", ""))
            deal["is_new"] = False
        else:
            deal["discovered_at"] = deal.get("posted_at", "")
            deal["is_new"] = True
            fresh_count += 1
        existing_by_link[link] = deal

    combined = list(existing_by_link.values())
    combined.sort(key=lambda d: d.get("posted_at", ""), reverse=True)
    print(f"Scraped: {len(new_deals)} | New added: {fresh_count} | Total saved: {len(combined)}")
    return combined, fresh_count


def run_scrape_cycle() -> Dict:
    existing = load_existing_deals()
    fresh = scrape_freebies()
    all_deals, fresh_count = deduplicate_deals(existing, fresh)
    scraped_at = datetime.now().isoformat()
    for deal in all_deals:
        deal["scraped_at"] = scraped_at
    save_deals(all_deals)
    meta = {
        "last_scraped_at": scraped_at,
        "scraped_count": len(fresh),
        "new_count": fresh_count,
        "total_count": len(all_deals),
    }
    save_scrape_meta(meta)
    return meta


def main() -> None:
    meta = run_scrape_cycle()
    print(
        f"Last scraped at: {meta['last_scraped_at']} | Scraped: {meta['scraped_count']} | New: {meta['new_count']} | Total: {meta['total_count']}"
    )


if __name__ == "__main__":
    main()
