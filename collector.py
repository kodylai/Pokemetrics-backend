"""
Pokemon Card Data Collector
============================
Pulls sold listing data from eBay API and stores in SQLite.
Run on a schedule (e.g., every 4-6 hours) via Task Scheduler on Windows.

Setup:
  1. Create an eBay developer account at developer.ebay.com
  2. Create an application and get your Client ID + Client Secret
  3. Set them in the .env file or as environment variables:
       EBAY_CLIENT_ID=your_client_id
       EBAY_CLIENT_SECRET=your_client_secret
  4. Fill in CARDS_TO_TRACK below with your card names and metadata
  5. Run: python collector.py
"""

import os
import sys
import json
import time
import sqlite3
import base64
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path


# ── CONFIG ────────────────────────────────────────────────────────────────────

DB_PATH = "pokemon_cards.db"

# eBay API credentials — set via environment variables or .env file
EBAY_CLIENT_ID = os.environ.get("EBAY_CLIENT_ID", "")
EBAY_CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET", "")

# Cards to track — fill this in with your set's chase cards
# pull_rate_1_in_x and cards_in_rarity_tier are static per set
CARDS_TO_TRACK = [
    {
        "card_name": "Umbreon ex 187 SAR",
        "set_name": "Prismatic Evolutions",
        "pokemon": "Umbreon",
        "rarity_tier": "SIR",
        "pull_rate_1_in_x": 45,
        "cards_in_rarity_tier": 18,
        "pack_price_usd": 5.50,
        "character_premium_rank": 1.3,
        "artwork_hype_score": 9.5,
        "google_trends_score": 72,
        "ebay_search_query": "Umbreon 187 Prismatic Evolutions SAR -psa -bgs -cgc -repack",
    },
    {
        "card_name": "Mega Charizard ex SIR",
        "set_name": "Phantasmal Flames",
        "pokemon": "Charizard",
        "rarity_tier": "SIR",
        "pull_rate_1_in_x": 55,
        "cards_in_rarity_tier": 12,
        "pack_price_usd": 4.50,
        "character_premium_rank": 1.1,
        "artwork_hype_score": 10,
        "google_trends_score": 100,
        "ebay_search_query": "Mega Charizard ex SIR Phantasmal Flames -psa -bgs -cgc -repack",
    },
    {
        "card_name": "Pikachu ex SIR",
        "set_name": "Ascended Heroes",
        "pokemon": "Pikachu",
        "rarity_tier": "SIR",
        "pull_rate_1_in_x": 60,
        "cards_in_rarity_tier": 10,
        "pack_price_usd": 4.50,
        "character_premium_rank": 1.8,
        "artwork_hype_score": 9,
        "google_trends_score": 95,
        "ebay_search_query": "Pikachu ex SIR Ascended Heroes -psa -bgs -cgc -repack",
    },
    # ─── ADD MORE CARDS HERE ───
    # Copy the template above and fill in for each chase card.
    # The ebay_search_query should be specific enough to find only that card.
    # Use "-psa -bgs -cgc" to exclude graded cards.
    # Use "-repack" to exclude repacks.
]


# ── DATABASE SETUP ────────────────────────────────────────────────────────────

def init_db():
    """Create database tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Card metadata (static info)
    c.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            card_name TEXT PRIMARY KEY,
            set_name TEXT,
            pokemon TEXT,
            rarity_tier TEXT,
            pull_rate_1_in_x REAL,
            cards_in_rarity_tier INTEGER,
            pack_price_usd REAL,
            character_premium_rank REAL,
            artwork_hype_score REAL,
            google_trends_score REAL,
            ebay_search_query TEXT
        )
    """)

    # Price observations over time
    c.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_name TEXT,
            timestamp TEXT,
            median_price REAL,
            avg_price REAL,
            min_price REAL,
            max_price REAL,
            num_sales INTEGER,
            raw_prices TEXT,
            FOREIGN KEY (card_name) REFERENCES cards(card_name)
        )
    """)

    # Model predictions over time
    c.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_name TEXT,
            timestamp TEXT,
            market_price REAL,
            predicted_price REAL,
            residual_pct REAL,
            pull_cost_score REAL,
            desirability_score REAL,
            FOREIGN KEY (card_name) REFERENCES cards(card_name)
        )
    """)

    conn.commit()
    conn.close()
    print("✅  Database initialized")


def upsert_cards(cards: list):
    """Insert or update card metadata."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for card in cards:
        c.execute("""
            INSERT OR REPLACE INTO cards
            (card_name, set_name, pokemon, rarity_tier, pull_rate_1_in_x,
             cards_in_rarity_tier, pack_price_usd, character_premium_rank,
             artwork_hype_score, google_trends_score, ebay_search_query)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            card["card_name"], card["set_name"], card["pokemon"],
            card["rarity_tier"], card["pull_rate_1_in_x"],
            card["cards_in_rarity_tier"], card["pack_price_usd"],
            card["character_premium_rank"], card["artwork_hype_score"],
            card["google_trends_score"], card["ebay_search_query"],
        ))
    conn.commit()
    conn.close()
    print(f"✅  Upserted {len(cards)} cards")


