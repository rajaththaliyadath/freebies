import json
import random
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import cloudscraper
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

TARGET_URLS = [
    "https://www.ozbargain.com.au/deals/freebies",
    "https://www.ozbargain.com.au/freebies",
    "https://www.ozbargain.com.au/tag/freebie",
]
STUDENT_BEANS_PAGES = [
    "https://www.studentbeans.com/au/trending-discounts",
    "https://www.studentbeans.com/student-discount/au/cats/fashion",
    "https://www.studentbeans.com/student-discount/au/cats/tech-mobile",
    "https://www.studentbeans.com/student-discount/au/cats/food-drink",
    "https://www.studentbeans.com/student-discount/au/cats/sports-outdoors",
    "https://www.studentbeans.com/student-discount/au/cats/entertainment",
    "https://www.studentbeans.com/student-discount/au/cats/health-beauty",
    "https://www.studentbeans.com/student-discount/au/cats/travel",
]
UNIDAYS_BRAND_URL = "https://www.myunidays.com/AU/en-AU/all-brands"
BASE_STUDENT_BEANS = "https://www.studentbeans.com"
BASE_UNIDAYS = "https://www.myunidays.com"
SLICKDEALS_RSS_URLS = [
    "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1",
    "https://slickdeals.net/newsearch.php?mode=popdeals&searcharea=deals&rss=1",
    "https://slickdeals.net/newsearch.php?mode=hotdeals&searcharea=deals&rss=1",
]
CONTENT_ENCODED_TAG = "{http://purl.org/rss/1.0/modules/content/}encoded"
RSSIMAGE_FROM_HTML = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.I)

DEALS_FILE = Path("deals.json")
SCRAPE_META_FILE = Path("scrape_meta.json")
STATE_CODES = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

