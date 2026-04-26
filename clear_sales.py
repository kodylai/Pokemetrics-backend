import sqlite3

conn = sqlite3.connect("pokemon_cards.db")
c = conn.cursor()

count = c.execute("SELECT COUNT(*) FROM sales_history").fetchone()[0]
print(f"Current records: {count}")

confirm = input("Delete ALL sales data and re-scrape fresh? (type YES): ")
if confirm == "YES":
    c.execute("DELETE FROM sales_history")
    conn.commit()
    print(f"Deleted {count} records. Run sales_scraper.py to re-scrape.")
else:
    print("Cancelled.")

conn.close()
