import sqlite3

conn = sqlite3.connect("pokemon_cards.db")
c = conn.cursor()

print("=== Titles containing PSA ===")
rows = c.execute("SELECT title, grade_label FROM sales_history WHERE UPPER(title) LIKE '%PSA%' LIMIT 10").fetchall()
for title, grade in rows:
    print(f"  [{grade}] {title[:80]}")
print(f"  Total: {c.execute('SELECT COUNT(*) FROM sales_history WHERE UPPER(title) LIKE ?', ('%PSA%',)).fetchone()[0]}")

print("\n=== Titles containing BGS ===")
rows = c.execute("SELECT title, grade_label FROM sales_history WHERE UPPER(title) LIKE '%BGS%' LIMIT 10").fetchall()
for title, grade in rows:
    print(f"  [{grade}] {title[:80]}")
print(f"  Total: {c.execute('SELECT COUNT(*) FROM sales_history WHERE UPPER(title) LIKE ?', ('%BGS%',)).fetchone()[0]}")

print("\n=== Titles containing CGC ===")
rows = c.execute("SELECT title, grade_label FROM sales_history WHERE UPPER(title) LIKE '%CGC%' LIMIT 10").fetchall()
for title, grade in rows:
    print(f"  [{grade}] {title[:80]}")
print(f"  Total: {c.execute('SELECT COUNT(*) FROM sales_history WHERE UPPER(title) LIKE ?', ('%CGC%',)).fetchone()[0]}")

print("\n=== Grade breakdown ===")
rows = c.execute("SELECT grade_label, COUNT(*) as cnt FROM sales_history GROUP BY grade_label ORDER BY cnt DESC").fetchall()
for label, cnt in rows:
    print(f"  {label:<25} {cnt:>6}")

print(f"\n=== Total records: {c.execute('SELECT COUNT(*) FROM sales_history').fetchone()[0]} ===")
conn.close()