# Order matters: first match wins. Put specific / low-false-positive topics before broad ones.
# Gaming uses strict phrases & tokens — avoid bare "game" / "switch" (huge false-positive rate).
TOPIC_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("Shoes", ["shoe", "sneaker", "footwear", "crocs", "converse", "vans", "asics", "nike", "adidas", "puma", "jordan", "new balance", "skechers", "uggs", "dr martens", "boots", "sandals", "slides", "loafer", "oxford shoe", "running shoe"]),
    (
        "Food",
        [
            "food",
            "pizza",
            "uber eats",
            "deliveroo",
            "menulog",
            "coffee",
            "restaurant",
            "grocery",
            "mcdonald",
            "kfc",
            "domino",
            "starbucks",
            "doordash",
            "liquor",
            "wine",
            "beer",
            "snack",
            "chocolate",
            "candy",
            "burger",
            "sushi",
            "bakery",
            "costco food",
            "woot grocery",
            "tea",
            "meat",
            "milk",
            "cereal",
        ],
    ),
    ("Beauty", ["beauty", "sephora", "mecca", "skincare", "cosmetic", "makeup", "fragrance", "haircare", "lush", "derma", "moisturizer", "perfume", "nail polish", "lipstick"]),
    ("Travel", ["travel", "hotel", "flight", "booking", "airbnb", "airline", "qantas", "jetstar", "virgin australia", "hostel", "luggage", "vacation", "car rental", "expedia", "trivago"]),
    (
        "Sports",
        [
            "fitness tracker",
            "golf club",
            "tennis racket",
            "basketball",
            "football cleat",
            "yoga mat",
            "peloton",
            "sportswear",
            "nike pro",
            "decathlon",
            "rebelsport",
            "dumbbell",
            "treadmill",
            "bowflex",
            "cycling shoe",
            "snowboard",
            "skiing",
            "skis",
            "sport coat",
            "sports bra",
            "sport",
            "sports",
            "gym",
            "bicycle",
            "e-bike",
        ],
    ),
    ("Books", ["magazine", "kindle", "audible", "textbook", "ebook", "graphic novel", "manga volume", "book", "books", "novel", "paperback"]),
    (
        "Finance",
        [
            "bank",
            "finance",
            "insurance",
            "afterpay",
            "zip pay",
            "credit card",
            "mortgage",
            "brokerage",
            "superannuation",
            "401k",
            "refinance",
            "super fund",
            "stock trade",
            "etf ",
            "crypto",
            "bitcoin",
        ],
    ),
    (
        "Gaming",
        [
            "gaming",
            "video game",
            "videogame",
            "gamer",
            "playstation",
            "xbox",
            "nintendo",
            "nintendo switch",
            "steam deck",
            "steam",
            "epic games",
            "ubisoft",
            "activision",
            "blizzard",
            "battle.net",
            "riot games",
            "ea play",
            "rockstar games",
            "game pass",
            "xbox game pass",
            "ps5",
            "ps4",
            "ps vr",
            "psvr",
            "meta quest",
            "oculus",
            "twitch",
            "discord nitro",
            "razer",
            "steelseries",
            "elgato",
            "astro a",
            "gaming headset",
            "gaming chair",
            "gaming mouse",
            "gaming keyboard",
            "gaming pc",
            "gaming laptop",
            "gaming monitor",
            "gamestop",
            "switch game",
            "switch oled",
            "pokemon",
        ],
    ),
    (
        "Tech",
        [
            "chromebook",
            "surface pro",
            "surface laptop",
            "laptop",
            "computer",
            "macbook",
            "ipad",
            "iphone",
            "samsung galaxy",
            "tablet",
            "monitor",
            "ssd",
            "nvme",
            "router",
            "mesh wifi",
            "cpu",
            "gpu",
            "graphics card",
            "mechanical keyboard",
            "webcam",
            "printer",
            "software license",
            "microsoft 365",
            "windows 11",
            "television",
            "oled tv",
            "qled",
            "earbuds",
            "airpods",
            "headphones",
            "bose",
            "sony wh-",
            "usb-c",
            "charger",
            "power bank",
            "smart watch",
            "fitbit",
            "galaxy watch",
            "raspberry pi",
            "arduino",
            "tech",
            "apple",
            "samsung",
            "google pixel",
            "chromecast",
            "dell",
            "hp",
            "lenovo",
            "asus",
            "msi",
            "canon",
            "nikon",
            "mobile",
            "android",
            "software",
            "spotify",
            "nas",
        ],
    ),
    (
        "Fashion",
        [
            "fashion",
            "asos",
            "shein",
            "clothing",
            "apparel",
            "zara",
            "h&m",
            "cotton on",
            "princess polly",
            "gymshark",
            "culture kings",
            "uniqlo",
            "handbag",
            "wallet leather",
            "jacket",
            "jeans",
            "dress",
            "sunglasses",
            "watch band",
            "tee shirt",
            "hoodie",
        ],
    ),
    (
        "Entertainment",
        [
            "cinema",
            "movie ticket",
            "imax",
            "streaming",
            "netflix",
            "hulu",
            "disney+",
            "hbo max",
            "crunchyroll",
            "paramount+",
            "concert ticket",
            "spotify premium",
            "festival pass",
            "theatre",
            "theater",
            "broadway",
            "board game",
            "lego",
            "puzzle 1000",
        ],
    ),
    (
        "Home",
        [
            "furniture",
            "mattress",
            "bed frame",
            "sofa",
            "couch",
            "dining set",
            "vacuum",
            "air fryer",
            "instant pot",
            "kitchenaid",
            "bedding",
            "bath towel",
            "bunnings",
            "ikea",
            "home depot",
            "lowes",
            "dyson",
            "robot mop",
            "google nest",
            "smart home hub",
            "kmart",
            "target",
            "costco",
            "decor",
        ],
    ),
]


def _topic_keyword_matches(haystack_lc: str, kw: str) -> bool:
    """Match a keyword against padded lowercase haystack. Phrases use substring; single
    alphanumeric tokens use word boundaries to avoid pineapple→apple, transport→sport, etc."""
    if not kw:
        return False
    k = kw.strip().lower()
    if not k:
        return False
    if " " in k:
        return k in haystack_lc
    if not re.match(r"^[a-z0-9]+$", k):
        return k in haystack_lc
    return re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", haystack_lc) is not None


def random_delay(low: float = 0.8, high: float = 2.3) -> None:
    time.sleep(random.uniform(low, high))


def parse_vote_count(raw_text: str) -> int:
    if not raw_text:
        return 0
    match = re.search(r"-?\d+", raw_text.replace(",", ""))
    return int(match.group()) if match else 0


def infer_topic(title: str, source_category: str = "", page_hint: str = "") -> str:
    haystack = f" {title} {source_category} {page_hint} ".lower()
    for topic, keywords in TOPIC_KEYWORDS:
        for kw in keywords:
            if _topic_keyword_matches(haystack, kw):
                return topic
    return "General"


