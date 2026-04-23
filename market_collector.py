"""
Market Dynamics Collector
==========================
Tracks eBay listing flow for Pokemon cards:
  - Active listings (current supply)
  - New listings (supply entering market)
  - Ended listings (estimated sold vs unsold)

Run daily alongside collector.py to build up market dynamics data.

Usage:
  python market_collector.py          # Real eBay data
  python market_collector.py --demo   # Generate demo data for testing
"""

import os
import sys
import json
import time
import sqlite3
import base64
import random
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta

DB_PATH = "pokemon_cards.db"

EBAY_CLIENT_ID = os.environ.get("EBAY_CLIENT_ID", "")
EBAY_CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET", "")


# ── DATABASE EXTENSION ────────────────────────────────────────────────────────

def init_market_tables():
    """Create market dynamics tables."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Daily listing snapshots
    c.execute("""
        CREATE TABLE IF NOT EXISTS listing_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_name TEXT,
            snapshot_date TEXT,
            active_listings INTEGER,
            new_listings INTEGER,
            ended_listings INTEGER,
            estimated_sold INTEGER,
            estimated_unsold INTEGER,
            avg_active_price REAL,
            avg_sold_price REAL,
            median_active_price REAL,
            raw_listing_ids TEXT,
            FOREIGN KEY (card_name) REFERENCES cards(card_name)
        )
    """)

    # Computed market dynamics (derived from snapshots)
    c.execute("""
        CREATE TABLE IF NOT EXISTS market_dynamics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_name TEXT,
            computed_date TEXT,
            demand_pressure REAL,
            supply_saturation_7d REAL,
            supply_saturation_30d REAL,
            supply_saturation_shift REAL,
            new_listing_trend REAL,
            sales_velocity REAL,
            price_trend_7d REAL,
            price_trend_30d REAL,
            market_signal TEXT,
            FOREIGN KEY (card_name) REFERENCES cards(card_name)
        )
    """)

    conn.commit()
    conn.close()
    print("✅  Market dynamics tables initialized")


# ── EBAY LISTING FETCHER ─────────────────────────────────────────────────────

def get_ebay_token() -> str:
    """Get OAuth token from eBay using client credentials."""
    if not EBAY_CLIENT_ID or not EBAY_CLIENT_SECRET:
        print("\n❌  eBay API credentials not set!")
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
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode())
        return result["access_token"]


def fetch_active_listings(token: str, query: str, limit: int = 50) -> dict:
    """
    Fetch current active listings from eBay Browse API.
    Returns listing count, prices, and item IDs for tracking.
    """
    base_url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    params = {
        "q": query,
        "filter": "buyingOptions:{FIXED_PRICE|AUCTION},conditions:{NEW|LIKE_NEW|VERY_GOOD},priceCurrency:USD",
        "sort": "-endDate",
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
        print(f"  ⚠️  eBay search failed: {e.code}")
        return {"total": 0, "prices": [], "item_ids": []}

    total = result.get("total", 0)
    prices = []
    item_ids = []

    for item in result.get("itemSummaries", []):
        try:
            price = float(item["price"]["value"])
            item_id = item.get("itemId", "")
            if 1 < price < 5000:
                prices.append(price)
                item_ids.append(item_id)
        except (KeyError, ValueError):
            continue

    return {
        "total": total,
        "prices": prices,
        "item_ids": item_ids,
    }


def estimate_sold_listings(prev_ids: list, curr_ids: list, ended_count: int) -> tuple:
    """
    Estimate sold vs unsold from ended listings.
    
    Logic: If a listing disappeared (was in prev snapshot but not current),
    it either sold or was removed. We use a sell-through rate estimate
    based on the card's historical data.
    
    Returns (estimated_sold, estimated_unsold)
    """
    if ended_count <= 0:
        return 0, 0

    # Default sell-through rate estimate: ~40% of ended listings are sales
    # This gets refined as you collect more data
    SELL_THROUGH_RATE = 0.40

    estimated_sold = max(1, int(ended_count * SELL_THROUGH_RATE))
    estimated_unsold = ended_count - estimated_sold

    return estimated_sold, estimated_unsold


# ── DAILY COLLECTION ──────────────────────────────────────────────────────────

def collect_market_data():
    """Collect daily listing snapshot for all tracked cards."""
    from collector import CARDS_TO_TRACK

    print(f"\n📊  Market dynamics collection at {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("─" * 50)

    token = get_ebay_token()
    print("✅  eBay authenticated\n")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")

    for card in CARDS_TO_TRACK:
        name = card["card_name"]
        query = card["ebay_search_query"]
        print(f"  📊  {name}...")

        # Fetch current active listings
        result = fetch_active_listings(token, query)

        if result["total"] == 0:
            print(f"      ⚠️  No listings found")
            continue

        # Get previous snapshot to calculate new/ended
        c.execute("""
            SELECT active_listings, raw_listing_ids
            FROM listing_snapshots
            WHERE card_name = ? AND snapshot_date < ?
            ORDER BY snapshot_date DESC LIMIT 1
        """, (name, today))
        prev = c.fetchone()

        prev_active = prev[0] if prev else 0
        prev_ids = json.loads(prev[1]) if prev and prev[1] else []
        curr_ids = result["item_ids"]

        # Calculate flows
        new_ids = set(curr_ids) - set(prev_ids)
        ended_ids = set(prev_ids) - set(curr_ids)

        new_listings = len(new_ids) if prev_ids else 0
        ended_listings = len(ended_ids) if prev_ids else 0

        estimated_sold, estimated_unsold = estimate_sold_listings(
            prev_ids, curr_ids, ended_listings
        )

        import statistics
        avg_price = statistics.mean(result["prices"]) if result["prices"] else 0
        median_price = statistics.median(result["prices"]) if result["prices"] else 0

        # Store snapshot
        c.execute("""
            INSERT INTO listing_snapshots
            (card_name, snapshot_date, active_listings, new_listings, ended_listings,
             estimated_sold, estimated_unsold, avg_active_price, avg_sold_price,
             median_active_price, raw_listing_ids)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, today, result["total"], new_listings, ended_listings,
            estimated_sold, estimated_unsold, avg_price, avg_price,
            median_price, json.dumps(curr_ids[:100])  # cap stored IDs
        ))

        print(f"      ✅  Active: {result['total']} | New: {new_listings} | "
              f"Ended: {ended_listings} (Est. sold: {estimated_sold})")

        time.sleep(0.5)

    conn.commit()
    conn.close()

    # Now compute dynamics
    compute_all_dynamics()


