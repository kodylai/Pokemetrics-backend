"""
Set Importer v2
=================
Fetches full card lists from the PokemonTCG API and generates
CARDS_TO_SCRAPE entries for sales_scraper.py.

Sets included:
- Base Set (holos)
- Evolving Skies (alt arts + chase)
- Phantasmal Flames (full set)
- Ascended Heroes (full set)
- Surging Sparks (chase cards)
- Crystal cards (Skyridge + Aquapolis)
- Shining cards (Neo Destiny + Neo Revelation)

Usage:
  python import_sets.py
"""

import urllib.request
import urllib.parse
import json
import time
import re

PTCG_API = "https://api.pokemontcg.io/v2"

# ══════════════════════════════════════════════════════════════════
# SETS TO IMPORT
# ══════════════════════════════════════════════════════════════════

SETS_TO_IMPORT = [
    # ── Already tracking (skip these if re-running) ──
    # Uncomment if you need to regenerate
    # {
    #     "name": "Prismatic Evolutions",
    #     "search": "Prismatic Evolutions",
    #     "category": "prismatic_evolutions",
    #     "mode": "all",
    # },
    # {
    #     "name": "151",
    #     "search": "151",
    #     "category": "sv_151",
    #     "mode": "all",
    # },

    # ── Classic Sets ──
    {
        "name": "Base Set",
        "search": "Base",
        "category": "base_set",
        "mode": "holo_only",  # Only holos — the iconic cards
        "min_price_common": 1.00,
        "min_price_rare": 5.00,
        "min_price_chase": 50.00,
    },

    # ── Sword & Shield Era ──
    {
        "name": "Evolving Skies",
        "search": "Evolving Skies",
        "category": "evolving_skies",
        "mode": "chase_only",  # Alt arts and ultra rares only
        "min_price_common": 1.00,
        "min_price_rare": 5.00,
        "min_price_chase": 20.00,
    },

    # ── Scarlet & Violet 2025-2026 ──
    {
        "name": "Surging Sparks",
        "search": "Surging Sparks",
        "category": "surging_sparks",
        "mode": "chase_only",
        "min_price_common": 0.50,
        "min_price_rare": 2.00,
        "min_price_chase": 10.00,
    },

    # ── Neo Era ──
    {
        "name": "Neo Destiny",
        "search": "Neo Destiny",
        "category": "neo_shining",
        "mode": "shining_only",  # Only Shining cards
        "min_price_chase": 100.00,
    },
    {
        "name": "Neo Revelation",
        "search": "Neo Revelation",
        "category": "neo_shining",
        "mode": "shining_only",
        "min_price_chase": 100.00,
    },

    # ── e-Reader Crystal Cards ──
    {
        "name": "Skyridge",
        "search": "Skyridge",
        "category": "crystal_cards",
        "mode": "crystal_only",  # Only Crystal type cards
        "min_price_chase": 200.00,
    },
    {
        "name": "Aquapolis",
        "search": "Aquapolis",
        "category": "crystal_cards",
        "mode": "crystal_only",
        "min_price_chase": 200.00,
    },
]

# ── Manual card entries for sets the API might not have yet ──
MANUAL_CARDS = [
    # Phantasmal Flames — 2026 set, may not be in API yet
    # Add the chase cards manually
    {"card_name": "Mega Charizard ex SIR", "search_query": "Mega Charizard ex 125 Phantasmal Flames", "expected_price": 1000, "min_price": 50, "category": "phantasmal_flames"},
    {"card_name": "Mega Blastoise ex SIR", "search_query": "Mega Blastoise ex SIR Phantasmal Flames", "expected_price": 200, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Venusaur ex SIR", "search_query": "Mega Venusaur ex SIR Phantasmal Flames", "expected_price": 150, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Gengar ex SIR", "search_query": "Mega Gengar ex SIR Phantasmal Flames", "expected_price": 200, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Rayquaza ex SIR", "search_query": "Mega Rayquaza ex SIR Phantasmal Flames", "expected_price": 300, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Mewtwo ex SIR", "search_query": "Mega Mewtwo ex SIR Phantasmal Flames", "expected_price": 250, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Gardevoir ex SIR", "search_query": "Mega Gardevoir ex SIR Phantasmal Flames", "expected_price": 200, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Lucario ex SIR", "search_query": "Mega Lucario ex SIR Phantasmal Flames", "expected_price": 150, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Sceptile ex SIR", "search_query": "Mega Sceptile ex SIR Phantasmal Flames", "expected_price": 100, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Swampert ex SIR", "search_query": "Mega Swampert ex SIR Phantasmal Flames", "expected_price": 100, "min_price": 20, "category": "phantasmal_flames"},
    {"card_name": "Mega Blaziken ex SIR", "search_query": "Mega Blaziken ex SIR Phantasmal Flames", "expected_price": 100, "min_price": 20, "category": "phantasmal_flames"},

    # Ascended Heroes — 2026 set
    {"card_name": "Pikachu ex SIR", "search_query": "Pikachu ex 276 Ascended Heroes", "expected_price": 1500, "min_price": 100, "category": "ascended_heroes"},
    {"card_name": "Dragonite ex SIR", "search_query": "Dragonite ex SIR Ascended Heroes", "expected_price": 200, "min_price": 20, "category": "ascended_heroes"},
    {"card_name": "Mewtwo ex SIR", "search_query": "Mewtwo ex SIR Ascended Heroes", "expected_price": 200, "min_price": 20, "category": "ascended_heroes"},
    {"card_name": "Mew ex SIR", "search_query": "Mew ex SIR Ascended Heroes", "expected_price": 150, "min_price": 20, "category": "ascended_heroes"},
    {"card_name": "Gyarados ex SIR", "search_query": "Gyarados ex SIR Ascended Heroes", "expected_price": 150, "min_price": 20, "category": "ascended_heroes"},
    {"card_name": "Arcanine ex SIR", "search_query": "Arcanine ex SIR Ascended Heroes", "expected_price": 100, "min_price": 20, "category": "ascended_heroes"},
]

