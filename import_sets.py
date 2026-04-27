"""
Set Importer v3 — Fixed
=========================
- Uses simpler eBay search queries (no quotes, no /total)
- Uses printedTotal from PokemonTCG API for proper card numbering
- Separate searches per set to avoid Base Set mix-up
"""

import urllib.request
import urllib.parse
import json
import time
import re

PTCG_API = "https://api.pokemontcg.io/v2"

SETS_TO_IMPORT = [
    # ── Classic Sets ──
    {
        "name": "Base Set",
        "search_query": 'set.id:"base1"',  # Exact set ID to avoid mixing with Base Set 2
        "display_name": "Base Set",
        "category": "base_set",
        "mode": "holo_only",
        "min_price_common": 1.00,
        "min_price_rare": 5.00,
        "min_price_chase": 50.00,
    },

    # ── Sword & Shield Era ──
    {
        "name": "Evolving Skies",
        "search_query": 'set.name:"Evolving Skies"',
        "display_name": "Evolving Skies",
        "category": "evolving_skies",
        "mode": "chase_only",
        "min_price_common": 1.00,
        "min_price_rare": 5.00,
        "min_price_chase": 20.00,
    },

    # ── Scarlet & Violet ──
    {
        "name": "Surging Sparks",
        "search_query": 'set.name:"Surging Sparks"',
        "display_name": "Surging Sparks",
        "category": "surging_sparks",
        "mode": "chase_only",
        "min_price_common": 0.50,
        "min_price_rare": 2.00,
        "min_price_chase": 10.00,
    },

    # ── Neo Era (Shining cards) ──
    {
        "name": "Neo Destiny",
        "search_query": 'set.name:"Neo Destiny"',
        "display_name": "Neo Destiny",
        "category": "neo_shining",
        "mode": "shining_only",
        "min_price_chase": 100.00,
    },
    {
        "name": "Neo Revelation",
        "search_query": 'set.name:"Neo Revelation"',
        "display_name": "Neo Revelation",
        "category": "neo_shining",
        "mode": "shining_only",
        "min_price_chase": 100.00,
    },

    # ── e-Reader Crystal Cards ──
    {
        "name": "Skyridge",
        "search_query": 'set.name:"Skyridge"',
        "display_name": "Skyridge",
        "category": "crystal_cards",
        "mode": "crystal_only",
        "min_price_chase": 200.00,
    },
    {
        "name": "Aquapolis",
        "search_query": 'set.name:"Aquapolis"',
        "display_name": "Aquapolis",
        "category": "crystal_cards",
        "mode": "crystal_only",
        "min_price_chase": 200.00,
    },
]

# ── Manual entries for 2026 sets not in PokemonTCG API ──
MANUAL_CARDS = [
    # Phantasmal Flames SIRs
    {"card_name": "Mega Charizard ex SIR Phantasmal Flames", "search_query": "Mega Charizard ex SIR 125 Phantasmal Flames", "expected_price": 1000, "min_price": 50, "category": "phantasmal_flames"},
    {"card_name": "Mega Blastoise ex SIR Phantasmal Flames", "search_query": "Mega Blastoise ex SIR Phantasmal Flames", "expected_price": 200, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Venusaur ex SIR Phantasmal Flames", "search_query": "Mega Venusaur ex SIR Phantasmal Flames", "expected_price": 150, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Gengar ex SIR Phantasmal Flames", "search_query": "Mega Gengar ex SIR Phantasmal Flames", "expected_price": 200, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Rayquaza ex SIR Phantasmal Flames", "search_query": "Mega Rayquaza ex SIR Phantasmal Flames", "expected_price": 300, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Mewtwo ex SIR Phantasmal Flames", "search_query": "Mega Mewtwo ex SIR Phantasmal Flames", "expected_price": 250, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Gardevoir ex SIR Phantasmal Flames", "search_query": "Mega Gardevoir ex SIR Phantasmal Flames", "expected_price": 200, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Lucario ex SIR Phantasmal Flames", "search_query": "Mega Lucario ex SIR Phantasmal Flames", "expected_price": 150, "min_price": 20, "category": "phantasmal_flames"},

    # Ascended Heroes SIRs
    {"card_name": "Pikachu ex SIR Ascended Heroes", "search_query": "Pikachu ex 276 SIR Ascended Heroes", "expected_price": 1500, "min_price": 100, "category": "ascended_heroes"},
    {"card_name": "Dragonite ex SIR Ascended Heroes", "search_query": "Dragonite ex SIR Ascended Heroes", "expected_price": 200, "min_price": 20, "category": "ascended_heroes"},
    {"card_name": "Mewtwo ex SIR Ascended Heroes", "search_query": "Mewtwo ex SIR Ascended Heroes", "expected_price": 200, "min_price": 20, "category": "ascended_heroes"},
    {"card_name": "Mew ex SIR Ascended Heroes", "search_query": "Mew ex SIR Ascended Heroes", "expected_price": 150, "min_price": 20, "category": "ascended_heroes"},
    {"card_name": "Gyarados ex SIR Ascended Heroes", "search_query": "Gyarados ex SIR Ascended Heroes", "expected_price": 150, "min_price": 20, "category": "ascended_heroes"},
]