# ── DYNAMICS COMPUTATION ──────────────────────────────────────────────────────

def compute_dynamics(card_name: str) -> dict:
    """
    Compute market dynamics for a single card.

    Demand Pressure = estimated_sold / active_listings (7-day avg)
    Supply Saturation Shift = (7-day avg active) / (30-day avg active)
    Market Signal = HEATING / COOLING / STABLE
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")

    # Get 30-day history
    c.execute("""
        SELECT snapshot_date, active_listings, new_listings, ended_listings,
               estimated_sold, estimated_unsold, avg_active_price, median_active_price
        FROM listing_snapshots
        WHERE card_name = ?
        ORDER BY snapshot_date DESC
        LIMIT 30
    """, (card_name,))
    rows = c.fetchall()

    if len(rows) < 2:
        conn.close()
        return {"error": "Not enough data (need at least 2 days)"}

    # Split into 7-day and 30-day windows
    all_data = rows  # most recent first
    data_7d = all_data[:7]
    data_30d = all_data

    # ── Demand Pressure ──
    # (total estimated sold in 7 days) / (avg active listings in 7 days)
    sold_7d = sum(r[4] for r in data_7d)
    avg_active_7d = sum(r[1] for r in data_7d) / len(data_7d)
    demand_pressure = (sold_7d / avg_active_7d * 100) if avg_active_7d > 0 else 0

    # ── Supply Saturation ──
    avg_active_30d = sum(r[1] for r in data_30d) / len(data_30d)
    supply_sat_7d = avg_active_7d
    supply_sat_30d = avg_active_30d
    supply_sat_shift = (avg_active_7d / avg_active_30d) if avg_active_30d > 0 else 1.0

    # ── New Listing Trend ──
    new_7d = sum(r[2] for r in data_7d) / len(data_7d) if data_7d else 0
    new_30d = sum(r[2] for r in data_30d) / len(data_30d) if data_30d else 0
    new_listing_trend = (new_7d / new_30d) if new_30d > 0 else 1.0

    # ── Sales Velocity ──
    # Average daily estimated sales over 7 days
    sales_velocity = sold_7d / len(data_7d) if data_7d else 0

    # ── Price Trends ──
    if len(data_7d) >= 2:
        recent_price = data_7d[0][7]   # median_active_price, most recent
        oldest_7d_price = data_7d[-1][7]
        price_trend_7d = ((recent_price - oldest_7d_price) / oldest_7d_price * 100) if oldest_7d_price > 0 else 0
    else:
        price_trend_7d = 0

    if len(data_30d) >= 2:
        oldest_30d_price = data_30d[-1][7]
        recent_price = data_30d[0][7]
        price_trend_30d = ((recent_price - oldest_30d_price) / oldest_30d_price * 100) if oldest_30d_price > 0 else 0
    else:
        price_trend_30d = 0

    # ── Market Signal ──
    if demand_pressure > 8 and supply_sat_shift < 1.0:
        signal = "HEATING"
    elif demand_pressure < 3 and supply_sat_shift > 1.2:
        signal = "COOLING"
    elif supply_sat_shift < 0.9:
        signal = "TIGHTENING"
    elif supply_sat_shift > 1.1:
        signal = "LOOSENING"
    else:
        signal = "STABLE"

    dynamics = {
        "card_name": card_name,
        "demand_pressure": round(demand_pressure, 2),
        "supply_saturation_7d": round(supply_sat_7d, 1),
        "supply_saturation_30d": round(supply_sat_30d, 1),
        "supply_saturation_shift": round(supply_sat_shift, 3),
        "new_listing_trend": round(new_listing_trend, 3),
        "sales_velocity": round(sales_velocity, 2),
        "price_trend_7d": round(price_trend_7d, 2),
        "price_trend_30d": round(price_trend_30d, 2),
        "market_signal": signal,
    }

    # Store to DB
    c.execute("""
        INSERT INTO market_dynamics
        (card_name, computed_date, demand_pressure, supply_saturation_7d,
         supply_saturation_30d, supply_saturation_shift, new_listing_trend,
         sales_velocity, price_trend_7d, price_trend_30d, market_signal)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        card_name, today, dynamics["demand_pressure"],
        dynamics["supply_saturation_7d"], dynamics["supply_saturation_30d"],
        dynamics["supply_saturation_shift"], dynamics["new_listing_trend"],
        dynamics["sales_velocity"], dynamics["price_trend_7d"],
        dynamics["price_trend_30d"], dynamics["market_signal"]
    ))
    conn.commit()
    conn.close()

    return dynamics


