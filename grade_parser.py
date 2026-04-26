"""
Grade Parser
=============
Extracts grading information from eBay listing titles.
Parses PSA, BGS, CGC, AGS, and identifies Raw cards.

Usage:
  from grade_parser import parse_grade, update_all_grades

  grade = parse_grade("Charizard Gold Star PSA 10 EX Dragon Frontiers")
  # Returns: {"grader": "PSA", "grade": "10", "label": "PSA 10", "category": "graded"}

  update_all_grades()  # Retroactively parse grades for all existing sales
"""

import re
import sqlite3

DB_PATH = "pokemon_cards.db"


def parse_grade(title: str) -> dict:
    """
    Parse grading info from an eBay listing title.

    Returns:
      {
        "grader": "PSA" | "BGS" | "CGC" | "AGS" | "Raw",
        "grade": "10" | "9.5" | "9" | etc.,
        "label": "PSA 10" | "BGS 9.5" | "Raw" | etc.,
        "category": "graded" | "raw"
      }
    """
    if not title:
        return {"grader": "Raw", "grade": "", "label": "Raw", "category": "raw"}

    upper = title.upper()

    # ── PSA grades ──
    psa_match = re.search(r'\bPSA\s*(\d+(?:\.\d+)?)', upper)
    if psa_match:
        grade = psa_match.group(1)
        return {"grader": "PSA", "grade": grade, "label": f"PSA {grade}", "category": "graded"}

    # ── BGS / Beckett grades ──
    bgs_match = re.search(r'\b(?:BGS|BECKETT|BKT)\s*(\d+(?:\.\d+)?)', upper)
    if bgs_match:
        grade = bgs_match.group(1)
        return {"grader": "BGS", "grade": grade, "label": f"BGS {grade}", "category": "graded"}

    # Black Label
    if "BLACK LABEL" in upper or "BL 10" in upper:
        return {"grader": "BGS", "grade": "10", "label": "BGS 10 Black Label", "category": "graded"}

    # ── CGC grades ──
    cgc_match = re.search(r'\bCGC\s*(\d+(?:\.\d+)?)', upper)
    if cgc_match:
        grade = cgc_match.group(1)
        return {"grader": "CGC", "grade": grade, "label": f"CGC {grade}", "category": "graded"}

    # ── AGS grades ──
    ags_match = re.search(r'\bAGS\s*(\d+(?:\.\d+)?)', upper)
    if ags_match:
        grade = ags_match.group(1)
        return {"grader": "AGS", "grade": grade, "label": f"AGS {grade}", "category": "graded"}

    # ── ACE grades ──
    ace_match = re.search(r'\bACE\s*(\d+(?:\.\d+)?)', upper)
    if ace_match:
        grade = ace_match.group(1)
        return {"grader": "ACE", "grade": grade, "label": f"ACE {grade}", "category": "graded"}

    # ── Generic "GRADED" mention ──
    if re.search(r'\b(?:GRADED|SLAB|SLABBED)\b', upper):
        return {"grader": "Unknown", "grade": "", "label": "Graded (unknown)", "category": "graded"}

    # ── GEM MINT without specific grader ──
    if "GEM MINT" in upper or "MINT 10" in upper:
        return {"grader": "Unknown", "grade": "10", "label": "Gem Mint", "category": "graded"}

    # ── Raw / Ungraded ──
    return {"grader": "Raw", "grade": "", "label": "Raw", "category": "raw"}


def init_grade_columns():
    """Add grade columns to sales_history if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("PRAGMA table_info(sales_history)")
    columns = [row[1] for row in c.fetchall()]

    added = False
    for col, default in [("grader", "Raw"), ("grade", ""), ("grade_label", "Raw"), ("grade_category", "raw")]:
        if col not in columns:
            c.execute(f"ALTER TABLE sales_history ADD COLUMN {col} TEXT DEFAULT '{default}'")
            added = True

    if added:
        conn.commit()
        print("  ✅  Grade columns added")

    conn.close()


def update_all_grades():
    """Parse grades for ALL sales records."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT id, title FROM sales_history")
    rows = c.fetchall()

    graded = 0
    for row_id, title in rows:
        result = parse_grade(title)
        c.execute("""
            UPDATE sales_history
            SET grader = ?, grade = ?, grade_label = ?, grade_category = ?
            WHERE id = ?
        """, (result["grader"], result["grade"], result["label"], result["category"], row_id))
        if result["category"] == "graded":
            graded += 1

    conn.commit()
    conn.close()
    print(f"✅  Parsed grades for {len(rows)} sales records ({graded} graded, {len(rows) - graded} raw)")


def get_grade_breakdown(card_name: str) -> list:
    """Get price breakdown by grade for a specific card."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT
            grade_label,
            grade_category,
            grader,
            grade,
            COUNT(*) as total_sales,
            ROUND(AVG(sold_price), 2) as avg_price,
            ROUND(MIN(sold_price), 2) as min_price,
            ROUND(MAX(sold_price), 2) as max_price,
            ROUND(AVG(confidence_score), 1) as avg_confidence,
            MAX(sold_date) as latest_sale
        FROM sales_history
        WHERE card_name = ? AND sold_price > 0
        GROUP BY grade_label
        ORDER BY
            CASE grade_category WHEN 'graded' THEN 0 ELSE 1 END,
            CASE grader
                WHEN 'PSA' THEN 0
                WHEN 'BGS' THEN 1
                WHEN 'CGC' THEN 2
                ELSE 3
            END,
            CAST(grade AS REAL) DESC
    """, (card_name,))

    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def get_all_grade_breakdowns() -> dict:
    """Get grade breakdowns for all cards."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT DISTINCT card_name FROM sales_history WHERE sold_price > 0")
    card_names = [row[0] for row in c.fetchall()]
    conn.close()

    result = {}
    for name in card_names:
        result[name] = get_grade_breakdown(name)
    return result


# ── ENTRY POINT ──
if __name__ == "__main__":
    init_grade_columns()
    update_all_grades()

    # Show a sample breakdown
    import sys
    card = sys.argv[1] if len(sys.argv) > 1 else "Charizard Gold Star"
    print(f"\n📊  Grade breakdown for: {card}")
    print("─" * 60)

    breakdown = get_grade_breakdown(card)
    if not breakdown:
        print("  No data found")
    else:
        for g in breakdown:
            print(f"  {g['grade_label']:<25} {g['total_sales']:>3} sales  "
                  f"Avg: ${g['avg_price']:>10,.2f}  "
                  f"Range: ${g['min_price']:,.2f}-${g['max_price']:,.2f}")