def parse_discount_label(text: str) -> str:
    t = text or ""
    m = re.search(r"(?:up to\s+)?\d+\s*%\s*off", t, re.I)
    if m:
        return m.group(0).strip()
    m2 = re.search(r"\d+\s*%\s*(?:student|sitewide|off)", t, re.I)
    if m2:
        return m2.group(0).strip()
    if re.search(r"\bfree\b", t, re.I):
        return "Free offer"
    return ""


def infer_deal_type(title: str, discount_label: str, source: str) -> str:
    t = (title or "").lower()
    if source == "slickdeals":
        if re.search(r"\bfree\b", t) and not re.search(r"[\$£€]\s*\d", t) and "%" not in t[:120]:
            return "free"
        return "discount"
    if source == "ozbargain":
        if "free" in t and "%" not in t[:80]:
            return "free"
        if "%" in t or "off" in t or "discount" in t:
            return "discount"
        return "free"
    if discount_label and "free" in discount_label.lower():
        return "free"
    if discount_label:
        return "discount"
    if "%" in t or " off" in t:
        return "discount"
    return "discount"


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
        return any(signal in page_text for signal in strong_signals)
    except Exception:
        return False


def _find_nearby_image(anchor: BeautifulSoup) -> str:
    el = anchor
    for _ in range(8):
        if el is None:
            break
        img = el.find("img", src=True)
        if img:
            src = (img.get("src") or img.get("data-src") or "").strip()
            if src and "placeholder" not in src.lower():
                if src.startswith("//"):
                    src = f"https:{src}"
                return src
        el = el.parent if hasattr(el, "parent") else None
    return ""


SB_BRAND_LINK = re.compile(r"^/student-discount/au/(?!cats/)([a-z0-9-]+)")


def scrape_ozbargain() -> List[Dict]:
    ua = random.choice(USER_AGENTS)
    scraped: List[Dict] = []

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
        raw_cat = category_tag.get_text(strip=True) if category_tag else "General"
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

        discount_label = parse_discount_label(title)
        topic = infer_topic(title, raw_cat)
        deal_type = infer_deal_type(title, discount_label, "ozbargain")

        scraped.append(
            {
                "title": title,
                "link": link,
                "image_url": image_url,
                "category": topic,
                "source_category": raw_cat,
                "votes": vote_count,
                "posted_at": posted_at,
                "locations": locations,
                "is_expired": is_expired,
                "source": "ozbargain",
                "deal_type": deal_type,
                "discount_label": discount_label or ("Discount" if deal_type == "discount" else ""),
            }
        )

    return scraped


def scrape_student_beans() -> List[Dict]:
    ua = random.choice(USER_AGENTS)
    seen_paths: Set[str] = set()
    scraped: List[Dict] = []
    page_hint_map = {
        "fashion": "Fashion",
        "tech-mobile": "Tech",
        "food-drink": "Food",
        "sports-outdoors": "Sports",
        "entertainment": "Entertainment",
        "health-beauty": "Beauty",
        "travel": "Travel",
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=ua, viewport={"width": 1400, "height": 900}, locale="en-AU")
        page = context.new_page()

        for list_url in STUDENT_BEANS_PAGES:
            page_hint = ""
            if "/cats/" in list_url:
                for key, hint in page_hint_map.items():
                    if key in list_url:
                        page_hint = hint
                        break

            try:
                page.goto(list_url, wait_until="domcontentloaded", timeout=60000)
                random_delay(1.0, 2.0)
                page.mouse.wheel(0, random.randint(600, 1600))
                random_delay(0.5, 1.2)
                soup = BeautifulSoup(page.content(), "html.parser")
            except Exception:
                continue

            for a in soup.select("a[href*='/student-discount/au/']"):
                href = (a.get("href") or "").strip()
                if not href or href in ("/student-discount/au/all",):
                    continue
                if "/cats/" in href:
                    continue
                m = SB_BRAND_LINK.match(urlparse(href).path)
                if not m:
                    continue
                if m.group(1) in ("all",):
                    continue

                full = urljoin(BASE_STUDENT_BEANS, href)
                path_key = urlparse(full).path
                if path_key in seen_paths:
                    continue
                seen_paths.add(path_key)

                text = a.get_text(" ", strip=True)
                if len(text) < 4:
                    continue

                title = re.sub(r"\s+", " ", text).strip()
                if len(title) > 200:
                    title = title[:197] + "…"

                image_url = _find_nearby_image(a)
                discount_label = parse_discount_label(title) or "Student discount"
                topic = infer_topic(title, "", page_hint)
                deal_type = infer_deal_type(title, discount_label, "studentbeans")

                scraped.append(
                    {
                        "title": title,
                        "link": full,
                        "image_url": image_url,
                        "category": topic,
                        "source_category": page_hint or "Student Beans",
                        "votes": 0,
                        "posted_at": datetime.now().isoformat(),
                        "locations": [],
                        "is_expired": "expired" in title.lower(),
                        "source": "studentbeans",
                        "deal_type": deal_type,
                        "discount_label": discount_label,
                    }
                )

            random_delay(0.8, 1.6)

        context.close()
        browser.close()

    return scraped


