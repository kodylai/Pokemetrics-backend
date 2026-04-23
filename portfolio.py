"""
Pokemon Card Portfolio Manager
================================
Track your personal collection with real-time valuations.

Features:
  - Add/remove cards from your portfolio
  - Track quantity, purchase price, and condition per card
  - Calculate current value using latest sales data
  - Show total portfolio value, profit/loss, and breakdown
  - Multiple portfolios (e.g., "Main Collection", "Investment", "Trade Binder")

All data stored locally in your SQLite database.
"""

import sqlite3
import sys
import json
from datetime import datetime

DB_PATH = "pokemon_cards.db"


# ── DATABASE ──────────────────────────────────────────────────────────────────

def init_portfolio_tables():
    """Create portfolio tables."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Portfolios (a user can have multiple)
    c.execute("""
        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT
        )
    """)

    # Individual cards in a portfolio
    c.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            card_name TEXT NOT NULL,
            set_name TEXT DEFAULT '',
            pokemon TEXT DEFAULT '',
            quantity INTEGER DEFAULT 1,
            purchase_price REAL DEFAULT 0,
            purchase_date TEXT DEFAULT '',
            condition TEXT DEFAULT 'Near Mint',
            notes TEXT DEFAULT '',
            added_at TEXT,
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
        )
    """)

    # Snapshot portfolio value over time for tracking gains
    c.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL,
            snapshot_date TEXT,
            total_value REAL,
            total_cost REAL,
            total_cards INTEGER,
            card_values TEXT,
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_portfolio_cards_pid
        ON portfolio_cards(portfolio_id)
    """)

    # Create a default portfolio if none exist
    c.execute("SELECT COUNT(*) FROM portfolios")
    if c.fetchone()[0] == 0:
        now = datetime.now().isoformat()
        c.execute("""
            INSERT INTO portfolios (name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, ("My Collection", "Main Pokémon card collection", now, now))

    conn.commit()
    conn.close()
    print("✅  Portfolio tables initialized")


# ── PORTFOLIO CRUD ────────────────────────────────────────────────────────────

def create_portfolio(name: str, description: str = "") -> dict:
    """Create a new portfolio."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()

    try:
        c.execute("""
            INSERT INTO portfolios (name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (name, description, now, now))
        conn.commit()
        portfolio_id = c.lastrowid
        conn.close()
        return {"id": portfolio_id, "name": name, "description": description}
    except sqlite3.IntegrityError:
        conn.close()
        return {"error": f"Portfolio '{name}' already exists"}


def get_portfolios() -> list:
    """List all portfolios with card counts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT p.*,
               COALESCE(SUM(pc.quantity), 0) as total_cards,
               COALESCE(SUM(pc.purchase_price * pc.quantity), 0) as total_cost
        FROM portfolios p
        LEFT JOIN portfolio_cards pc ON p.id = pc.portfolio_id
        GROUP BY p.id
        ORDER BY p.created_at DESC
    """)

    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def delete_portfolio(portfolio_id: int) -> dict:
    """Delete a portfolio and all its cards."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM portfolio_cards WHERE portfolio_id = ?", (portfolio_id,))
    c.execute("DELETE FROM portfolio_snapshots WHERE portfolio_id = ?", (portfolio_id,))
    c.execute("DELETE FROM portfolios WHERE id = ?", (portfolio_id,))
    deleted = c.rowcount
    conn.commit()
    conn.close()
    return {"deleted": deleted > 0}


def rename_portfolio(portfolio_id: int, name: str, description: str = None) -> dict:
    """Rename a portfolio."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()

    if description is not None:
        c.execute("""
            UPDATE portfolios SET name = ?, description = ?, updated_at = ?
            WHERE id = ?
        """, (name, description, now, portfolio_id))
    else:
        c.execute("""
            UPDATE portfolios SET name = ?, updated_at = ?
            WHERE id = ?
        """, (name, now, portfolio_id))

    conn.commit()
    conn.close()
    return {"success": True}


# ── CARD MANAGEMENT ───────────────────────────────────────────────────────────

def add_card(portfolio_id: int, card_name: str, set_name: str = "",
             pokemon: str = "", quantity: int = 1, purchase_price: float = 0,
             purchase_date: str = "", condition: str = "Near Mint",
             notes: str = "") -> dict:
    """Add a card to a portfolio."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()

    c.execute("""
        INSERT INTO portfolio_cards
        (portfolio_id, card_name, set_name, pokemon, quantity,
         purchase_price, purchase_date, condition, notes, added_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        portfolio_id, card_name, set_name, pokemon, quantity,
        purchase_price, purchase_date, condition, notes, now
    ))

    # Update portfolio timestamp
    c.execute("UPDATE portfolios SET updated_at = ? WHERE id = ?", (now, portfolio_id))

    card_id = c.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": card_id,
        "card_name": card_name,
        "quantity": quantity,
        "purchase_price": purchase_price,
    }


