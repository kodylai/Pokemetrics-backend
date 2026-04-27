"""
FAST SCRAPER UPGRADE
=====================
Replace the collect_all_sales() function in sales_scraper.py with this version.
Also add the helper functions (get_last_scraped_times, should_skip, scrape_card_batch)
above collect_all_sales.

Features:
- Skips cards scraped within the last 12 hours
- Runs 3 parallel Chrome browsers for ~3x speed
- 1 page for cheap cards, 2 pages for expensive ones
- Commits after each card to avoid database locks
"""

import threading

# ── CONFIG ──
SKIP_HOURS = 12     # Skip cards scraped within this many hours
NUM_BROWSERS = 3    # Number of parallel Chrome instances


def get_last_scraped_times():
    """Get the most recent scrape time for each card."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT card_name, MAX(scraped_at) as last_scraped
        FROM sales_history GROUP BY card_name
    """)
    result = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return result


def should_skip(card_name, last_scraped_times, skip_hours=SKIP_HOURS):
    """Check if a card was scraped recently enough to skip."""
    last = last_scraped_times.get(card_name)
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
        return (datetime.now() - last_dt).total_seconds() / 3600 < skip_hours
    except (ValueError, TypeError):
        return False


def scrape_card_batch(cards_batch, verified_only, headless, batch_id):
    """Scrape a batch of cards with one browser instance."""
    driver = create_browser(headless=headless)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    scraped_at = datetime.now().isoformat()
    batch_new = 0
    batch_filtered = 0

    try:
        for card in cards_batch:
            name = card["card_name"]
            query = card["search_query"]
            expected = card.get("expected_price", 0)
            print(f"  [{batch_id}] 🔍  {name}")

            sales = scrape_sold_listings(
                driver, query,
                expected_price=expected,
                min_price=card.get("min_price"),
                max_price=card.get("max_price"),
                pages=2 if expected >= 20 else 1,
            )

            if not sales:
                print(f"  [{batch_id}]     ⚠️  No listings found")
                continue

            new_count = 0
            filtered_count = 0
            for sale in sales:
                if verified_only and sale["confidence_score"] < 60:
                    filtered_count += 1
                    continue
                if is_blacklisted(sale["title"]):
                    filtered_count += 1
                    continue
                try:
                    c.execute("""
                        INSERT OR IGNORE INTO sales_history
                        (card_name, title, sold_price, sold_date, condition,
                         listing_type, url, scraped_at, confidence_score,
                         confidence_flags, seller_feedback, bid_count, best_offer)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        name, sale["title"], sale["sold_price"],
                        sale["sold_date"], sale["condition"],
                        sale["listing_type"], sale["url"], scraped_at,
                        sale["confidence_score"], sale["confidence_flags"],
                        sale["seller_feedback"], sale["bid_count"],
                        1 if sale["best_offer"] else 0,
                    ))
                    if c.rowcount > 0:
                        new_count += 1
                except sqlite3.IntegrityError:
                    pass

            batch_new += new_count
            batch_filtered += filtered_count
            prices_all = [s["sold_price"] for s in sales if s["sold_price"] > 0]
            print(f"  [{batch_id}]     ✅  {len(sales)} sales ({new_count} new, {filtered_count} filtered)")
            if prices_all:
                import statistics
                print(f"  [{batch_id}]     💵  Median: ${statistics.median(prices_all):,.2f}")

            conn.commit()
            time.sleep(random.uniform(2, 4))
    finally:
        driver.quit()
        conn.commit()
        conn.close()

    return batch_new, batch_filtered


# ══════════════════════════════════════════════════════════════════
# Replace your existing collect_all_sales() with this:
# ══════════════════════════════════════════════════════════════════

def collect_all_sales(verified_only=False, headless=False):
    """Scrape with skip logic + parallel browsers."""
    mode = "VERIFIED ONLY" if verified_only else "ALL SALES"
    print(f"\n💰  Sales History Scraper [{mode}] — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("─" * 60)

    last_scraped = get_last_scraped_times()
    cards_to_run = []
    skipped = 0
    for card in CARDS_TO_SCRAPE:
        if should_skip(card["card_name"], last_scraped):
            skipped += 1
        else:
            cards_to_run.append(card)

    print(f"  📊  {len(CARDS_TO_SCRAPE)} total, {skipped} skipped (<{SKIP_HOURS}h old), {len(cards_to_run)} to scrape")

    if not cards_to_run:
        print("  ✅  All cards up to date!\n")
        return

    total_new = 0
    total_filtered = 0
    num_browsers = min(NUM_BROWSERS, len(cards_to_run))

    if num_browsers <= 1:
        print(f"  🌐  Launching 1 browser...\n")
        new, filtered = scrape_card_batch(cards_to_run, verified_only, headless, "A")
        total_new += new
        total_filtered += filtered
    else:
        batches = [[] for _ in range(num_browsers)]
        for i, card in enumerate(cards_to_run):
            batches[i % num_browsers].append(card)

        labels = ["A", "B", "C", "D", "E"][:num_browsers]
        print(f"  🌐  Launching {num_browsers} parallel browsers...")
        for i, batch in enumerate(batches):
            print(f"      Browser {labels[i]}: {len(batch)} cards")
        print()

        results = [None] * num_browsers
        threads = []

        def run_batch(idx, batch, label):
            results[idx] = scrape_card_batch(batch, verified_only, headless, label)

        for i, batch in enumerate(batches):
            t = threading.Thread(target=run_batch, args=(i, batch, labels[i]))
            threads.append(t)
            t.start()
            time.sleep(2)

        for t in threads:
            t.join()

        for r in results:
            if r:
                total_new += r[0]
                total_filtered += r[1]

    # ── GRADED SEARCH PASS (single browser) ──
    GRADED_SEARCHES = ["PSA", "BGS", "CGC"]
    GRADED_THRESHOLD = 50
    graded_cards = [c for c in CARDS_TO_SCRAPE if c.get("expected_price", 0) >= GRADED_THRESHOLD]

    if graded_cards:
        print(f"\n{'='*55}")
        print(f"  🏅  GRADED PASS — {len(graded_cards)} cards × 3 graders × 3 grades")
        print(f"{'='*55}\n")

        driver = create_browser(headless=headless)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        scraped_at = datetime.now().isoformat()

        try:
            for card in graded_cards:
                name = card["card_name"]
                clean_query = card["search_query"].replace('"', '')
                clean_query = re.sub(r'-\w+', '', clean_query)
                clean_query = re.sub(r'\s+', ' ', clean_query).strip()

                for grader in GRADED_SEARCHES:
                    grades = ["10", "9", "8"] if grader == "PSA" else ["10", "9.5", "9"]
                    for grade_num in grades:
                        gq = f"{grader} {grade_num} {clean_query}"
                        print(f"  🏅  {name} [{grader} {grade_num}]")

                        sales = scrape_sold_listings(driver, gq,
                            expected_price=card.get("expected_price", 0) * 2,
                            min_price=card.get("min_price", 0), pages=1)

                        if not sales:
                            continue

                        aliases = {"PSA": ["PSA"], "BGS": ["BGS", "BECKETT", "BKT"], "CGC": ["CGC"]}
                        graded_sales = [s for s in sales if any(a in s["title"].upper() for a in aliases.get(grader, [grader]))]

                        new_count = 0
                        for sale in graded_sales:
                            if is_blacklisted(sale["title"]):
                                continue
                            try:
                                c.execute("""INSERT OR IGNORE INTO sales_history
                                    (card_name, title, sold_price, sold_date, condition,
                                     listing_type, url, scraped_at, confidence_score,
                                     confidence_flags, seller_feedback, bid_count, best_offer)
                                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                    (name, sale["title"], sale["sold_price"], sale["sold_date"],
                                     sale["condition"], sale["listing_type"], sale["url"], scraped_at,
                                     sale["confidence_score"], sale["confidence_flags"],
                                     sale["seller_feedback"], sale["bid_count"],
                                     1 if sale["best_offer"] else 0))
                                if c.rowcount > 0:
                                    new_count += 1
                                    total_new += 1
                            except sqlite3.IntegrityError:
                                pass

                        if new_count > 0:
                            print(f"      ✅  {new_count} new graded listings")
                        conn.commit()
                        time.sleep(random.uniform(2, 3))
        finally:
            driver.quit()
            conn.commit()
            conn.close()

        try:
            from grade_parser import update_all_grades, init_grade_columns
            init_grade_columns()
            update_all_grades()
        except Exception as e:
            print(f"  ⚠️  Grade parse error: {e}")

    print(f"\n✅  Done! {total_new} new records, {total_filtered} filtered out\n")
