import sqlite3
conn = sqlite3.connect("pokemon_cards.db")
c = conn.cursor()

psa = c.execute("SELECT COUNT(*) FROM sales_history WHERE UPPER(title) LIKE '%PSA%'").fetchone()[0]
bgs = c.execute("SELECT COUNT(*) FROM sales_history WHERE UPPER(title) LIKE '%BGS%' OR UPPER(title) LIKE '%BECKETT%'").fetchone()[0]
cgc = c.execute("SELECT COUNT(*) FROM sales_history WHERE UPPER(title) LIKE '%CGC%'").fetchone()[0]

print(f"PSA in title: {psa}")
print(f"BGS/Beckett in title: {bgs}")
print(f"CGC in title: {cgc}")

# Show some sample titles from recent scrape
print("\n=== 5 most recent titles ===")
for row in c.execute("SELECT title FROM sales_history ORDER BY id DESC LIMIT 5").fetchall():
    print(f"  {row[0][:100]}")

conn.close()
