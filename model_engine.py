"""
Pokemon Card Model Engine
==========================
Reads latest prices from SQLite, runs the regression model,
and stores predictions back to the database.

Called by the dashboard or can be run standalone.
"""

import sqlite3
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import MinMaxScaler
from datetime import datetime

DB_PATH = "pokemon_cards.db"

WEIGHT_CHARACTER = 0.45
WEIGHT_ARTWORK   = 0.45
WEIGHT_TRENDS    = 0.10


def get_latest_prices() -> pd.DataFrame:
    """Get the most recent price observation for each card, joined with metadata."""
    conn = sqlite3.connect(DB_PATH)

    query = """
        SELECT c.*, ph.median_price as market_price_usd, ph.timestamp as last_updated,
               ph.num_sales, ph.min_price, ph.max_price
        FROM cards c
        LEFT JOIN price_history ph ON c.card_name = ph.card_name
        WHERE ph.timestamp = (
            SELECT MAX(ph2.timestamp)
            FROM price_history ph2
            WHERE ph2.card_name = c.card_name
        )
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_price_history(card_name: str = None, days: int = 30) -> pd.DataFrame:
    """Get price history for one or all cards."""
    conn = sqlite3.connect(DB_PATH)

    if card_name:
        query = """
            SELECT card_name, timestamp, median_price, avg_price, min_price, max_price, num_sales
            FROM price_history
            WHERE card_name = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """
        df = pd.read_sql_query(query, conn, params=(card_name, days * 4))
    else:
        query = """
            SELECT card_name, timestamp, median_price, avg_price, min_price, max_price, num_sales
            FROM price_history
            ORDER BY timestamp DESC
        """
        df = pd.read_sql_query(query, conn)

    conn.close()
    return df


def run_model() -> dict:
    """Run the full pricing model and return results."""
    df = get_latest_prices()

    if df.empty or len(df) < 3:
        return {"error": "Not enough data. Need at least 3 cards with price data."}

    # ── Pull cost ──
    df["packs_to_pull"] = df["pull_rate_1_in_x"] * df["cards_in_rarity_tier"]
    df["pull_cost_usd"] = df["packs_to_pull"] * df["pack_price_usd"]

    # ── Desirability ──
    scaler = MinMaxScaler(feature_range=(1, 10))

    max_rank = df["character_premium_rank"].max()
    df["char_score"] = max_rank - df["character_premium_rank"] + 1
    if df["char_score"].nunique() > 1:
        df["char_score"] = scaler.fit_transform(df[["char_score"]])
    else:
        df["char_score"] = 5.5

    df["art_score"] = df["artwork_hype_score"]

    if df["google_trends_score"].nunique() > 1:
        df["trends_score"] = scaler.fit_transform(df[["google_trends_score"]])
    else:
        df["trends_score"] = 5.5

    df["desirability"] = (
        WEIGHT_CHARACTER * df["char_score"]
        + WEIGHT_ARTWORK  * df["art_score"]
        + WEIGHT_TRENDS   * df["trends_score"]
    )

    # ── Normalize to 1-10 ──
    if df["pull_cost_usd"].nunique() > 1:
        df["pull_cost_score"] = scaler.fit_transform(df[["pull_cost_usd"]])
    else:
        df["pull_cost_score"] = 5.5

    if df["desirability"].nunique() > 1:
        df["desirability_score"] = scaler.fit_transform(df[["desirability"]])
    else:
        df["desirability_score"] = 5.5

    # ── Regression ──
    X = df[["pull_cost_score", "desirability_score"]].values
    y = np.log(df["market_price_usd"].values)

    model = LinearRegression()
    model.fit(X, y)

    y_pred_log = model.predict(X)
    df["predicted_price"] = np.exp(y_pred_log)
    df["residual_pct"] = ((df["market_price_usd"] - df["predicted_price"]) / df["predicted_price"]) * 100

    ss_res = np.sum((y - y_pred_log) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    pull_cost_impact = (np.exp(model.coef_[0]) - 1) * 100
    desirability_impact = (np.exp(model.coef_[1]) - 1) * 100

    # ── Store predictions ──
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = datetime.now().isoformat()
    for _, row in df.iterrows():
        c.execute("""
            INSERT INTO predictions
            (card_name, timestamp, market_price, predicted_price, residual_pct,
             pull_cost_score, desirability_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            row["card_name"], timestamp, row["market_price_usd"],
            row["predicted_price"], row["residual_pct"],
            row["pull_cost_score"], row["desirability_score"]
        ))
    conn.commit()
    conn.close()

    # ── Build results ──
    cards = []
    for _, row in df.iterrows():
        status = "overvalued" if row["residual_pct"] > 20 else "undervalued" if row["residual_pct"] < -20 else "fair"
        cards.append({
            "card_name": row["card_name"],
            "set_name": row["set_name"],
            "pokemon": row["pokemon"],
            "market_price": round(row["market_price_usd"], 2),
            "predicted_price": round(row["predicted_price"], 2),
            "residual_pct": round(row["residual_pct"], 1),
            "status": status,
            "pull_cost_score": round(row["pull_cost_score"], 2),
            "desirability_score": round(row["desirability_score"], 2),
            "last_updated": row.get("last_updated", ""),
            "num_sales": int(row.get("num_sales", 0)),
        })

    return {
        "r_squared": round(r_squared, 3),
        "pull_cost_impact": round(pull_cost_impact, 1),
        "desirability_impact": round(desirability_impact, 1),
        "num_cards": len(df),
        "timestamp": timestamp,
        "cards": sorted(cards, key=lambda x: x["residual_pct"], reverse=True),
    }


if __name__ == "__main__":
    results = run_model()
    if "error" in results:
        print(f"❌  {results['error']}")
    else:
        print(f"\n📊  Model Results (R² = {results['r_squared']})")
        print(f"   Pull cost impact: +{results['pull_cost_impact']}% per point")
        print(f"   Desirability impact: +{results['desirability_impact']}% per point\n")
        for card in results["cards"]:
            print(f"   {card['card_name']:<30} ${card['market_price']:>8.2f}  →  ${card['predicted_price']:>8.2f}  ({card['residual_pct']:+.1f}%)  {card['status'].upper()}")
