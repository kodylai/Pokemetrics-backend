"""
eBay Sold Listings Scraper — Selenium + Confidence Scoring
============================================================
Uses a real Chrome browser to scrape eBay sold listings,
bypassing anti-bot detection that blocks raw HTTP requests.

CONFIDENCE SCORING:
  HIGH (80-100):  Buy It Now, reputable sellers, normal price
  MEDIUM (50-79): Best Offer accepted, reasonable price
  LOW (0-49):     Auctions (high non-payment risk), outliers

Usage:
  python sales_scraper.py                  # Scrape all cards
  python sales_scraper.py --verified       # Only high-confidence sales
  python sales_scraper.py --card "Umbreon" # Scrape one card
  python sales_scraper.py --demo           # Dry run
  python sales_scraper.py --headless       # No browser window (background)

Requirements:
  pip install selenium webdriver-manager beautifulsoup4
"""

import os
import sys
import re
import json
import time
import sqlite3
import random
import math
import urllib.parse
from datetime import datetime

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

DB_PATH = "pokemon_cards.db"

# ── Cards to track ──
CARDS_TO_SCRAPE = [
    {
        "card_name": "Umbreon ex 187 SAR",
        "search_query": "Umbreon ex 187 Prismatic Evolutions",
        "expected_price": 1150,
        "min_price": 200,
        "max_price": 3000,
    },
    {
        "card_name": "Mega Charizard ex SIR",
        "search_query": "Mega Charizard ex 125 Phantasmal Flames",
        "expected_price": 830,
        "min_price": 200,
        "max_price": 2000,
    },
    {
        "card_name": "Pikachu ex SIR",
        "search_query": "Pikachu ex 276 Ascended Heroes",
        "expected_price": 1000,
        "min_price": 200,
        "max_price": 2500,
    },
    # ─── ADD MORE CARDS HERE ───
]

# ── Title blacklist ──
BLACKLIST_KEYWORDS = [
    "repack", "mystery", "lot of", "bundle of", "custom",
    "proxy", "fake", "replica", "read description",
    "damaged", "poor condition",
    "japanese", "jp", "korean", "chinese",
    "complete set", "master set", "bulk lot",
    "booster box", "booster pack", "etb",
    "code card", "online code",
]


# ── DATABASE ──────────────────────────────────────────────────────────────────

def init_sales_table():
    """Create sales history table with confidence scoring."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sales_history'")
    if c.fetchone():
        c.execute("PRAGMA table_info(sales_history)")
        columns = [row[1] for row in c.fetchall()]
        if "confidence_score" not in columns:
            print("  📦  Upgrading sales_history table...")
            c.execute("ALTER TABLE sales_history ADD COLUMN confidence_score INTEGER DEFAULT 50")
            c.execute("ALTER TABLE sales_history ADD COLUMN confidence_flags TEXT DEFAULT ''")
            c.execute("ALTER TABLE sales_history ADD COLUMN seller_feedback TEXT DEFAULT ''")
            c.execute("ALTER TABLE sales_history ADD COLUMN bid_count INTEGER DEFAULT 0")
            c.execute("ALTER TABLE sales_history ADD COLUMN best_offer INTEGER DEFAULT 0")
            conn.commit()
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS sales_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT,
                title TEXT,
                sold_price REAL,
                sold_date TEXT,
                condition TEXT,
                listing_type TEXT,
                url TEXT,
                scraped_at TEXT,
                confidence_score INTEGER DEFAULT 50,
                confidence_flags TEXT DEFAULT '',
                seller_feedback TEXT DEFAULT '',
                bid_count INTEGER DEFAULT 0,
                best_offer INTEGER DEFAULT 0,
                UNIQUE(card_name, url)
            )
        """)

    c.execute("CREATE INDEX IF NOT EXISTS idx_sales_card_date ON sales_history(card_name, sold_date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sales_confidence ON sales_history(card_name, confidence_score)")
    conn.commit()
    conn.close()
    print("✅  Sales history table initialized")


# ── SELENIUM BROWSER ──────────────────────────────────────────────────────────

