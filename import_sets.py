"""
Set Importer
==============
Fetches full card lists from the PokemonTCG API and generates
CARDS_TO_SCRAPE entries for sales_scraper.py.

Usage:
  python import_sets.py

This will:
1. Fetch all cards from Prismatic Evolutions and 151
2. Generate a Python file with all card entries
3. Print instructions for adding them to your scraper
"""

import urllib.request
import urllib.parse
import json
import time

PTCG_API = "https://api.pokemontcg.io/v2"

SETS_TO_IMPORT = [
    {
        "name": "Prismatic Evolutions",
        "search": "Prismatic Evolutions",
        "category": "prismatic_evolutions",
        "min_price_common": 0.50,
        "min_price_rare": 2.00,
        "min_price_chase": 20.00,
    },
    {
        "name": "151",
        "search": "151",
        "category": "sv_151",
        "min_price_common": 0.50,
        "min_price_rare": 2.00,
        "min_price_chase": 20.00,
    },
]

# Rarities that count as "chase" (high value)
CHASE_RARITIES = [
    "Special Illustration Rare", "Illustration Rare", "Ultra Rare",
    "Hyper Rare", "ACE SPEC Rare", "Double Rare",
]

RARE_RARITIES = [
    "Rare", "Rare Holo", "Rare Holo EX", "Rare Holo ex",
]


def fetch_set_cards(set_name):
    """Fetch all cards from a set via PokemonTCG API."""
    all_cards = []
    page = 1
    while True:
        q = urllib.parse.quote(f'set.name:"{set_name}"')
        url = f"{PTCG_API}/cards?q={q}&page={page}&pageSize=100&orderBy=number"
        req = urllib.request.Request(url, headers={"User-Agent": "Pokemetrics/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            print(f"  ⚠️  Page {page} error: {e}")
            break

        batch = data.get("data", [])
        all_cards.extend(batch)
        print(f"  📄  Page {page}: {len(batch)} cards")

        if len(batch) < 100:
            break
        page += 1
        time.sleep(0.5)

    return all_cards


def generate_scraper_entries(cards, set_config):
    """Generate CARDS_TO_SCRAPE entries from API card data."""
    entries = []
    set_name = set_config["name"]
    category = set_config["category"]

    for card in cards:
        name = card.get("name", "")
        number = card.get("number", "")
        rarity = card.get("rarity", "Common")
        set_display = card.get("set", {}).get("name", set_name)

        # Build a descriptive card name
        # For cards with same name, add number to distinguish
        card_name = f"{name} {number}/{cards[-1]['number']} {set_display}"

        # Build eBay search query — use QUOTED card name + card number/total + set name
        # This prevents eBay from returning random lots and bundles
        # e.g. '"Bill\'s Transfer" 194/165 "Scarlet Violet 151"' instead of 'Bill\'s Transfer 194 151'
        set_short = set_display.replace("Scarlet & Violet ", "SV ").replace("Sword & Shield ", "SS ")
        search_query = f'"{name}" {number}/{cards[-1]["number"]} "{set_short}" -lot -bundle -set -collection -binder'

        # Set min_price based on rarity
        if rarity in CHASE_RARITIES:
            min_price = set_config["min_price_chase"]
            expected = 50
        elif rarity in RARE_RARITIES:
            min_price = set_config["min_price_rare"]
            expected = 10
        else:
            min_price = set_config["min_price_common"]
            expected = 2

        entries.append({
            "card_name": card_name,
            "search_query": search_query,
            "expected_price": expected,
            "min_price": min_price,
            "category": category,
            "rarity": rarity,
            "number": number,
            "pokemon": name,
        })

    return entries


def write_output(all_entries, filename="set_cards_config.py"):
    """Write all entries to a Python file."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write('"""\n')
        f.write("Auto-generated card scraper config\n")
        f.write(f"Total cards: {len(all_entries)}\n")
        f.write('"""\n\n')
        f.write("# ══════════════════════════════════════════\n")
        f.write("# Copy everything below into CARDS_TO_SCRAPE\n")
        f.write("# in sales_scraper.py\n")
        f.write("# ══════════════════════════════════════════\n\n")
        f.write("NEW_CARDS = [\n")

        current_category = None
        for entry in all_entries:
            cat = entry.get("category", "")
            if cat != current_category:
                current_category = cat
                f.write(f"\n    # ── {cat.upper().replace('_', ' ')} ──\n")

            f.write(f"    {{\n")
            f.write(f'        "card_name": {json.dumps(entry["card_name"])},\n')
            f.write(f'        "search_query": {json.dumps(entry["search_query"])},\n')
            f.write(f'        "expected_price": {entry["expected_price"]},\n')
            f.write(f'        "min_price": {entry["min_price"]},\n')
            f.write(f'        "category": {json.dumps(entry["category"])},\n')
            f.write(f"    }},\n")

        f.write("]\n")

    print(f"\n✅  Wrote {len(all_entries)} card entries to {filename}")
    print(f"    Copy the entries from {filename} into your sales_scraper.py CARDS_TO_SCRAPE list")


def main():
    print("🖼️  Set Importer — Fetching card lists from PokemonTCG API")
    print("─" * 55)

    all_entries = []

    for set_config in SETS_TO_IMPORT:
        print(f"\n🔍  Fetching: {set_config['name']}")
        cards = fetch_set_cards(set_config["search"])
        print(f"  ✅  Found {len(cards)} cards")

        if not cards:
            print(f"  ⚠️  No cards found for '{set_config['search']}'")
            print(f"      The PokemonTCG API might use a different set name.")
            print(f"      Try searching at: https://pokemontcg.io/")
            continue

        entries = generate_scraper_entries(cards, set_config)
        all_entries.extend(entries)

        # Print summary
        chase = sum(1 for e in entries if e["expected_price"] >= 50)
        rare = sum(1 for e in entries if 10 <= e["expected_price"] < 50)
        common = sum(1 for e in entries if e["expected_price"] < 10)
        print(f"  📊  {chase} chase cards, {rare} rares, {common} commons")

    if all_entries:
        write_output(all_entries)
    else:
        print("\n⚠️  No cards fetched. Check the set names and try again.")


if __name__ == "__main__":
    main()