# ── EBAY API ──────────────────────────────────────────────────────────────────

def get_ebay_token() -> str:
    """Get OAuth token from eBay using client credentials."""
    if not EBAY_CLIENT_ID or not EBAY_CLIENT_SECRET:
        print("\n❌  eBay API credentials not set!")
        print("   Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET as environment variables")
        print("   Or create a .env file with these values\n")
        print("   Get credentials at: https://developer.ebay.com\n")
        sys.exit(1)

    url = "https://api.ebay.com/identity/v1/oauth2/token"
    credentials = base64.b64encode(
        f"{EBAY_CLIENT_ID}:{EBAY_CLIENT_SECRET}".encode()
    ).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {credentials}",
    }
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope",
    }).encode()

    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
            return result["access_token"]
    except urllib.error.HTTPError as e:
        print(f"❌  eBay auth failed: {e.code} {e.reason}")
        print(f"   Response: {e.read().decode()}")
        sys.exit(1)


def search_ebay_sold(token: str, query: str, limit: int = 25) -> list:
    """
    Search eBay for sold listings using the Browse API.
    Returns list of sold prices in USD.
    """
    base_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    params = {
        "q": query,
        "filter": "buyingOptions:{FIXED_PRICE|AUCTION},conditions:{NEW|LIKE_NEW|VERY_GOOD},priceCurrency:USD",
        "sort": "-endDate",  # most recent first
        "limit": str(limit),
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    headers = {
        "Authorization": f"Bearer {token}",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  ⚠️  eBay search failed for '{query}': {e.code}")
        return []

    prices = []
    for item in result.get("itemSummaries", []):
        try:
            price = float(item["price"]["value"])
            currency = item["price"]["currency"]
            if currency == "USD" and 1 < price < 5000:  # filter outliers
                prices.append(price)
        except (KeyError, ValueError):
            continue

    return prices


def collect_prices():
    """Main collection loop — fetch prices for all tracked cards."""
    print(f"\n🔄  Starting price collection at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("─" * 50)

    token = get_ebay_token()
    print("✅  eBay authenticated\n")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = datetime.now().isoformat()

    for card in CARDS_TO_TRACK:
        name = card["card_name"]
        query = card["ebay_search_query"]
        print(f"  📦  Fetching: {name}...")

        prices = search_ebay_sold(token, query)

        if not prices:
            print(f"      ⚠️  No results found")
            continue

        import statistics
        median_price = statistics.median(prices)
        avg_price = statistics.mean(prices)
        min_price = min(prices)
        max_price = max(prices)

        c.execute("""
            INSERT INTO price_history
            (card_name, timestamp, median_price, avg_price, min_price, max_price, num_sales, raw_prices)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, timestamp, median_price, avg_price,
            min_price, max_price, len(prices), json.dumps(prices)
        ))

        print(f"      ✅  {len(prices)} sales | Median: ${median_price:.2f} | Range: ${min_price:.2f}-${max_price:.2f}")

        time.sleep(0.5)  # rate limit buffer

    conn.commit()
    conn.close()
    print(f"\n✅  Collection complete at {datetime.now().strftime('%H:%M')}\n")


# ── DEMO MODE (no API needed) ────────────────────────────────────────────────

def collect_demo_prices():
    """
    Populate DB with sample data so you can test the dashboard
    before setting up eBay API credentials.
    """
    import random

    print("\n🎮  Running in DEMO MODE (no eBay API needed)")
    print("─" * 50)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Generate 7 days of fake price history
    for days_ago in range(7, -1, -1):
        timestamp = (datetime.now() - timedelta(days=days_ago)).isoformat()

        demo_prices = {
            "Umbreon ex 187 SAR": (1100, 1250),
            "Mega Charizard ex SIR": (780, 860),
            "Pikachu ex SIR": (950, 1100),
        }

        for card in CARDS_TO_TRACK:
            name = card["card_name"]
            price_range = demo_prices.get(name, (50, 150))
            base = random.uniform(*price_range)
            # Add slight upward trend
            trend = days_ago * -2
            prices = [round(base + trend + random.uniform(-15, 15), 2) for _ in range(15)]

            median_price = sorted(prices)[len(prices)//2]
            avg_price = sum(prices)/len(prices)

            c.execute("""
                INSERT INTO price_history
                (card_name, timestamp, median_price, avg_price, min_price, max_price, num_sales, raw_prices)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name, timestamp, median_price, avg_price,
                min(prices), max(prices), len(prices), json.dumps(prices)
            ))

    conn.commit()
    conn.close()
    print("✅  Demo data populated (7 days of history)\n")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    upsert_cards(CARDS_TO_TRACK)

    if "--demo" in sys.argv:
        collect_demo_prices()
    else:
        collect_prices()
