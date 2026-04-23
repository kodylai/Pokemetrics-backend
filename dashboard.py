"""
Pokemon Card Dashboard Server
===============================
Local web dashboard with two views:
  1. Price Model — regression predictions, over/undervalued
  2. Market Dynamics — demand pressure, supply saturation, listing flow

Run: python dashboard.py
Then open: http://localhost:5000
"""

import sqlite3
import json
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
from model_engine import run_model, get_price_history, DB_PATH
from market_collector import get_all_dynamics, get_listing_history
from sales_scraper import get_sales_history, get_sales_summary, get_price_over_time
from grade_parser import get_grade_breakdown, get_all_grade_breakdowns, init_grade_columns, update_all_grades
from fetch_images import get_all_card_images
from portfolio import (
    get_portfolios, create_portfolio, delete_portfolio, rename_portfolio,
    add_card, update_card, remove_card, get_portfolio_cards,
    valuate_portfolio, take_snapshot, get_portfolio_history,
    init_portfolio_tables
)

app = Flask(__name__)
CORS(app)

# Initialize tables on startup
init_portfolio_tables()
init_grade_columns()
update_all_grades()


@app.route("/")
def index():
    return send_file("dashboard.html")


# ── PRICE MODEL API ──────────────────────────────────────────────────────────

@app.route("/api/model")
def api_model():
    results = run_model()
    return jsonify(results)


@app.route("/api/history/<card_name>")
def api_history(card_name):
    df = get_price_history(card_name)
    if df.empty:
        return jsonify([])
    return jsonify(df.to_dict(orient="records"))


@app.route("/api/history")
def api_all_history():
    df = get_price_history()
    if df.empty:
        return jsonify([])
    return jsonify(df.to_dict(orient="records"))


# ── MARKET DYNAMICS API ──────────────────────────────────────────────────────

@app.route("/api/dynamics")
def api_dynamics():
    results = get_all_dynamics()
    return jsonify(results)


@app.route("/api/listings")
def api_listings():
    card_name = request.args.get("card")
    results = get_listing_history(card_name)
    return jsonify(results)


@app.route("/api/listings/<card_name>")
def api_card_listings(card_name):
    results = get_listing_history(card_name)
    return jsonify(results)


@app.route("/api/cards")
def api_cards():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM cards")
    cards = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(cards)


@app.route("/api/images")
def api_images():
    """Get all card image URLs from the database."""
    return jsonify(get_all_card_images())


# ── SALES HISTORY API ────────────────────────────────────────────────────────
# Add ?verified=true to any endpoint to filter to high-confidence sales only

@app.route("/api/sales")
def api_sales():
    """Get all sales history. ?card=name&verified=true"""
    card_name = request.args.get("card")
    verified = request.args.get("verified", "").lower() == "true"
    results = get_sales_history(card_name, verified_only=verified)
    return jsonify(results)


@app.route("/api/sales/<card_name>")
def api_card_sales(card_name):
    """Get sales history for a specific card. ?verified=true"""
    verified = request.args.get("verified", "").lower() == "true"
    results = get_sales_history(card_name, verified_only=verified)
    return jsonify(results)


@app.route("/api/sales/summary")
def api_sales_summary():
    """Get summary stats. ?verified=true"""
    verified = request.args.get("verified", "").lower() == "true"
    results = get_sales_summary(verified_only=verified)
    return jsonify(results)


@app.route("/api/sales/trend/<card_name>")
def api_sales_trend(card_name):
    """Get daily price trend. ?verified=true"""
    verified = request.args.get("verified", "").lower() == "true"
    results = get_price_over_time(card_name, verified_only=verified)
    return jsonify(results)


# ── GRADE BREAKDOWN API ─────────────────────────────────────────────────────

@app.route("/api/grades/<card_name>")
def api_grade_breakdown(card_name):
    """Get price breakdown by grade (PSA 10, PSA 9, BGS 9.5, Raw, etc.)"""
    results = get_grade_breakdown(card_name)
    return jsonify(results)


@app.route("/api/grades")
def api_all_grades():
    """Get grade breakdowns for all cards."""
    results = get_all_grade_breakdowns()
    return jsonify(results)


# ── PORTFOLIO API ────────────────────────────────────────────────────────────

@app.route("/api/portfolios", methods=["GET"])
def api_get_portfolios():
    """List all portfolios."""
    return jsonify(get_portfolios())


@app.route("/api/portfolios", methods=["POST"])
def api_create_portfolio():
    """Create a new portfolio. Body: {name, description}"""
    data = request.get_json()
    result = create_portfolio(data.get("name", ""), data.get("description", ""))
    return jsonify(result)


@app.route("/api/portfolios/<int:pid>", methods=["DELETE"])
def api_delete_portfolio(pid):
    """Delete a portfolio."""
    return jsonify(delete_portfolio(pid))


@app.route("/api/portfolios/<int:pid>", methods=["PUT"])
def api_rename_portfolio(pid):
    """Rename a portfolio. Body: {name, description}"""
    data = request.get_json()
    result = rename_portfolio(pid, data.get("name", ""), data.get("description"))
    return jsonify(result)


@app.route("/api/portfolios/<int:pid>/cards", methods=["GET"])
def api_get_cards(pid):
    """Get all cards in a portfolio."""
    return jsonify(get_portfolio_cards(pid))


@app.route("/api/portfolios/<int:pid>/cards", methods=["POST"])
def api_add_card(pid):
    """Add a card. Body: {card_name, set_name, pokemon, quantity, purchase_price, purchase_date, condition, notes}"""
    data = request.get_json()
    result = add_card(
        portfolio_id=pid,
        card_name=data.get("card_name", ""),
        set_name=data.get("set_name", ""),
        pokemon=data.get("pokemon", ""),
        quantity=data.get("quantity", 1),
        purchase_price=data.get("purchase_price", 0),
        purchase_date=data.get("purchase_date", ""),
        condition=data.get("condition", "Near Mint"),
        notes=data.get("notes", ""),
    )
    return jsonify(result)


@app.route("/api/portfolios/cards/<int:card_id>", methods=["PUT"])
def api_update_card(card_id):
    """Update a card. Body: any card fields to update."""
    data = request.get_json()
    result = update_card(card_id, **data)
    return jsonify(result)


@app.route("/api/portfolios/cards/<int:card_id>", methods=["DELETE"])
def api_remove_card(card_id):
    """Remove a card from portfolio."""
    return jsonify(remove_card(card_id))


@app.route("/api/portfolios/<int:pid>/value", methods=["GET"])
def api_portfolio_value(pid):
    """Get full portfolio valuation with per-card breakdown."""
    return jsonify(valuate_portfolio(pid))


@app.route("/api/portfolios/<int:pid>/snapshot", methods=["POST"])
def api_take_snapshot(pid):
    """Take a point-in-time snapshot of portfolio value."""
    return jsonify(take_snapshot(pid))


@app.route("/api/portfolios/<int:pid>/history", methods=["GET"])
def api_portfolio_history(pid):
    """Get portfolio value history for charting."""
    return jsonify(get_portfolio_history(pid))


if __name__ == "__main__":
    print("\n🎴  Pokémon Card Price Dashboard")
    print("─" * 40)
    print("  Open in browser: http://localhost:5000")
    print("  Press Ctrl+C to stop\n")
    app.run(debug=True, port=5000)