def scrape_unidays() -> List[Dict]:
    ua = random.choice(USER_AGENTS)
    scraped: List[Dict] = []
    seen: Set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=ua, viewport={"width": 1400, "height": 900}, locale="en-AU")
        page = context.new_page()
        try:
            page.goto(UNIDAYS_BRAND_URL, wait_until="domcontentloaded", timeout=60000)
            random_delay(1.5, 2.5)
            for _ in range(18):
                page.mouse.wheel(0, 1800)
                random_delay(0.35, 0.75)
            hrefs = page.evaluate(
                """() => {
                const as = [...document.querySelectorAll('a[href^="/AU/en-AU/partners/"]')];
                const out = [];
                for (const a of as) {
                  const href = a.getAttribute('href');
                  if (!href || !href.endsWith('/view')) continue;
                  const t = (a.innerText || '').trim().split('\\n')[0].trim();
                  if (t.length < 2) continue;
                  out.push({ href, title: t.slice(0, 220) });
                }
                return out;
              }"""
            )
        except Exception:
            hrefs = []
        context.close()
        browser.close()

    for item in hrefs or []:
        href = item.get("href") or ""
        title = item.get("title") or ""
        if not href or not title:
            continue
        full = urljoin(BASE_UNIDAYS, href)
        if full in seen:
            continue
        seen.add(full)

        discount_label = parse_discount_label(title) or "Student discount"
        topic = infer_topic(title, "")
        deal_type = infer_deal_type(title, discount_label, "unidays")

        scraped.append(
            {
                "title": f"{title} — UNiDAYS student offer",
                "link": full,
                "image_url": "",
                "category": topic,
                "source_category": "UNiDAYS",
                "votes": 0,
                "posted_at": datetime.now().isoformat(),
                "locations": [],
                "is_expired": False,
                "source": "unidays",
                "deal_type": deal_type,
                "discount_label": discount_label,
            }
        )

        if len(scraped) >= 200:
            break

    return scraped


def _cloud_scraper() -> "cloudscraper.CloudScraper":
    if sys.platform.startswith("linux"):
        plat = "linux"
    elif sys.platform.startswith("win"):
        plat = "windows"
    else:
        plat = "darwin"
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": plat, "mobile": False}
    )


def _strip_url_query(url: str) -> str:
    try:
        parts = urlparse(url)
        return urlunparse((parts.scheme, parts.netloc, parts.path, "", "", ""))
    except Exception:
        return url


