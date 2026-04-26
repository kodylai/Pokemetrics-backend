import sqlite3

conn = sqlite3.connect("pokemon_cards.db")
c = conn.cursor()

# Check what's stored for Bill's Transfer
print("=== Bill's Transfer sales ===")
rows = c.execute("""
    SELECT title, sold_price, sold_date 
    FROM sales_history 
    WHERE card_name LIKE '%Bill%Transfer%'
    ORDER BY sold_price DESC
    LIMIT 10
""").fetchall()
for title, price, date in rows:
    print(f"  ${price:>8,.2f}  {date}  {title[:80]}")

print(f"\n=== Charizard ex 199/207 151 sales ===")
rows = c.execute("""
    SELECT title, sold_price, sold_date 
    FROM sales_history 
    WHERE card_name LIKE '%Charizard ex 199%'
    ORDER BY sold_price DESC
    LIMIT 10
""").fetchall()
for title, price, date in rows:
    print(f"  ${price:>8,.2f}  {date}  {title[:80]}")

conn.close()
