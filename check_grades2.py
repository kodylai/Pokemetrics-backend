import sqlite3

conn = sqlite3.connect("pokemon_cards.db")
c = conn.cursor()

# Show 20 most recent titles that should be graded
print("=== 20 most recent titles from graded search ===")
rows = c.execute("""
    SELECT title, sold_price, grade_label 
    FROM sales_history 
    WHERE scraped_at = (SELECT MAX(scraped_at) FROM sales_history)
    ORDER BY sold_price DESC
    LIMIT 20
""").fetchall()
for title, price, grade in rows:
    has_psa = "PSA" in title.upper()
    has_bgs = "BGS" in title.upper()
    has_cgc = "CGC" in title.upper()
    flag = "PSA" if has_psa else "BGS" if has_bgs else "CGC" if has_cgc else "---"
    print(f"  [{grade:<10}] [{flag}] ${price:>10,.2f}  {title[:90]}")

print(f"\n=== Total PSA in titles: {c.execute('SELECT COUNT(*) FROM sales_history WHERE UPPER(title) LIKE ?', ('%PSA%',)).fetchone()[0]}")
print(f"=== Total BGS in titles: {c.execute('SELECT COUNT(*) FROM sales_history WHERE UPPER(title) LIKE ?', ('%BGS%',)).fetchone()[0]}")
print(f"=== Total CGC in titles: {c.execute('SELECT COUNT(*) FROM sales_history WHERE UPPER(title) LIKE ?', ('%CGC%',)).fetchone()[0]}")

conn.close()