def update_card(card_id: int, **kwargs) -> dict:
    """Update a card's details."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    allowed = ["card_name", "set_name", "pokemon", "quantity",
               "purchase_price", "purchase_date", "condition", "notes"]

    updates = []
    values = []
    for key, value in kwargs.items():
        if key in allowed:
            updates.append(f"{key} = ?")
            values.append(value)

    if not updates:
        conn.close()
        return {"error": "No valid fields to update"}

    values.append(card_id)
    c.execute(f"UPDATE portfolio_cards SET {', '.join(updates)} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return {"success": True}


def remove_card(card_id: int) -> dict:
    """Remove a card from a portfolio."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM portfolio_cards WHERE id = ?", (card_id,))
    deleted = c.rowcount
    conn.commit()
    conn.close()
    return {"deleted": deleted > 0}


def get_portfolio_cards(portfolio_id: int) -> list:
    """Get all cards in a portfolio."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT * FROM portfolio_cards
        WHERE portfolio_id = ?
        ORDER BY added_at DESC
    """, (portfolio_id,))

    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


# ── VALUATION ─────────────────────────────────────────────────────────────────

def get_current_price(card_name: str) -> dict:
    """
    Get the best current price estimate for a card.
    Priority: verified sales median > all sales median > price history > 0
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Try verified sales first (confidence >= 60)
    c.execute("""
        SELECT
            ROUND(AVG(sold_price), 2) as avg_price,
            COUNT(*) as num_sales
        FROM (
            SELECT sold_price FROM sales_history
            WHERE card_name = ? AND confidence_score >= 60
                  AND sold_price > 0
            ORDER BY sold_date DESC
            LIMIT 10
        )
    """, (card_name,))
    row = c.fetchone()
    if row and row[0] and row[1] >= 3:
        conn.close()
        return {"price": row[0], "source": "verified_sales", "num_sales": row[1]}

    # Fallback: all recent sales
    c.execute("""
        SELECT
            ROUND(AVG(sold_price), 2) as avg_price,
            COUNT(*) as num_sales
        FROM (
            SELECT sold_price FROM sales_history
            WHERE card_name = ? AND sold_price > 0
            ORDER BY sold_date DESC
            LIMIT 10
        )
    """, (card_name,))
    row = c.fetchone()
    if row and row[0] and row[1] >= 1:
        conn.close()
        return {"price": row[0], "source": "all_sales", "num_sales": row[1]}

    # Fallback: price history (from collector.py)
    c.execute("""
        SELECT median_price FROM price_history
        WHERE card_name = ? AND median_price > 0
        ORDER BY timestamp DESC LIMIT 1
    """, (card_name,))
    row = c.fetchone()
    if row and row[0]:
        conn.close()
        return {"price": row[0], "source": "price_history", "num_sales": 0}

    conn.close()
    return {"price": 0, "source": "unknown", "num_sales": 0}


def valuate_portfolio(portfolio_id: int) -> dict:
    """
    Calculate full portfolio valuation.
    Returns total value, cost basis, profit/loss, and per-card breakdown.
    """
    cards = get_portfolio_cards(portfolio_id)

    if not cards:
        return {
            "portfolio_id": portfolio_id,
            "total_value": 0,
            "total_cost": 0,
            "total_profit": 0,
            "total_profit_pct": 0,
            "total_cards": 0,
            "total_unique": 0,
            "cards": [],
        }

    card_details = []
    total_value = 0
    total_cost = 0
    total_cards = 0

    for card in cards:
        pricing = get_current_price(card["card_name"])
        current_price = pricing["price"]
        qty = card["quantity"]
        cost_per = card["purchase_price"]

        card_value = current_price * qty
        card_cost = cost_per * qty
        profit = card_value - card_cost
        profit_pct = ((profit / card_cost) * 100) if card_cost > 0 else 0

        total_value += card_value
        total_cost += card_cost
        total_cards += qty

        card_details.append({
            "id": card["id"],
            "card_name": card["card_name"],
            "set_name": card["set_name"],
            "pokemon": card["pokemon"],
            "quantity": qty,
            "condition": card["condition"],
            "purchase_price": cost_per,
            "purchase_date": card["purchase_date"],
            "current_price": current_price,
            "price_source": pricing["source"],
            "card_value": round(card_value, 2),
            "card_cost": round(card_cost, 2),
            "profit": round(profit, 2),
            "profit_pct": round(profit_pct, 1),
            "notes": card["notes"],
        })

    total_profit = total_value - total_cost
    total_profit_pct = ((total_profit / total_cost) * 100) if total_cost > 0 else 0

    return {
        "portfolio_id": portfolio_id,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_profit": round(total_profit, 2),
        "total_profit_pct": round(total_profit_pct, 1),
        "total_cards": total_cards,
        "total_unique": len(cards),
        "cards": sorted(card_details, key=lambda x: x["card_value"], reverse=True),
    }


# ── SNAPSHOTS (track value over time) ────────────────────────────────────────

def take_snapshot(portfolio_id: int) -> dict:
    """Save a point-in-time snapshot of portfolio value."""
    valuation = valuate_portfolio(portfolio_id)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")

    # Store card-level values for historical reference
    card_values = json.dumps([
        {"card_name": cd["card_name"], "value": cd["card_value"], "price": cd["current_price"]}
        for cd in valuation["cards"]
    ])

    c.execute("""
        INSERT INTO portfolio_snapshots
        (portfolio_id, snapshot_date, total_value, total_cost, total_cards, card_values)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        portfolio_id, today, valuation["total_value"],
        valuation["total_cost"], valuation["total_cards"], card_values
    ))

    conn.commit()
    conn.close()

    return {"snapshot_date": today, "total_value": valuation["total_value"]}