# Rarity classifications
CHASE_RARITIES = [
    "Special Illustration Rare", "Illustration Rare", "Ultra Rare",
    "Hyper Rare", "ACE SPEC Rare", "Double Rare",
    "Rare BREAK", "Rare Holo VMAX", "Rare Holo VSTAR",
    "Rare Secret", "Rare Rainbow", "Rare Ultra",
]
RARE_RARITIES = ["Rare", "Rare Holo", "Rare Holo EX", "Rare Holo ex"]


def fetch_cards(search_query):
    """Fetch cards using exact PokemonTCG API query."""
    all_cards = []
    page = 1
    while True:
        q = urllib.parse.quote(search_query)
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


def filter_cards(cards, mode):
    if mode == "all":
        return cards
    elif mode == "holo_only":
        return [c for c in cards if "Holo" in (c.get("rarity") or "")]
    elif mode == "chase_only":
        return [c for c in cards if (c.get("rarity") or "") in CHASE_RARITIES]
    elif mode == "shining_only":
        return [c for c in cards if "Shining" in (c.get("name") or "")]
    elif mode == "crystal_only":
        return [c for c in cards if "Crystal" in (c.get("name") or "")]
    return cards


def generate_entries(cards, set_config):
    entries = []
    display_name = set_config.get("display_name", set_config["name"])
    category = set_config["category"]

    for card in cards:
        name = card.get("name", "")
        number = card.get("number", "")
        rarity = card.get("rarity", "Common")
        set_obj = card.get("set", {})
        set_name = set_obj.get("name", display_name)
        printed_total = set_obj.get("printedTotal", "?")

        # Card name: "Charizard 4/102 Base Set"
        card_name = f"{name} {number}/{printed_total} {set_name}"

        # eBay search query — SIMPLE, no quotes, no /total
        # Just: Charizard 4 Base Set -lot -bundle -collection -binder
        search_query = f"{name} {number} {set_name} -lot -bundle -collection -binder"

        # Price tiers
        if rarity in CHASE_RARITIES or "Shining" in name or "Crystal" in name:
            min_price = set_config.get("min_price_chase", 20)
            expected = 100
        elif rarity in RARE_RARITIES:
            min_price = set_config.get("min_price_rare", 5)
            expected = 20
        else:
            min_price = set_config.get("min_price_common", 1)
            expected = 5

        entries.append({
            "card_name": card_name,
            "search_query": search_query,
            "expected_price": expected,
            "min_price": min_price,
            "category": category,
        })

    return entries


def write_output(all_entries, filename="set_cards_config.py"):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Auto-generated — {len(all_entries)} cards\n")
        f.write("# Copy into CARDS_TO_SCRAPE in sales_scraper.py\n\n")
        f.write("NEW_CARDS = [\n")

        current_cat = None
        for entry in all_entries:
            cat = entry.get("category", "")
            if cat != current_cat:
                current_cat = cat
                f.write(f"\n    # ── {cat.upper().replace('_', ' ')} ──\n")

            f.write(f"    {{\n")
            f.write(f'        "card_name": {json.dumps(entry["card_name"])},\n')
            f.write(f'        "search_query": {json.dumps(entry["search_query"])},\n')
            f.write(f'        "expected_price": {entry["expected_price"]},\n')
            f.write(f'        "min_price": {entry["min_price"]},\n')
            f.write(f'        "category": {json.dumps(entry["category"])},\n')
            f.write(f"    }},\n")

        f.write("]\n")
    print(f"\n✅  Wrote {len(all_entries)} entries to {filename}")


def main():
    print("🖼️  Set Importer v3")
    print("─" * 55)

    all_entries = []

    for sc in SETS_TO_IMPORT:
        print(f"\n🔍  {sc['name']} (mode: {sc.get('mode', 'all')})")
        cards = fetch_cards(sc["search_query"])

        if not cards:
            print(f"  ⚠️  No cards found")
            continue

        filtered = filter_cards(cards, sc.get("mode", "all"))
        print(f"  ✅  {len(cards)} total → {len(filtered)} after filter")

        # Show set info
        if cards:
            s = cards[0].get("set", {})
            print(f"  📦  Set: {s.get('name')} | ID: {s.get('id')} | Printed: {s.get('printedTotal')} | Total: {s.get('total')}")

        entries = generate_entries(filtered, sc)
        all_entries.extend(entries)

    # Add manual entries
    if MANUAL_CARDS:
        print(f"\n📝  {len(MANUAL_CARDS)} manual entries (Phantasmal Flames, Ascended Heroes)")
        all_entries.extend(MANUAL_CARDS)

    if all_entries:
        write_output(all_entries)
        print(f"\n📊  Summary:")
        cats = {}
        for e in all_entries:
            cat = e.get("category", "unknown")
            cats[cat] = cats.get(cat, 0) + 1
        for cat, count in sorted(cats.items()):
            print(f"  {cat:<25} {count:>4} cards")
        print(f"  {'TOTAL':<25} {len(all_entries):>4} cards")


if __name__ == "__main__":
    main()
