"""
Card Image Fetcher — Fixed
============================
Uses correct PokemonTCG API rarity ("Rare Holo Star") and set names
(no "EX" prefix — e.g. "Dragon Frontiers" not "EX Dragon Frontiers").

Usage:
  python fetch_images.py
"""

import sys
import re
import json
import time
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime

DB_PATH = "pokemon_cards.db"
PTCG_API = "https://api.pokemontcg.io/v2"

# ── Correct search params (rarity = "Rare Holo Star", set names without "EX" prefix) ──
GOLD_STAR_SEARCH = {
    "Mudkip Gold Star":         ("Mudkip", "Team Rocket Returns"),
    "Torchic Gold Star":        ("Torchic", "Team Rocket Returns"),
    "Treecko Gold Star":        ("Treecko", "Team Rocket Returns"),
    "Latias Gold Star":         ("Latias", "Deoxys"),
    "Latios Gold Star":         ("Latios", "Deoxys"),
    "Rayquaza Gold Star":       ("Rayquaza", "Deoxys"),
    "Entei Gold Star":          ("Entei", "Unseen Forces"),
    "Raikou Gold Star":         ("Raikou", "Unseen Forces"),
    "Suicune Gold Star":        ("Suicune", "Unseen Forces"),
    "Flareon Gold Star Delta":  ("Flareon", "Delta Species"),
    "Jolteon Gold Star Delta":  ("Jolteon", "Delta Species"),
    "Vaporeon Gold Star Delta": ("Vaporeon", "Delta Species"),
    "Gyarados Gold Star":       ("Gyarados", "Holon Phantoms"),
    "Mewtwo Gold Star":         ("Mewtwo", "Holon Phantoms"),
    "Pikachu Gold Star":        ("Pikachu", "Holon Phantoms"),
    "Regirock Gold Star":       ("Regirock", "Legend Maker"),
    "Regice Gold Star":         ("Regice", "Legend Maker"),
    "Registeel Gold Star":      ("Registeel", "Legend Maker"),
    "Alakazam Gold Star":       ("Alakazam", "Crystal Guardians"),
    "Celebi Gold Star":         ("Celebi", "Crystal Guardians"),
    "Charizard Gold Star":      ("Charizard", "Dragon Frontiers"),
    "Mew Gold Star":            ("Mew", "Dragon Frontiers"),
    "Flareon Gold Star PK":     ("Flareon", "Power Keepers"),
    "Jolteon Gold Star PK":     ("Jolteon", "Power Keepers"),
    "Vaporeon Gold Star PK":    ("Vaporeon", "Power Keepers"),
    "Espeon Gold Star":         ("Espeon", "POP Series 5"),
    "Umbreon Gold Star":        ("Umbreon", "POP Series 5"),
}

# ── Manual overrides for cards too new for the API ──
MANUAL_IMAGES = {
    "Umbreon ex 187 SAR":    "https://tcgplayer-cdn.tcgplayer.com/product/594292_200w.jpg",
    "Mega Charizard ex SIR": "https://tcgplayer-cdn.tcgplayer.com/product/662184_200w.jpg",
    "Pikachu ex SIR":        "https://tcgplayer-cdn.tcgplayer.com/product/676088_200w.jpg",
}