def compute_all_dynamics():
    """Compute dynamics for all tracked cards."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT card_name FROM cards")
    cards = [row[0] for row in c.fetchall()]
    conn.close()

    print(f"\n🧮  Computing market dynamics...")
    for name in cards:
        result = compute_dynamics(name)
        if "error" in result:
            print(f"  ⚠️  {name}: {result['error']}")
        else:
            signal = result["market_signal"]
            dp = result["demand_pressure"]
            ss = result["supply_saturation_shift"]
            print(f"  ✅  {name}: {signal} | Demand: {dp}% | Supply shift: {ss}x")

    print()


# ── API HELPERS (for dashboard) ───────────────────────────────────────────────

def get_all_dynamics() -> list:
    """Get latest dynamics for all cards."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT md.*
        FROM market_dynamics md
        INNER JOIN (
            SELECT card_name, MAX(computed_date) as max_date
            FROM market_dynamics
            GROUP BY card_name
        ) latest ON md.card_name = latest.card_name AND md.computed_date = latest.max_date
    """)
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def get_listing_history(card_name: str = None) -> list:
    """Get listing snapshot history for charts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    if card_name:
        c.execute("""
            SELECT * FROM listing_snapshots
            WHERE card_name = ?
            ORDER BY snapshot_date ASC
        """, (card_name,))
    else:
        c.execute("SELECT * FROM listing_snapshots ORDER BY snapshot_date ASC")

    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