def get_portfolio_history(portfolio_id: int) -> list:
    """Get portfolio value history for charting."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT snapshot_date, total_value, total_cost, total_cards
        FROM portfolio_snapshots
        WHERE portfolio_id = ?
        ORDER BY snapshot_date ASC
    """, (portfolio_id,))

    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


# ── DEMO DATA ─────────────────────────────────────────────────────────────────

def create_demo_portfolio():
    """Create a sample portfolio for testing."""
    init_portfolio_tables()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Check if demo data already exists
    c.execute("SELECT id FROM portfolios WHERE name = 'My Collection'")
    row = c.fetchone()
    portfolio_id = row[0] if row else 1
    conn.close()

    # Add sample cards
    sample_cards = [
        {
            "card_name": "Umbreon ex 187 SAR",
            "set_name": "Prismatic Evolutions",
            "pokemon": "Umbreon",
            "quantity": 1,
            "purchase_price": 900,
            "purchase_date": "2026-02-15",
            "condition": "Near Mint",
            "notes": "Pulled from a booster box",
        },
        {
            "card_name": "Mega Charizard ex SIR",
            "set_name": "Phantasmal Flames",
            "pokemon": "Charizard",
            "quantity": 1,
            "purchase_price": 650,
            "purchase_date": "2026-03-01",
            "condition": "Near Mint",
            "notes": "Bought raw on eBay",
        },
        {
            "card_name": "Pikachu ex SIR",
            "set_name": "Ascended Heroes",
            "pokemon": "Pikachu",
            "quantity": 2,
            "purchase_price": 800,
            "purchase_date": "2026-03-20",
            "condition": "Near Mint",
            "notes": "One to keep, one to trade",
        },
        {
            "card_name": "Mewtwo ex SAR",
            "set_name": "Destined Rivals",
            "pokemon": "Mewtwo",
            "quantity": 1,
            "purchase_price": 150,
            "purchase_date": "2026-01-10",
            "condition": "Lightly Played",
            "notes": "Got a deal on this one",
        },
    ]

    for card in sample_cards:
        add_card(portfolio_id, **card)

    print(f"✅  Demo portfolio created with {len(sample_cards)} cards")

    # Take a snapshot
    snap = take_snapshot(portfolio_id)
    print(f"📸  Snapshot taken — portfolio value: ${snap['total_value']:,.2f}")


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_portfolio_tables()

    if "--demo" in sys.argv:
        create_demo_portfolio()
    else:
        # Show portfolio valuation
        portfolios = get_portfolios()
        if not portfolios:
            print("No portfolios found. Run with --demo to create one.")
        else:
            for p in portfolios:
                print(f"\n📁  {p['name']} ({p['total_cards']} cards)")
                val = valuate_portfolio(p["id"])
                print(f"    💰  Value:  ${val['total_value']:,.2f}")
                print(f"    💵  Cost:   ${val['total_cost']:,.2f}")
                pnl = val['total_profit']
                pct = val['total_profit_pct']
                emoji = "📈" if pnl >= 0 else "📉"
                print(f"    {emoji}  P/L:    ${pnl:,.2f} ({pct:+.1f}%)")
                print()
                for card in val["cards"]:
                    c_pnl = card["profit"]
                    c_emoji = "🟢" if c_pnl >= 0 else "🔴"
                    print(f"    {c_emoji}  {card['card_name']:<30} x{card['quantity']}  "
                          f"${card['current_price']:>8,.2f}  "
                          f"(paid ${card['purchase_price']:,.2f})  "
                          f"{card['profit_pct']:+.1f}%")