def _parse_slickdeals_pub_date(raw: str) -> str:
    raw = (raw or "").strip()
    for fmt in ("%a, %d %b %y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(raw, fmt).isoformat()
        except ValueError:
            continue
    return datetime.now().isoformat()


def scrape_slickdeals() -> List[Dict]:
    scraped: List[Dict] = []
    seen_paths: Set[str] = set()
    scraper = _cloud_scraper()
    for rss_url in SLICKDEALS_RSS_URLS:
        try:
            resp = scraper.get(rss_url, timeout=45)
        except Exception:
            continue
        ctype = (resp.headers.get("content-type") or "").lower()
        if resp.status_code != 200 or "xml" not in ctype:
            continue
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError:
            continue
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            cat_el = item.find("category")
            enc_el = item.find(CONTENT_ENCODED_TAG)
            title = (title_el.text or "").strip() if title_el is not None and title_el.text else ""
            link = (link_el.text or "").strip() if link_el is not None and link_el.text else ""
            if not title or not link:
                continue
            link_clean = _strip_url_query(link)
            path_key = urlparse(link_clean).path
            if path_key in seen_paths:
                continue
            seen_paths.add(path_key)

            encoded = (enc_el.text or "") if enc_el is not None and enc_el.text else ""
            img_m = RSSIMAGE_FROM_HTML.search(encoded)
            image_url = img_m.group(1) if img_m else ""
            if image_url.startswith("//"):
                image_url = f"https:{image_url}"

            raw_cat = (cat_el.text or "Slickdeals").strip() if cat_el is not None and cat_el.text else "Slickdeals"
            pub = _parse_slickdeals_pub_date(pub_el.text if pub_el is not None and pub_el.text else "")

            discount_label = parse_discount_label(title)
            if not discount_label and re.search(r"[\$£€]", title):
                price_m = re.search(
                    r"(?:from\s+)?[\$£€]\s*[\d,.]+(?:\s*-\s*[\$£€]?\s*[\d,.]+)?",
                    title,
                    re.I,
                )
                if price_m:
                    discount_label = price_m.group(0).strip()
            if not discount_label:
                discount_label = "Deal"

            topic = infer_topic(title, raw_cat)
            deal_type = infer_deal_type(title, discount_label, "slickdeals")

            scraped.append(
                {
                    "title": title,
                    "link": link_clean,
                    "image_url": image_url,
                    "category": topic,
                    "source_category": raw_cat,
                    "votes": 0,
                    "posted_at": pub,
                    "locations": [],
                    "is_expired": bool(re.search(r"\bexpired\b", title, re.I)),
                    "source": "slickdeals",
                    "deal_type": deal_type,
                    "discount_label": discount_label,
                }
            )
    return scraped


def migrate_deal_fields(deal: Dict) -> Dict:
    d = dict(deal)
    if "source" not in d:
        d["source"] = "ozbargain"
    if "deal_type" not in d:
        d["deal_type"] = infer_deal_type(d.get("title", ""), "", "ozbargain")
    if "discount_label" not in d:
        dl = parse_discount_label(d.get("title", ""))
        d["discount_label"] = dl
    if "source_category" not in d:
        d["source_category"] = d.get("category", "General")
    raw = d.get("source_category") or d.get("category") or ""
    if d.get("source") == "ozbargain" and d.get("category"):
        d["category"] = infer_topic(d.get("title", ""), raw)
    elif d.get("category") in ("", None):
        d["category"] = infer_topic(d.get("title", ""), raw)
    return d


def deduplicate_deals(existing: List[Dict], new_deals: List[Dict]) -> Tuple[List[Dict], int]:
    existing = [migrate_deal_fields(d) for d in existing]
    existing_by_link = {deal.get("link"): deal for deal in existing if deal.get("link")}
    fresh_count = 0

    for old in existing_by_link.values():
        old["is_new"] = False

    for deal in new_deals:
        deal = migrate_deal_fields(deal)
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
    combined.sort(key=lambda d: d.get("posted_at", "") or "", reverse=True)
    print(f"Merged | New: {fresh_count} | Total: {len(combined)}")
    return combined, fresh_count


def run_scrape_cycle() -> Dict:
    existing = load_existing_deals()
    oz = scrape_ozbargain()
    sb = scrape_student_beans()
    ud = scrape_unidays()
    sd = scrape_slickdeals()
    fresh = oz + sb + ud + sd
    all_deals, fresh_count = deduplicate_deals(existing, fresh)
    scraped_at = datetime.now().isoformat()
    for deal in all_deals:
        deal["scraped_at"] = scraped_at
    save_deals(all_deals)
    meta = {
        "last_scraped_at": scraped_at,
        "scraped_count": len(fresh),
        "scraped_ozbargain": len(oz),
        "scraped_studentbeans": len(sb),
        "scraped_unidays": len(ud),
        "scraped_slickdeals": len(sd),
        "new_count": fresh_count,
        "total_count": len(all_deals),
    }
    save_scrape_meta(meta)
    return meta


def main() -> None:
    meta = run_scrape_cycle()
    print(
        f"Last: {meta['last_scraped_at']} | OzB: {meta['scraped_ozbargain']} | "
        f"StudentBeans: {meta['scraped_studentbeans']} | UNiDAYS: {meta['scraped_unidays']} | "
        f"Slickdeals: {meta['scraped_slickdeals']} | "
        f"New: {meta['new_count']} | Total: {meta['total_count']}"
    )


if __name__ == "__main__":
    main()