# ── DEMO MODE ─────────────────────────────────────────────────────────────────

def generate_demo_data():
    """Generate 30 days of realistic market dynamics demo data."""
    from collector import CARDS_TO_TRACK

    print("\n🎮  Generating market dynamics demo data (30 days)")
    print("─" * 50)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Scenarios for each card
    scenarios = {
        "Umbreon ex 187 SAR": {
            "base_active": 280, "trend": "cooling",
            "base_price": 1300, "price_drift": -5.0,
            "base_sold_rate": 0.35
        },
        "Mega Charizard ex SIR": {
            "base_active": 150, "trend": "heating",
            "base_price": 780, "price_drift": 2.5,
            "base_sold_rate": 0.55
        },
        "Pikachu ex SIR": {
            "base_active": 200, "trend": "stable",
            "base_price": 950, "price_drift": 4.0,
            "base_sold_rate": 0.42
        },
    }

    for card in CARDS_TO_TRACK:
        name = card["card_name"]
        scenario = scenarios.get(name, {
            "base_active": 180, "trend": "stable",
            "base_price": 100, "price_drift": 0,
            "base_sold_rate": 0.40
        })

        prev_ids = [f"item_{i}" for i in range(scenario["base_active"])]
        item_counter = scenario["base_active"]

        for days_ago in range(30, -1, -1):
            date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

            # Simulate listing flow based on trend
            if scenario["trend"] == "cooling":
                # Supply building up, sales slowing
                new_count = max(5, int(random.gauss(25, 5) + (30 - days_ago) * 0.3))
                sold_rate = max(0.2, scenario["base_sold_rate"] - (30 - days_ago) * 0.005)
            elif scenario["trend"] == "heating":
                # Supply tightening, sales accelerating
                new_count = max(3, int(random.gauss(15, 4) - (30 - days_ago) * 0.2))
                sold_rate = min(0.7, scenario["base_sold_rate"] + (30 - days_ago) * 0.004)
            else:
                new_count = max(3, int(random.gauss(18, 5)))
                sold_rate = scenario["base_sold_rate"] + random.uniform(-0.05, 0.05)

            # Generate new item IDs
            new_ids = [f"item_{item_counter + i}" for i in range(new_count)]
            item_counter += new_count

            # Some old listings end
            end_count = max(0, int(random.gauss(new_count * 0.9, 3)))
            end_count = min(end_count, len(prev_ids))
            ended_ids = random.sample(prev_ids, end_count) if end_count > 0 else []

            estimated_sold = int(end_count * sold_rate)
            estimated_unsold = end_count - estimated_sold

            # Update active listings
            curr_ids = [id for id in prev_ids if id not in ended_ids] + new_ids
            active = len(curr_ids)

            # Price with drift
            price = scenario["base_price"] + scenario["price_drift"] * (30 - days_ago)
            avg_price = price + random.uniform(-10, 10)
            median_price = price + random.uniform(-5, 5)

            c.execute("""
                INSERT INTO listing_snapshots
                (card_name, snapshot_date, active_listings, new_listings, ended_listings,
                 estimated_sold, estimated_unsold, avg_active_price, avg_sold_price,
                 median_active_price, raw_listing_ids)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name, date, active, new_count, end_count,
                estimated_sold, estimated_unsold, avg_price, avg_price * 0.95,
                median_price, json.dumps(curr_ids[-50:])
            ))

            prev_ids = curr_ids

        print(f"  ✅  {name}: 30 days of {scenario['trend']} data")

    conn.commit()
    conn.close()

    # Compute dynamics from the demo data
    compute_all_dynamics()
    print("✅  Demo market dynamics data ready\n")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_market_tables()

    if "--demo" in sys.argv:
        generate_demo_data()
    else:
        collect_market_data()
