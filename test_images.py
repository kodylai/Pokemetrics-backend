import urllib.request
import urllib.parse
import json

# Test 1: Try different rarity names
print("=== Testing rarity names for Charizard ===")
for rarity in ["Rare Shining", "Rare Holo Star", "Rare Star", "Rare Secret", "Shiny Rare", "Rare Holo"]:
    q = urllib.parse.quote(f'name:"Charizard" rarity:"{rarity}" set.series:"EX"')
    url = f"https://api.pokemontcg.io/v2/cards?q={q}&pageSize=3"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Pokemetrics/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        count = len(data.get("data", []))
        if count > 0:
            for c in data["data"]:
                print(f"  FOUND with '{rarity}': {c['id']} {c['name']} {c['set']['name']} rarity={c.get('rarity','?')}")
                print(f"    {c['images']['small']}")
        else:
            print(f"  '{rarity}': no results")
    except Exception as e:
        print(f"  '{rarity}': ERROR - {e}")

# Test 2: Search by set name directly
print("\n=== Testing by set name ===")
for set_name in ["EX Dragon Frontiers", "Dragon Frontiers", "ex12"]:
    q = urllib.parse.quote(f'name:"Charizard" set.name:"{set_name}"')
    url = f"https://api.pokemontcg.io/v2/cards?q={q}&pageSize=5"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Pokemetrics/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        count = len(data.get("data", []))
        if count > 0:
            for c in data["data"]:
                print(f"  FOUND with set '{set_name}': {c['id']} #{c['number']} {c['name']} rarity={c.get('rarity','?')}")
                print(f"    {c['images']['small']}")
        else:
            print(f"  set '{set_name}': no results")
    except Exception as e:
        print(f"  set '{set_name}': ERROR - {e}")

# Test 3: Just search Charizard in EX series and find the Gold Star
print("\n=== All Charizards in EX series ===")
q = urllib.parse.quote('name:"Charizard" set.series:"EX"')
url = f"https://api.pokemontcg.io/v2/cards?q={q}&pageSize=20"
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Pokemetrics/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    for c in data.get("data", []):
        print(f"  {c['id']:<20} #{c['number']:<6} {c['name']:<25} {c['set']['name']:<30} rarity={c.get('rarity','?')}")
except Exception as e:
    print(f"  ERROR: {e}")