def create_browser(headless: bool = False):
    """Create a Chrome browser instance."""
    options = Options()

    if headless:
        options.add_argument("--headless=new")

    # Make it look like a real browser
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Random user agent
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    ]
    options.add_argument(f"--user-agent={random.choice(user_agents)}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Remove webdriver flag
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return driver


# ── URL BUILDER ───────────────────────────────────────────────────────────────

def build_sold_url(query: str, min_price: float = None, max_price: float = None,
                   page: int = 1) -> str:
    params = {
        "_nkw": query,
        "LH_Complete": "1",
        "LH_Sold": "1",
        "_sop": "13",
        "_pgn": str(page),
        "rt": "nc",
        "_ipg": "60",
    }
    if min_price:
        params["_udlo"] = str(min_price)
    if max_price:
        params["_udhi"] = str(max_price)

    return f"https://www.ebay.com/sch/i.html?{urllib.parse.urlencode(params)}"


# ── PARSERS ───────────────────────────────────────────────────────────────────

def parse_price(price_text: str) -> float:
    if not price_text:
        return 0.0
    cleaned = re.sub(r'[^\d.]', '', price_text.split("to")[0].strip())
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_date(date_text: str) -> str:
    if not date_text:
        return ""
    cleaned = date_text.replace("Sold", "").strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    for fmt in ("%b %d, %Y", "%d %b %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return cleaned


def parse_feedback(feedback_text: str) -> int:
    if not feedback_text:
        return 0
    nums = re.findall(r'[\d,]+', feedback_text.replace(",", ""))
    try:
        return int(nums[0]) if nums else 0
    except (ValueError, IndexError):
        return 0


def is_blacklisted(title: str) -> bool:
    lower = title.lower()
    return any(kw in lower for kw in BLACKLIST_KEYWORDS)


# ── CONFIDENCE SCORING ────────────────────────────────────────────────────────

def calculate_confidence(sale: dict, expected_price: float, all_prices: list) -> tuple:
    """Calculate confidence score (0-100) for a sale."""
    score = 0
    flags = []

    listing_type = sale.get("listing_type", "")
    is_best_offer = sale.get("best_offer", False)

    if listing_type == "Buy It Now" and not is_best_offer:
        score += 30
        flags.append("BIN")
    elif is_best_offer:
        score += 20
        flags.append("OFFER_ACCEPTED")
    elif listing_type == "Auction":
        score += 0
        flags.append("AUCTION")
        if sale.get("bid_count", 0) == 1:
            score -= 20
            flags.append("SINGLE_BID")

    price = sale.get("sold_price", 0)
    if all_prices and len(all_prices) >= 3:
        import statistics
        median = statistics.median(all_prices)
        try:
            stdev = statistics.stdev(all_prices)
        except statistics.StatisticsError:
            stdev = median * 0.2

        if stdev > 0:
            z_score = abs(price - median) / stdev
            if z_score <= 1.0:
                score += 20
                flags.append("NORMAL_PRICE")
            elif z_score <= 2.0:
                score += 10
                flags.append("SLIGHT_OUTLIER")
            else:
                flags.append("PRICE_OUTLIER")
    elif expected_price > 0:
        deviation = abs(price - expected_price) / expected_price
        if deviation <= 0.25:
            score += 20
            flags.append("NORMAL_PRICE")
        elif deviation <= 0.50:
            score += 10
            flags.append("SLIGHT_OUTLIER")
        else:
            flags.append("PRICE_OUTLIER")

    if expected_price > 0 and price < expected_price * 0.5:
        score -= 10
        flags.append("SUSPICIOUSLY_CHEAP")

    feedback = parse_feedback(sale.get("seller_feedback", ""))
    if feedback >= 100:
        score += 15
        flags.append("TRUSTED_SELLER")
    elif feedback >= 50:
        score += 10
        flags.append("ESTABLISHED_SELLER")
    elif feedback >= 10:
        score += 5
        flags.append("SOME_FEEDBACK")
    else:
        flags.append("LOW_FEEDBACK")

    title = sale.get("title", "")
    if not is_blacklisted(title):
        score += 15
        flags.append("CLEAN_TITLE")
    else:
        flags.append("SUSPICIOUS_TITLE")

    score = max(0, min(100, score))
    return score, flags


# ── MAIN SCRAPING (SELENIUM) ─────────────────────────────────────────────────

def scrape_sold_listings(driver, query: str, expected_price: float = 0,
                         min_price: float = None, max_price: float = None,
                         pages: int = 2) -> list:
    """Scrape eBay sold listings using Selenium."""
    all_sales = []

    for page in range(1, pages + 1):
        url = build_sold_url(query, min_price, max_price, page)

        try:
            driver.get(url)
            time.sleep(random.uniform(4, 6))

            # Wait for items — try new selector first, then old
            item_selector = None
            for selector in [".s-card", ".s-item"]:
                try:
                    WebDriverWait(driver, 8).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    item_selector = selector
                    break
                except Exception:
                    continue

            if not item_selector:
                print(f"      ⚠️  Page {page} timed out or no results")
                continue

            soup = BeautifulSoup(driver.page_source, "html.parser")
            items = soup.select(item_selector)

            if not items:
                print(f"      ⚠️  No items found on page {page}")
                break

            page_count = 0
            for item in items:
                try:
                    # ── Check if this is actually a SOLD item ──
                    item_text = item.get_text().lower()
                    
                    # Skip items that are clearly active listings, not sold
                    if "new listing" in item_text and "sold" not in item_text:
                        continue

                    # ── Title — try multiple selectors ──
                    title = ""
                    for sel in [".s-card__title", ".s-item__title"]:
                        title_elem = item.select_one(sel)
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            break
                    # Fallback: find any link text or heading
                    if not title:
                        link = item.select_one("a")
                        if link:
                            title = link.get_text(strip=True)
                    if not title or title.lower() in ["shop on ebay", ""]:
                        continue
                    
                    # Strip "New Listing" prefix from title if present
                    if title.startswith("New Listing"):
                        title = title[len("New Listing"):].strip()
                    if title.startswith("New listing"):
                        title = title[len("New listing"):].strip()

                    # ── Price — look for price in multiple ways ──
                    price = 0.0
                    price_text = ""
                    for sel in [".s-card__price", ".s-item__price", "[class*='price']"]:
                        price_elem = item.select_one(sel)
                        if price_elem:
                            price_text = price_elem.get_text(strip=True)
                            price = parse_price(price_text)
                            if price > 0:
                                break

                    if "to" in price_text:
                        continue
                    if min_price and price < min_price:
                        continue
                    if max_price and price > max_price:
                        continue
                    if price <= 0:
                        continue

                    # ── Sold date ──
                    sold_date = ""
                    for sel in [".s-card__title--tagblock .POSITIVE",
                                ".s-item__title--tagblock .POSITIVE",
                                ".s-item__ended-date",
                                ".s-item__endedDate",
                                "[class*='ended']",
                                "[class*='sold']"]:
                        date_elem = item.select_one(sel)
                        if date_elem:
                            sold_date = parse_date(date_elem.get_text(strip=True))
                            if sold_date:
                                break
                    # Fallback: search all text for "Sold" pattern
                    if not sold_date:
                        all_text = item.get_text()
                        sold_match = re.search(r'Sold\s+(\w{3}\s+\d{1,2},?\s+\d{4})', all_text)
                        if sold_match:
                            sold_date = parse_date(sold_match.group(0))

                    # ── Condition ──
                    condition = "Unknown"
                    for sel in [".SECONDARY_INFO", "[class*='condition']", "[class*='subtitle']"]:
                        cond_elem = item.select_one(sel)
                        if cond_elem:
                            condition = cond_elem.get_text(strip=True)
                            break

                    # ── URL ──
                    item_url = ""
                    for sel in [".s-card__link", ".s-item__link", "a[href*='itm/']"]:
                        link_elem = item.select_one(sel)
                        if link_elem and link_elem.get("href"):
                            item_url = link_elem["href"]
                            break
                    if "?" in item_url:
                        item_url = item_url.split("?")[0]

                    # ── Listing type & bids ──
                    listing_type = "Buy It Now"
                    bid_count = 0
                    best_offer = False

                    for sel in [".s-item__bidCount", "[class*='bid']"]:
                        bid_elem = item.select_one(sel)
                        if bid_elem:
                            listing_type = "Auction"
                            bid_text = bid_elem.get_text(strip=True)
                            bid_nums = re.findall(r'\d+', bid_text)
                            bid_count = int(bid_nums[0]) if bid_nums else 0
                            break

                    # Best offer check
                    item_text = item.get_text().lower()
                    if "best offer" in item_text:
                        best_offer = True
                        if listing_type == "Buy It Now":
                            listing_type = "Best Offer"

                    # ── Seller info ──
                    seller_feedback = ""
                    for sel in [".s-item__seller-info-text", "[class*='seller']"]:
                        seller_elem = item.select_one(sel)
                        if seller_elem:
                            seller_feedback = seller_elem.get_text(strip=True)
                            break

                    all_sales.append({
                        "title": title,
                        "sold_price": price,
                        "sold_date": sold_date,
                        "condition": condition,
                        "listing_type": listing_type,
                        "url": item_url,
                        "bid_count": bid_count,
                        "best_offer": best_offer,
                        "seller_feedback": seller_feedback,
                    })
                    page_count += 1

                except Exception:
                    continue

            print(f"      📄  Page {page}: {page_count} listings scraped")

        except Exception as e:
            print(f"      ⚠️  Error on page {page}: {e}")
            continue

        # Delay between pages
        if page < pages:
            time.sleep(random.uniform(3, 6))

    # Calculate confidence scores
    all_prices = [s["sold_price"] for s in all_sales if s["sold_price"] > 0]
    for sale in all_sales:
        score, flags = calculate_confidence(sale, expected_price, all_prices)
        sale["confidence_score"] = score
        sale["confidence_flags"] = ",".join(flags)

    return all_sales


# ── MAIN COLLECTION ───────────────────────────────────────────────────────────

def collect_all_sales(verified_only: bool = False, headless: bool = False):
    """Scrape sold listings for all tracked cards."""
    mode = "VERIFIED ONLY" if verified_only else "ALL SALES"
    print(f"\n💰  Sales History Scraper [{mode}] — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("─" * 60)

    print("  🌐  Launching Chrome browser...")
    driver = create_browser(headless=headless)
    print("  ✅  Browser ready\n")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    scraped_at = datetime.now().isoformat()

    total_new = 0
    total_filtered = 0

    try:
        for card in CARDS_TO_SCRAPE:
            name = card["card_name"]
            query = card["search_query"]
            expected = card.get("expected_price", 0)
            print(f"  🔍  {name}")
            print(f"      Query: \"{query}\"")

            sales = scrape_sold_listings(
                driver,
                query,
                expected_price=expected,
                min_price=card.get("min_price"),
                max_price=card.get("max_price"),
                pages=2,
            )

            if not sales:
                print(f"      ⚠️  No sold listings found\n")
                continue

            high = [s for s in sales if s["confidence_score"] >= 70]
            medium = [s for s in sales if 40 <= s["confidence_score"] < 70]
            low = [s for s in sales if s["confidence_score"] < 40]

            new_count = 0
            filtered_count = 0

            for sale in sales:
                if verified_only and sale["confidence_score"] < 60:
                    filtered_count += 1
                    continue
                if is_blacklisted(sale["title"]):
                    filtered_count += 1
                    continue

                try:
                    c.execute("""
                        INSERT OR IGNORE INTO sales_history
                        (card_name, title, sold_price, sold_date, condition,
                         listing_type, url, scraped_at, confidence_score,
                         confidence_flags, seller_feedback, bid_count, best_offer)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        name, sale["title"], sale["sold_price"],
                        sale["sold_date"], sale["condition"],
                        sale["listing_type"], sale["url"], scraped_at,
                        sale["confidence_score"], sale["confidence_flags"],
                        sale["seller_feedback"], sale["bid_count"],
                        1 if sale["best_offer"] else 0,
                    ))
                    if c.rowcount > 0:
                        new_count += 1
                except sqlite3.IntegrityError:
                    pass

            total_new += new_count
            total_filtered += filtered_count

            prices_high = [s["sold_price"] for s in high if s["sold_price"] > 0]
            prices_all = [s["sold_price"] for s in sales if s["sold_price"] > 0]

            print(f"      ✅  Found {len(sales)} sales ({new_count} new, {filtered_count} filtered)")
            print(f"      📊  Confidence: {len(high)} high | {len(medium)} medium | {len(low)} low")

            if prices_high:
                import statistics
                median_h = statistics.median(prices_high)
                print(f"      💚  Verified median: ${median_h:,.2f}")

            if prices_all:
                import statistics
                median_a = statistics.median(prices_all)
                print(f"      💵  All-sales median: ${median_a:,.2f}")

            print()
            time.sleep(random.uniform(3, 6))

        # ── GRADED SEARCH PASS ──
        # For cards with expected_price >= $50, do additional searches
        # specifically for PSA and BGS graded versions
        GRADED_SEARCHES = ["PSA", "BGS", "CGC"]
        GRADED_THRESHOLD = 50  # Only search graded for cards worth $50+

        graded_cards = [c for c in CARDS_TO_SCRAPE if c.get("expected_price", 0) >= GRADED_THRESHOLD]

        if graded_cards:
            print(f"\n{'='*55}")
            print(f"  🏅  GRADED SEARCH PASS — {len(graded_cards)} cards × {len(GRADED_SEARCHES)} graders × 3 grades")
            print(f"{'='*55}\n")

            for card in graded_cards:
                name = card["card_name"]
                base_query = card["search_query"]

                # Build a SHORT graded query — strip card numbers and keep just
                # the pokemon name + set name. eBay works better with shorter queries.
                # "Pikachu ex 276 Ascended Heroes" -> "Pikachu ex Ascended Heroes"
                # "Charizard Gold Star 100 EX Dragon Frontiers" -> "Charizard Gold Star Dragon Frontiers"
                # "Umbreon ex 161/180 Prismatic Evolutions" -> "Umbreon ex Prismatic Evolutions"
                clean_query = re.sub(r'\d+/\d+', '', base_query)  # remove "161/180"
                clean_query = re.sub(r'\b\d{2,3}\b', '', clean_query)  # remove standalone 2-3 digit numbers
                clean_query = re.sub(r'\bEX\b', '', clean_query)  # remove "EX" prefix from set names
                clean_query = re.sub(r'\s+', ' ', clean_query).strip()

                for grader in GRADED_SEARCHES:
                    # Each grading company uses different grade scales
                    grade_scales = {
                        "PSA": ["10", "9", "8"],       # PSA uses whole numbers only
                        "BGS": ["10", "9.5", "9"],     # BGS uses half grades
                        "CGC": ["10", "9.5", "9"],     # CGC uses half grades
                    }
                    grades_to_search = grade_scales.get(grader, ["10", "9"])

                    for grade_num in grades_to_search:
                        graded_query = f"{grader} {grade_num} {clean_query}"
                        print(f"  🏅  {name} [{grader} {grade_num}]")
                        print(f"      Query: \"{graded_query}\"")

                        sales = scrape_sold_listings(
                            driver,
                            graded_query,
                            expected_price=card.get("expected_price", 0) * 2,
                            min_price=card.get("min_price", 0),
                            pages=1,
                        )

                    if not sales:
                        print(f"      ⚠️  No graded listings found\n")
                        continue

                    # FILTER: only keep listings that actually mention the grader in the title
                    # eBay returns irrelevant results even with PSA/BGS in the query
                    grader_aliases = {
                        "PSA": ["PSA", "PROFESSIONAL SPORTS AUTHENTICATOR"],
                        "BGS": ["BGS", "BECKETT", "BKT"],
                        "CGC": ["CGC"],
                    }
                    aliases = grader_aliases.get(grader, [grader])
                    graded_sales = [
                        s for s in sales
                        if any(alias in s["title"].upper() for alias in aliases)
                    ]

                    skipped = len(sales) - len(graded_sales)
                    if skipped > 0:
                        print(f"      🔍  {len(sales)} results, {skipped} skipped (no {grader} in title)")

                    new_count = 0
                    updated_count = 0
                    for sale in graded_sales:
                        if is_blacklisted(sale["title"]):
                            continue
                        try:
                            # First try to insert as new
                            c.execute("""
                                INSERT OR IGNORE INTO sales_history
                                (card_name, title, sold_price, sold_date, condition,
                                 listing_type, url, scraped_at, confidence_score,
                                 confidence_flags, seller_feedback, bid_count, best_offer)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                name, sale["title"], sale["sold_price"],
                                sale["sold_date"], sale["condition"],
                                sale["listing_type"], sale["url"], scraped_at,
                                sale["confidence_score"], sale["confidence_flags"],
                                sale["seller_feedback"], sale["bid_count"],
                                1 if sale["best_offer"] else 0,
                            ))
                            if c.rowcount > 0:
                                new_count += 1
                                total_new += 1
                            else:
                                # Record already exists — update title if the new one has grading info
                                # This catches cases where the same listing was scraped earlier
                                # with a truncated title that didn't include "PSA 10" etc.
                                c.execute("""
                                    UPDATE sales_history
                                    SET title = ?
                                    WHERE sold_price = ? AND sold_date = ? AND card_name = ?
                                    AND (title NOT LIKE '%PSA%' AND title NOT LIKE '%BGS%'
                                         AND title NOT LIKE '%CGC%' AND title NOT LIKE '%BECKETT%')
                                """, (
                                    sale["title"], sale["sold_price"],
                                    sale["sold_date"], name,
                                ))
                                if c.rowcount > 0:
                                    updated_count += 1
                        except sqlite3.IntegrityError:
                            pass

                    print(f"      ✅  {len(graded_sales)} graded listings, {new_count} new, {updated_count} updated")
                    print()
                    time.sleep(random.uniform(2, 4))

            # Re-parse grades for all new records
            from grade_parser import update_all_grades, init_grade_columns
            init_grade_columns()
            conn.commit()
            update_all_grades()

    finally:
        driver.quit()
        print("  🌐  Browser closed")

    conn.commit()
    conn.close()
    print(f"\n✅  Done! {total_new} new records, {total_filtered} filtered out\n")


# ── QUERY HELPERS (for dashboard / Lovable) ───────────────────────────────────

def get_sales_history(card_name: str = None, verified_only: bool = False) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    min_conf = 60 if verified_only else 0

    if card_name:
        c.execute("""
            SELECT * FROM sales_history
            WHERE card_name = ? AND confidence_score >= ?
            ORDER BY sold_date DESC
        """, (card_name, min_conf))
    else:
        c.execute("""
            SELECT * FROM sales_history
            WHERE confidence_score >= ?
            ORDER BY sold_date DESC
        """, (min_conf,))

    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def get_sales_summary(verified_only: bool = False) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    min_conf = 60 if verified_only else 0

    c.execute("""
        SELECT
            card_name,
            COUNT(*) as total_sales,
            ROUND(AVG(sold_price), 2) as avg_price,
            ROUND(MIN(sold_price), 2) as min_price,
            ROUND(MAX(sold_price), 2) as max_price,
            ROUND(AVG(confidence_score), 1) as avg_confidence,
            MIN(sold_date) as earliest_sale,
            MAX(sold_date) as latest_sale,
            SUM(CASE WHEN listing_type = 'Buy It Now' THEN 1 ELSE 0 END) as bin_count,
            SUM(CASE WHEN listing_type = 'Auction' THEN 1 ELSE 0 END) as auction_count,
            SUM(CASE WHEN listing_type = 'Best Offer' THEN 1 ELSE 0 END) as offer_count
        FROM sales_history
        WHERE sold_price > 0 AND confidence_score >= ?
        GROUP BY card_name
        ORDER BY avg_price DESC
    """, (min_conf,))

    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def get_price_over_time(card_name: str, verified_only: bool = False) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    min_conf = 60 if verified_only else 0

    c.execute("""
        SELECT
            sold_date,
            ROUND(AVG(sold_price), 2) as avg_price,
            COUNT(*) as num_sales,
            ROUND(MIN(sold_price), 2) as min_price,
            ROUND(MAX(sold_price), 2) as max_price,
            ROUND(AVG(confidence_score), 1) as avg_confidence
        FROM sales_history
        WHERE card_name = ? AND sold_price > 0 AND sold_date != ''
              AND confidence_score >= ?
        GROUP BY sold_date
        ORDER BY sold_date ASC
    """, (card_name, min_conf))

    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not HAS_SELENIUM:
        print("\n❌  Selenium not installed. Run:")
        print("    pip install selenium webdriver-manager beautifulsoup4\n")
        sys.exit(1)
    if not HAS_BS4:
        print("\n❌  BeautifulSoup not installed. Run:")
        print("    pip install beautifulsoup4\n")
        sys.exit(1)

    init_sales_table()

    verified = "--verified" in sys.argv
    headless = "--headless" in sys.argv

    if "--demo" in sys.argv:
        print("\n🎮  Demo mode — URLs that would be scraped:\n")
        for card in CARDS_TO_SCRAPE:
            url = build_sold_url(card["search_query"], card.get("min_price"), card.get("max_price"))
            print(f"  {card['card_name']} (expected ~${card.get('expected_price', '?')})")
            print(f"    {url}\n")
        print("  Run without --demo to scrape with Chrome.")
        print("  Add --headless to run without visible browser window.")
        print("  Add --verified to only keep high-confidence sales.\n")

    elif "--card" in sys.argv:
        idx = sys.argv.index("--card") + 1
        if idx < len(sys.argv):
            search = sys.argv[idx].lower()
            matching = [c for c in CARDS_TO_SCRAPE if search in c["card_name"].lower()]
            if matching:
                CARDS_TO_SCRAPE[:] = matching
                collect_all_sales(verified_only=verified, headless=headless)
            else:
                print(f"❌  No card matching '{search}'")
        else:
            print("❌  Provide a card name after --card")
    else:
        collect_all_sales(verified_only=verified, headless=headless)