# Rarities
CHASE_RARITIES = [
    "Special Illustration Rare", "Illustration Rare", "Ultra Rare",
    "Hyper Rare", "ACE SPEC Rare", "Double Rare",
    "Rare BREAK", "Rare Holo VMAX", "Rare Holo VSTAR",
    "Rare Secret", "Rare Rainbow", "Rare Ultra",
]
RARE_RARITIES = ["Rare", "Rare Holo", "Rare Holo EX", "Rare Holo ex"]
SHINING_RARITIES = ["Rare Shining"]
CRYSTAL_RARITIES = ["Rare Holo"]


def fetch_set_cards(set_name):
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


def filter_cards(cards, mode):
    """Filter cards based on mode."""
    if mode == "all":
        return cards
    elif mode == "holo_only":
        return [c for c in cards if "Holo" in (c.get("rarity") or "") or c.get("supertype") == "Energy"]
    elif mode == "chase_only":
        return [c for c in cards if (c.get("rarity") or "") in CHASE_RARITIES]
    elif mode == "shining_only":
        return [c for c in cards if "Shining" in (c.get("name") or "") or (c.get("rarity") or "") in SHINING_RARITIES]
    elif mode == "crystal_only":
        return [c for c in cards if "Crystal" in (c.get("name") or "")]
    return cards


def generate_entries(cards, set_config):
    entries = []
    set_name = set_config["name"]
    category = set_config["category"]
    total = cards[-1]["number"] if cards else "?"

    for card in cards:
        name = card.get("name", "")
        number = card.get("number", "")
        rarity = card.get("rarity", "Common")
        set_display = card.get("set", {}).get("name", set_name)

        card_name = f"{name} {number}/{total} {set_display}"

        # Build precise eBay search query
        set_short = set_display.replace("Scarlet & Violet ", "SV ").replace("Sword & Shield ", "SS ")
        search_query = f'"{name}" {number}/{total} "{set_short}" -lot -bundle -collection -binder'

        if rarity in CHASE_RARITIES or rarity in SHINING_RARITIES:
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
        f.write(f'# Auto-generated card config — {len(all_entries)} cards\n')
        f.write('# Copy into CARDS_TO_SCRAPE in sales_scraper.py\n\n')
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

    print(f"\n✅  Wrote {len(all_entries)} card entries to {filename}")


def main():
    print("🖼️  Set Importer v2")
    print("─" * 55)

    all_entries = []

    for sc in SETS_TO_IMPORT:
        print(f"\n🔍  Fetching: {sc['name']} (mode: {sc.get('mode', 'all')})")
        cards = fetch_set_cards(sc["search"])

        if not cards:
            print(f"  ⚠️  No cards found for '{sc['search']}'")
            continue

        filtered = filter_cards(cards, sc.get("mode", "all"))
        print(f"  ✅  {len(cards)} total, {len(filtered)} after filter ({sc.get('mode', 'all')})")

        entries = generate_entries(filtered, sc)
        all_entries.extend(entries)

    # Add manual cards
    if MANUAL_CARDS:
        print(f"\n📝  Adding {len(MANUAL_CARDS)} manual card entries")
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
    else:
        print("\n⚠️  No cards fetched.")


if __name__ == "__main__":
    main()