def init_image_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS card_images (
            card_name TEXT PRIMARY KEY,
            image_small TEXT,
            image_large TEXT,
            source TEXT,
            fetched_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def search_ptcg_gold_star(pokemon_name, set_name):
    """Search for a Gold Star card using correct rarity and set name."""
    q = urllib.parse.quote(f'name:"{pokemon_name}" set.name:"{set_name}" rarity:"Rare Holo Star"')
    url = f"{PTCG_API}/cards?q={q}&pageSize=3"

    req = urllib.request.Request(url, headers={"User-Agent": "Pokemetrics/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        # Retry without rarity filter
        try:
            q2 = urllib.parse.quote(f'name:"{pokemon_name}" set.name:"{set_name}"')
            url2 = f"{PTCG_API}/cards?q={q2}&pageSize=5&orderBy=-number"
            req2 = urllib.request.Request(url2, headers={"User-Agent": "Pokemetrics/1.0"})
            with urllib.request.urlopen(req2, timeout=15) as resp2:
                data = json.loads(resp2.read().decode())
        except Exception as e2:
            print(f"⚠️  API error: {e2}")
            return {}

    cards = data.get("data", [])
    if not cards:
        return {}

    # Prefer "Rare Holo Star" rarity, or highest card number (Gold Stars are always last)
    best = cards[0]
    for card in cards:
        if card.get("rarity") == "Rare Holo Star":
            best = card
            break
        try:
            if int(card.get("number", 0)) > int(best.get("number", 0)):
                best = card
        except ValueError:
            pass

    return {
        "small": best.get("images", {}).get("small", ""),
        "large": best.get("images", {}).get("large", ""),
    }


def search_ptcg_generic(card_name):
    """Search for any card by name."""
    clean = re.sub(r'\d+', '', card_name)
    clean = re.sub(r'\b(SAR|SIR|IR|HR|MHR|PK|Delta|Gold Star|ex)\b', '', clean, flags=re.IGNORECASE)
    clean = clean.strip().replace("  ", " ")

    q = urllib.parse.quote(f'name:"{clean}"')
    url = f"{PTCG_API}/cards?q={q}&pageSize=1&orderBy=-set.releaseDate"

    req = urllib.request.Request(url, headers={"User-Agent": "Pokemetrics/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return {}

    cards = data.get("data", [])
    if not cards:
        return {}

    return {
        "small": cards[0].get("images", {}).get("small", ""),
        "large": cards[0].get("images", {}).get("large", ""),
    }


def fetch_all_images():
    print(f"\n🖼️  Card Image Fetcher — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("─" * 55)

    init_image_table()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get all unique card names
    c.execute("SELECT DISTINCT card_name FROM sales_history")
    all_cards = [row[0] for row in c.fetchall()]
    c.execute("SELECT DISTINCT card_name FROM cards")
    for row in c.fetchall():
        if row[0] not in all_cards:
            all_cards.append(row[0])

    # Check existing
    c.execute("SELECT card_name FROM card_images WHERE image_small IS NOT NULL AND image_small != ''")
    already_have = set(row[0] for row in c.fetchall())

    to_fetch = [name for name in all_cards if name not in already_have]
    print(f"  📊  {len(all_cards)} total cards, {len(already_have)} already have images, {len(to_fetch)} to fetch\n")

    now = datetime.now().isoformat()
    fetched = 0
    failed = 0

    for name in to_fetch:
        print(f"  🔍  {name}...", end=" ", flush=True)

        # 1. Manual overrides
        if name in MANUAL_IMAGES:
            c.execute("""
                INSERT OR REPLACE INTO card_images (card_name, image_small, image_large, source, fetched_at)
                VALUES (?, ?, ?, 'manual', ?)
            """, (name, MANUAL_IMAGES[name], MANUAL_IMAGES[name], now))
            print("✅ (manual)")
            fetched += 1
            continue

        # 2. Gold Star specific search
        if name in GOLD_STAR_SEARCH:
            pokemon, set_name = GOLD_STAR_SEARCH[name]
            imgs = search_ptcg_gold_star(pokemon, set_name)
        else:
            # 3. Generic search
            imgs = search_ptcg_generic(name)

        if imgs and imgs.get("small"):
            c.execute("""
                INSERT OR REPLACE INTO card_images (card_name, image_small, image_large, source, fetched_at)
                VALUES (?, ?, ?, 'pokemontcg_api', ?)
            """, (name, imgs["small"], imgs.get("large", ""), now))
            print("✅")
            fetched += 1
        else:
            print("❌")
            failed += 1

        time.sleep(0.5)

    conn.commit()
    conn.close()
    print(f"\n✅  Done! {fetched} images fetched, {failed} not found\n")


def get_all_card_images():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT card_name, image_small, image_large FROM card_images")
    result = {}
    for row in c.fetchall():
        result[row[0]] = {"small": row[1], "large": row[2]}
    conn.close()
    return result


if __name__ == "__main__":
    fetch_all_images()
