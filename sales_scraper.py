"""
eBay Sold Listings Scraper — Selenium + Confidence Scoring
============================================================
Uses a real Chrome browser to scrape eBay sold listings,
bypassing anti-bot detection that blocks raw HTTP requests.

CONFIDENCE SCORING:
  HIGH (80-100):  Buy It Now, reputable sellers, normal price
  MEDIUM (50-79): Best Offer accepted, reasonable price
  LOW (0-49):     Auctions (high non-payment risk), outliers

Usage:
  python sales_scraper.py                  # Scrape all cards
  python sales_scraper.py --verified       # Only high-confidence sales
  python sales_scraper.py --card "Umbreon" # Scrape one card
  python sales_scraper.py --demo           # Dry run
  python sales_scraper.py --headless       # No browser window (background)

Requirements:
  pip install selenium webdriver-manager beautifulsoup4
"""

import os
import sys
import re
import json
import time
import sqlite3
import random
import math
import urllib.parse
from datetime import datetime

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

DB_PATH = "pokemon_cards.db"

# ── Cards to track ──
CARDS_TO_SCRAPE = [
      # ── BASE SET ──
    {
        "card_name": "Alakazam 1/165 Expedition Base Set",
        "search_query": "\"Alakazam\" 1/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Alakazam 1/165 Base Set 2",
        "search_query": "\"Alakazam\" 1/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Alakazam 1/165 Base",
        "search_query": "\"Alakazam\" 1/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Blastoise 2/165 Base Set 2",
        "search_query": "\"Blastoise\" 2/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Blastoise 2/165 Base",
        "search_query": "\"Blastoise\" 2/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Ampharos 2/165 Expedition Base Set",
        "search_query": "\"Ampharos\" 2/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Arbok 3/165 Expedition Base Set",
        "search_query": "\"Arbok\" 3/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Chansey 3/165 Base Set 2",
        "search_query": "\"Chansey\" 3/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Chansey 3/165 Base",
        "search_query": "\"Chansey\" 3/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Charizard 4/165 Base Set 2",
        "search_query": "\"Charizard\" 4/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Blastoise 4/165 Expedition Base Set",
        "search_query": "\"Blastoise\" 4/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Charizard 4/165 Base",
        "search_query": "\"Charizard\" 4/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Clefairy 5/165 Base",
        "search_query": "\"Clefairy\" 5/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Clefable 5/165 Base Set 2",
        "search_query": "\"Clefable\" 5/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Butterfree 5/165 Expedition Base Set",
        "search_query": "\"Butterfree\" 5/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Charizard 6/165 Expedition Base Set",
        "search_query": "\"Charizard\" 6/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Clefairy 6/165 Base Set 2",
        "search_query": "\"Clefairy\" 6/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Gyarados 6/165 Base",
        "search_query": "\"Gyarados\" 6/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Hitmonchan 7/165 Base",
        "search_query": "\"Hitmonchan\" 7/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Clefable 7/165 Expedition Base Set",
        "search_query": "\"Clefable\" 7/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Gyarados 7/165 Base Set 2",
        "search_query": "\"Gyarados\" 7/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Cloyster 8/165 Expedition Base Set",
        "search_query": "\"Cloyster\" 8/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Hitmonchan 8/165 Base Set 2",
        "search_query": "\"Hitmonchan\" 8/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Machamp 8/165 Base",
        "search_query": "\"Machamp\" 8/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Dragonite 9/165 Expedition Base Set",
        "search_query": "\"Dragonite\" 9/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Magneton 9/165 Base",
        "search_query": "\"Magneton\" 9/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Magneton 9/165 Base Set 2",
        "search_query": "\"Magneton\" 9/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Mewtwo 10/165 Base Set 2",
        "search_query": "\"Mewtwo\" 10/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Mewtwo 10/165 Base",
        "search_query": "\"Mewtwo\" 10/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Dugtrio 10/165 Expedition Base Set",
        "search_query": "\"Dugtrio\" 10/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Nidoking 11/165 Base Set 2",
        "search_query": "\"Nidoking\" 11/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Fearow 11/165 Expedition Base Set",
        "search_query": "\"Fearow\" 11/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Nidoking 11/165 Base",
        "search_query": "\"Nidoking\" 11/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Nidoqueen 12/165 Base Set 2",
        "search_query": "\"Nidoqueen\" 12/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Feraligatr 12/165 Expedition Base Set",
        "search_query": "\"Feraligatr\" 12/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Ninetales 12/165 Base",
        "search_query": "\"Ninetales\" 12/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Poliwrath 13/165 Base",
        "search_query": "\"Poliwrath\" 13/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Gengar 13/165 Expedition Base Set",
        "search_query": "\"Gengar\" 13/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Ninetales 13/165 Base Set 2",
        "search_query": "\"Ninetales\" 13/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Raichu 14/165 Base",
        "search_query": "\"Raichu\" 14/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Golem 14/165 Expedition Base Set",
        "search_query": "\"Golem\" 14/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Pidgeot 14/165 Base Set 2",
        "search_query": "\"Pidgeot\" 14/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Poliwrath 15/165 Base Set 2",
        "search_query": "\"Poliwrath\" 15/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Venusaur 15/165 Base",
        "search_query": "\"Venusaur\" 15/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Kingler 15/165 Expedition Base Set",
        "search_query": "\"Kingler\" 15/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Machamp 16/165 Expedition Base Set",
        "search_query": "\"Machamp\" 16/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Raichu 16/165 Base Set 2",
        "search_query": "\"Raichu\" 16/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Zapdos 16/165 Base",
        "search_query": "\"Zapdos\" 16/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Magby 17/165 Expedition Base Set",
        "search_query": "\"Magby\" 17/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Scyther 17/165 Base Set 2",
        "search_query": "\"Scyther\" 17/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Meganium 18/165 Expedition Base Set",
        "search_query": "\"Meganium\" 18/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Venusaur 18/165 Base Set 2",
        "search_query": "\"Venusaur\" 18/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Mew 19/165 Expedition Base Set",
        "search_query": "\"Mew\" 19/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Wigglytuff 19/165 Base Set 2",
        "search_query": "\"Wigglytuff\" 19/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Mewtwo 20/165 Expedition Base Set",
        "search_query": "\"Mewtwo\" 20/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Zapdos 20/165 Base Set 2",
        "search_query": "\"Zapdos\" 20/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Ninetales 21/165 Expedition Base Set",
        "search_query": "\"Ninetales\" 21/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Pichu 22/165 Expedition Base Set",
        "search_query": "\"Pichu\" 22/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Pidgeot 23/165 Expedition Base Set",
        "search_query": "\"Pidgeot\" 23/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Poliwrath 24/165 Expedition Base Set",
        "search_query": "\"Poliwrath\" 24/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Raichu 25/165 Expedition Base Set",
        "search_query": "\"Raichu\" 25/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Rapidash 26/165 Expedition Base Set",
        "search_query": "\"Rapidash\" 26/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Skarmory 27/165 Expedition Base Set",
        "search_query": "\"Skarmory\" 27/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Typhlosion 28/165 Expedition Base Set",
        "search_query": "\"Typhlosion\" 28/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Tyranitar 29/165 Expedition Base Set",
        "search_query": "\"Tyranitar\" 29/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Venusaur 30/165 Expedition Base Set",
        "search_query": "\"Venusaur\" 30/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Vileplume 31/165 Expedition Base Set",
        "search_query": "\"Vileplume\" 31/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Weezing 32/165 Expedition Base Set",
        "search_query": "\"Weezing\" 32/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Double Colorless Energy 96/165 Base",
        "search_query": "\"Double Colorless Energy\" 96/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Fighting Energy 97/165 Base",
        "search_query": "\"Fighting Energy\" 97/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Fire Energy 98/165 Base",
        "search_query": "\"Fire Energy\" 98/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Grass Energy 99/165 Base",
        "search_query": "\"Grass Energy\" 99/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Lightning Energy 100/165 Base",
        "search_query": "\"Lightning Energy\" 100/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Psychic Energy 101/165 Base",
        "search_query": "\"Psychic Energy\" 101/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Water Energy 102/165 Base",
        "search_query": "\"Water Energy\" 102/165 \"Base\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Double Colorless Energy 124/165 Base Set 2",
        "search_query": "\"Double Colorless Energy\" 124/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Fighting Energy 125/165 Base Set 2",
        "search_query": "\"Fighting Energy\" 125/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Fire Energy 126/165 Base Set 2",
        "search_query": "\"Fire Energy\" 126/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Grass Energy 127/165 Base Set 2",
        "search_query": "\"Grass Energy\" 127/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Lightning Energy 128/165 Base Set 2",
        "search_query": "\"Lightning Energy\" 128/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Psychic Energy 129/165 Base Set 2",
        "search_query": "\"Psychic Energy\" 129/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Water Energy 130/165 Base Set 2",
        "search_query": "\"Water Energy\" 130/165 \"Base Set 2\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Darkness Energy 158/165 Expedition Base Set",
        "search_query": "\"Darkness Energy\" 158/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Metal Energy 159/165 Expedition Base Set",
        "search_query": "\"Metal Energy\" 159/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Fighting Energy 160/165 Expedition Base Set",
        "search_query": "\"Fighting Energy\" 160/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Fire Energy 161/165 Expedition Base Set",
        "search_query": "\"Fire Energy\" 161/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Grass Energy 162/165 Expedition Base Set",
        "search_query": "\"Grass Energy\" 162/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Lightning Energy 163/165 Expedition Base Set",
        "search_query": "\"Lightning Energy\" 163/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Psychic Energy 164/165 Expedition Base Set",
        "search_query": "\"Psychic Energy\" 164/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },
    {
        "card_name": "Water Energy 165/165 Expedition Base Set",
        "search_query": "\"Water Energy\" 165/165 \"Expedition Base Set\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1.0,
        "category": "base_set",
    },

    # ── EVOLVING SKIES ──
    {
        "card_name": "Leafeon VMAX 8/237 Evolving Skies",
        "search_query": "\"Leafeon VMAX\" 8/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Trevenant VMAX 14/237 Evolving Skies",
        "search_query": "\"Trevenant VMAX\" 14/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Flareon VMAX 18/237 Evolving Skies",
        "search_query": "\"Flareon VMAX\" 18/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Gyarados VMAX 29/237 Evolving Skies",
        "search_query": "\"Gyarados VMAX\" 29/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Vaporeon VMAX 30/237 Evolving Skies",
        "search_query": "\"Vaporeon VMAX\" 30/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Glaceon VMAX 41/237 Evolving Skies",
        "search_query": "\"Glaceon VMAX\" 41/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Jolteon VMAX 51/237 Evolving Skies",
        "search_query": "\"Jolteon VMAX\" 51/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Dracozolt VMAX 59/237 Evolving Skies",
        "search_query": "\"Dracozolt VMAX\" 59/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Espeon VMAX 65/237 Evolving Skies",
        "search_query": "\"Espeon VMAX\" 65/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Sylveon VMAX 75/237 Evolving Skies",
        "search_query": "\"Sylveon VMAX\" 75/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Lycanroc VMAX 92/237 Evolving Skies",
        "search_query": "\"Lycanroc VMAX\" 92/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Umbreon VMAX 95/237 Evolving Skies",
        "search_query": "\"Umbreon VMAX\" 95/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Garbodor VMAX 101/237 Evolving Skies",
        "search_query": "\"Garbodor VMAX\" 101/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Rayquaza VMAX 111/237 Evolving Skies",
        "search_query": "\"Rayquaza VMAX\" 111/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Duraludon VMAX 123/237 Evolving Skies",
        "search_query": "\"Duraludon VMAX\" 123/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Leafeon V 166/237 Evolving Skies",
        "search_query": "\"Leafeon V\" 166/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Leafeon V 167/237 Evolving Skies",
        "search_query": "\"Leafeon V\" 167/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Trevenant V 168/237 Evolving Skies",
        "search_query": "\"Trevenant V\" 168/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Flareon V 169/237 Evolving Skies",
        "search_query": "\"Flareon V\" 169/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Volcarona V 170/237 Evolving Skies",
        "search_query": "\"Volcarona V\" 170/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Gyarados V 171/237 Evolving Skies",
        "search_query": "\"Gyarados V\" 171/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Vaporeon V 172/237 Evolving Skies",
        "search_query": "\"Vaporeon V\" 172/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Suicune V 173/237 Evolving Skies",
        "search_query": "\"Suicune V\" 173/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Glaceon V 174/237 Evolving Skies",
        "search_query": "\"Glaceon V\" 174/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Glaceon V 175/237 Evolving Skies",
        "search_query": "\"Glaceon V\" 175/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Arctovish V 176/237 Evolving Skies",
        "search_query": "\"Arctovish V\" 176/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Jolteon V 177/237 Evolving Skies",
        "search_query": "\"Jolteon V\" 177/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Dracozolt V 178/237 Evolving Skies",
        "search_query": "\"Dracozolt V\" 178/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Espeon V 179/237 Evolving Skies",
        "search_query": "\"Espeon V\" 179/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Espeon V 180/237 Evolving Skies",
        "search_query": "\"Espeon V\" 180/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Golurk V 181/237 Evolving Skies",
        "search_query": "\"Golurk V\" 181/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Golurk V 182/237 Evolving Skies",
        "search_query": "\"Golurk V\" 182/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Sylveon V 183/237 Evolving Skies",
        "search_query": "\"Sylveon V\" 183/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Sylveon V 184/237 Evolving Skies",
        "search_query": "\"Sylveon V\" 184/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Medicham V 185/237 Evolving Skies",
        "search_query": "\"Medicham V\" 185/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Medicham V 186/237 Evolving Skies",
        "search_query": "\"Medicham V\" 186/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Lycanroc V 187/237 Evolving Skies",
        "search_query": "\"Lycanroc V\" 187/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Umbreon V 188/237 Evolving Skies",
        "search_query": "\"Umbreon V\" 188/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Umbreon V 189/237 Evolving Skies",
        "search_query": "\"Umbreon V\" 189/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Garbodor V 190/237 Evolving Skies",
        "search_query": "\"Garbodor V\" 190/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Dragonite V 191/237 Evolving Skies",
        "search_query": "\"Dragonite V\" 191/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Dragonite V 192/237 Evolving Skies",
        "search_query": "\"Dragonite V\" 192/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Rayquaza V 193/237 Evolving Skies",
        "search_query": "\"Rayquaza V\" 193/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Rayquaza V 194/237 Evolving Skies",
        "search_query": "\"Rayquaza V\" 194/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Noivern V 195/237 Evolving Skies",
        "search_query": "\"Noivern V\" 195/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Noivern V 196/237 Evolving Skies",
        "search_query": "\"Noivern V\" 196/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Duraludon V 197/237 Evolving Skies",
        "search_query": "\"Duraludon V\" 197/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Duraludon V 198/237 Evolving Skies",
        "search_query": "\"Duraludon V\" 198/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Aroma Lady 199/237 Evolving Skies",
        "search_query": "\"Aroma Lady\" 199/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Copycat 200/237 Evolving Skies",
        "search_query": "\"Copycat\" 200/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Gordie 201/237 Evolving Skies",
        "search_query": "\"Gordie\" 201/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Raihan 202/237 Evolving Skies",
        "search_query": "\"Raihan\" 202/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Zinnia's Resolve 203/237 Evolving Skies",
        "search_query": "\"Zinnia's Resolve\" 203/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Leafeon VMAX 204/237 Evolving Skies",
        "search_query": "\"Leafeon VMAX\" 204/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Leafeon VMAX 205/237 Evolving Skies",
        "search_query": "\"Leafeon VMAX\" 205/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Trevenant VMAX 206/237 Evolving Skies",
        "search_query": "\"Trevenant VMAX\" 206/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Gyarados VMAX 207/237 Evolving Skies",
        "search_query": "\"Gyarados VMAX\" 207/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Glaceon VMAX 208/237 Evolving Skies",
        "search_query": "\"Glaceon VMAX\" 208/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Glaceon VMAX 209/237 Evolving Skies",
        "search_query": "\"Glaceon VMAX\" 209/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Dracozolt VMAX 210/237 Evolving Skies",
        "search_query": "\"Dracozolt VMAX\" 210/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Sylveon VMAX 211/237 Evolving Skies",
        "search_query": "\"Sylveon VMAX\" 211/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Sylveon VMAX 212/237 Evolving Skies",
        "search_query": "\"Sylveon VMAX\" 212/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Lycanroc VMAX 213/237 Evolving Skies",
        "search_query": "\"Lycanroc VMAX\" 213/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Umbreon VMAX 214/237 Evolving Skies",
        "search_query": "\"Umbreon VMAX\" 214/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Umbreon VMAX 215/237 Evolving Skies",
        "search_query": "\"Umbreon VMAX\" 215/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Garbodor VMAX 216/237 Evolving Skies",
        "search_query": "\"Garbodor VMAX\" 216/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Rayquaza VMAX 217/237 Evolving Skies",
        "search_query": "\"Rayquaza VMAX\" 217/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Rayquaza VMAX 218/237 Evolving Skies",
        "search_query": "\"Rayquaza VMAX\" 218/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Duraludon VMAX 219/237 Evolving Skies",
        "search_query": "\"Duraludon VMAX\" 219/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Duraludon VMAX 220/237 Evolving Skies",
        "search_query": "\"Duraludon VMAX\" 220/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Aroma Lady 221/237 Evolving Skies",
        "search_query": "\"Aroma Lady\" 221/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Copycat 222/237 Evolving Skies",
        "search_query": "\"Copycat\" 222/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Gordie 223/237 Evolving Skies",
        "search_query": "\"Gordie\" 223/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Raihan 224/237 Evolving Skies",
        "search_query": "\"Raihan\" 224/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Zinnia's Resolve 225/237 Evolving Skies",
        "search_query": "\"Zinnia's Resolve\" 225/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Froslass 226/237 Evolving Skies",
        "search_query": "\"Froslass\" 226/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Inteleon 227/237 Evolving Skies",
        "search_query": "\"Inteleon\" 227/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Cresselia 228/237 Evolving Skies",
        "search_query": "\"Cresselia\" 228/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Boost Shake 229/237 Evolving Skies",
        "search_query": "\"Boost Shake\" 229/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Crystal Cave 230/237 Evolving Skies",
        "search_query": "\"Crystal Cave\" 230/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Full Face Guard 231/237 Evolving Skies",
        "search_query": "\"Full Face Guard\" 231/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Stormy Mountains 232/237 Evolving Skies",
        "search_query": "\"Stormy Mountains\" 232/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Toy Catcher 233/237 Evolving Skies",
        "search_query": "\"Toy Catcher\" 233/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Turffield Stadium 234/237 Evolving Skies",
        "search_query": "\"Turffield Stadium\" 234/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Lightning Energy 235/237 Evolving Skies",
        "search_query": "\"Lightning Energy\" 235/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Darkness Energy 236/237 Evolving Skies",
        "search_query": "\"Darkness Energy\" 236/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Metal Energy 237/237 Evolving Skies",
        "search_query": "\"Metal Energy\" 237/237 \"Evolving Skies\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },

    # ── SURGING SPARKS ──
    {
        "card_name": "Durant ex 4/252 Surging Sparks",
        "search_query": "\"Durant ex\" 4/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Ceruledge ex 36/252 Surging Sparks",
        "search_query": "\"Ceruledge ex\" 36/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Scovillain ex 37/252 Surging Sparks",
        "search_query": "\"Scovillain ex\" 37/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Milotic ex 42/252 Surging Sparks",
        "search_query": "\"Milotic ex\" 42/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Black Kyurem ex 48/252 Surging Sparks",
        "search_query": "\"Black Kyurem ex\" 48/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Pikachu ex 57/252 Surging Sparks",
        "search_query": "\"Pikachu ex\" 57/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Kilowattrel ex 68/252 Surging Sparks",
        "search_query": "\"Kilowattrel ex\" 68/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Latias ex 76/252 Surging Sparks",
        "search_query": "\"Latias ex\" 76/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Sylveon ex 86/252 Surging Sparks",
        "search_query": "\"Sylveon ex\" 86/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Palossand ex 91/252 Surging Sparks",
        "search_query": "\"Palossand ex\" 91/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Flygon ex 106/252 Surging Sparks",
        "search_query": "\"Flygon ex\" 106/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Hydreigon ex 119/252 Surging Sparks",
        "search_query": "\"Hydreigon ex\" 119/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Archaludon ex 130/252 Surging Sparks",
        "search_query": "\"Archaludon ex\" 130/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Alolan Exeggutor ex 133/252 Surging Sparks",
        "search_query": "\"Alolan Exeggutor ex\" 133/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Tatsugiri ex 142/252 Surging Sparks",
        "search_query": "\"Tatsugiri ex\" 142/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Slaking ex 147/252 Surging Sparks",
        "search_query": "\"Slaking ex\" 147/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Cyclizar ex 159/252 Surging Sparks",
        "search_query": "\"Cyclizar ex\" 159/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Flamigo ex 160/252 Surging Sparks",
        "search_query": "\"Flamigo ex\" 160/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Amulet of Hope 162/252 Surging Sparks",
        "search_query": "\"Amulet of Hope\" 162/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Brilliant Blender 164/252 Surging Sparks",
        "search_query": "\"Brilliant Blender\" 164/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Energy Search Pro 176/252 Surging Sparks",
        "search_query": "\"Energy Search Pro\" 176/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Megaton Blower 182/252 Surging Sparks",
        "search_query": "\"Megaton Blower\" 182/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Miracle Headset 183/252 Surging Sparks",
        "search_query": "\"Miracle Headset\" 183/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Precious Trolley 185/252 Surging Sparks",
        "search_query": "\"Precious Trolley\" 185/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Scramble Switch 186/252 Surging Sparks",
        "search_query": "\"Scramble Switch\" 186/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Enriching Energy 191/252 Surging Sparks",
        "search_query": "\"Enriching Energy\" 191/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Exeggcute 192/252 Surging Sparks",
        "search_query": "\"Exeggcute\" 192/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Vivillon 193/252 Surging Sparks",
        "search_query": "\"Vivillon\" 193/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Shiinotic 194/252 Surging Sparks",
        "search_query": "\"Shiinotic\" 194/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Castform Sunny Form 195/252 Surging Sparks",
        "search_query": "\"Castform Sunny Form\" 195/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Larvesta 196/252 Surging Sparks",
        "search_query": "\"Larvesta\" 196/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Ceruledge 197/252 Surging Sparks",
        "search_query": "\"Ceruledge\" 197/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Feebas 198/252 Surging Sparks",
        "search_query": "\"Feebas\" 198/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Spheal 199/252 Surging Sparks",
        "search_query": "\"Spheal\" 199/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Bruxish 200/252 Surging Sparks",
        "search_query": "\"Bruxish\" 200/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Cetitan 201/252 Surging Sparks",
        "search_query": "\"Cetitan\" 201/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Stunfisk 202/252 Surging Sparks",
        "search_query": "\"Stunfisk\" 202/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Latios 203/252 Surging Sparks",
        "search_query": "\"Latios\" 203/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Mesprit 204/252 Surging Sparks",
        "search_query": "\"Mesprit\" 204/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Phanpy 205/252 Surging Sparks",
        "search_query": "\"Phanpy\" 205/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Vibrava 206/252 Surging Sparks",
        "search_query": "\"Vibrava\" 206/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Clobbopus 207/252 Surging Sparks",
        "search_query": "\"Clobbopus\" 207/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Alolan Dugtrio 208/252 Surging Sparks",
        "search_query": "\"Alolan Dugtrio\" 208/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Skarmory 209/252 Surging Sparks",
        "search_query": "\"Skarmory\" 209/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Flapple 210/252 Surging Sparks",
        "search_query": "\"Flapple\" 210/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Appletun 211/252 Surging Sparks",
        "search_query": "\"Appletun\" 211/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Slakoth 212/252 Surging Sparks",
        "search_query": "\"Slakoth\" 212/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Kecleon 213/252 Surging Sparks",
        "search_query": "\"Kecleon\" 213/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Braviary 214/252 Surging Sparks",
        "search_query": "\"Braviary\" 214/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Durant ex 215/252 Surging Sparks",
        "search_query": "\"Durant ex\" 215/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Scovillain ex 216/252 Surging Sparks",
        "search_query": "\"Scovillain ex\" 216/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Milotic ex 217/252 Surging Sparks",
        "search_query": "\"Milotic ex\" 217/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Black Kyurem ex 218/252 Surging Sparks",
        "search_query": "\"Black Kyurem ex\" 218/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Pikachu ex 219/252 Surging Sparks",
        "search_query": "\"Pikachu ex\" 219/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Latias ex 220/252 Surging Sparks",
        "search_query": "\"Latias ex\" 220/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Palossand ex 221/252 Surging Sparks",
        "search_query": "\"Palossand ex\" 221/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Flygon ex 222/252 Surging Sparks",
        "search_query": "\"Flygon ex\" 222/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Hydreigon ex 223/252 Surging Sparks",
        "search_query": "\"Hydreigon ex\" 223/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Archaludon ex 224/252 Surging Sparks",
        "search_query": "\"Archaludon ex\" 224/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Alolan Exeggutor ex 225/252 Surging Sparks",
        "search_query": "\"Alolan Exeggutor ex\" 225/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Tatsugiri ex 226/252 Surging Sparks",
        "search_query": "\"Tatsugiri ex\" 226/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Slaking ex 227/252 Surging Sparks",
        "search_query": "\"Slaking ex\" 227/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Cyclizar ex 228/252 Surging Sparks",
        "search_query": "\"Cyclizar ex\" 228/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Clemont's Quick Wit 229/252 Surging Sparks",
        "search_query": "\"Clemont's Quick Wit\" 229/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Cyrano 230/252 Surging Sparks",
        "search_query": "\"Cyrano\" 230/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Drasna 231/252 Surging Sparks",
        "search_query": "\"Drasna\" 231/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Drayton 232/252 Surging Sparks",
        "search_query": "\"Drayton\" 232/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Jasmine's Gaze 233/252 Surging Sparks",
        "search_query": "\"Jasmine's Gaze\" 233/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Lisia's Appeal 234/252 Surging Sparks",
        "search_query": "\"Lisia's Appeal\" 234/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Surfer 235/252 Surging Sparks",
        "search_query": "\"Surfer\" 235/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Durant ex 236/252 Surging Sparks",
        "search_query": "\"Durant ex\" 236/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Milotic ex 237/252 Surging Sparks",
        "search_query": "\"Milotic ex\" 237/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Pikachu ex 238/252 Surging Sparks",
        "search_query": "\"Pikachu ex\" 238/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Latias ex 239/252 Surging Sparks",
        "search_query": "\"Latias ex\" 239/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Hydreigon ex 240/252 Surging Sparks",
        "search_query": "\"Hydreigon ex\" 240/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Archaludon ex 241/252 Surging Sparks",
        "search_query": "\"Archaludon ex\" 241/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Alolan Exeggutor ex 242/252 Surging Sparks",
        "search_query": "\"Alolan Exeggutor ex\" 242/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Clemont's Quick Wit 243/252 Surging Sparks",
        "search_query": "\"Clemont's Quick Wit\" 243/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Drayton 244/252 Surging Sparks",
        "search_query": "\"Drayton\" 244/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Jasmine's Gaze 245/252 Surging Sparks",
        "search_query": "\"Jasmine's Gaze\" 245/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Lisia's Appeal 246/252 Surging Sparks",
        "search_query": "\"Lisia's Appeal\" 246/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Pikachu ex 247/252 Surging Sparks",
        "search_query": "\"Pikachu ex\" 247/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Alolan Exeggutor ex 248/252 Surging Sparks",
        "search_query": "\"Alolan Exeggutor ex\" 248/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Counter Gain 249/252 Surging Sparks",
        "search_query": "\"Counter Gain\" 249/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Gravity Mountain 250/252 Surging Sparks",
        "search_query": "\"Gravity Mountain\" 250/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Night Stretcher 251/252 Surging Sparks",
        "search_query": "\"Night Stretcher\" 251/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Jet Energy 252/252 Surging Sparks",
        "search_query": "\"Jet Energy\" 252/252 \"Surging Sparks\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },

    # ── NEO SHINING ──
    {
        "card_name": "Shining Celebi 106/113 Neo Destiny",
        "search_query": "\"Shining Celebi\" 106/113 \"Neo Destiny\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Charizard 107/113 Neo Destiny",
        "search_query": "\"Shining Charizard\" 107/113 \"Neo Destiny\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Kabutops 108/113 Neo Destiny",
        "search_query": "\"Shining Kabutops\" 108/113 \"Neo Destiny\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Mewtwo 109/113 Neo Destiny",
        "search_query": "\"Shining Mewtwo\" 109/113 \"Neo Destiny\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Noctowl 110/113 Neo Destiny",
        "search_query": "\"Shining Noctowl\" 110/113 \"Neo Destiny\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Raichu 111/113 Neo Destiny",
        "search_query": "\"Shining Raichu\" 111/113 \"Neo Destiny\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Steelix 112/113 Neo Destiny",
        "search_query": "\"Shining Steelix\" 112/113 \"Neo Destiny\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Tyranitar 113/113 Neo Destiny",
        "search_query": "\"Shining Tyranitar\" 113/113 \"Neo Destiny\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Gyarados 65/66 Neo Revelation",
        "search_query": "\"Shining Gyarados\" 65/66 \"Neo Revelation\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Magikarp 66/66 Neo Revelation",
        "search_query": "\"Shining Magikarp\" 66/66 \"Neo Revelation\" -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },

    # ── CRYSTAL CARDS ──
    {
        "card_name": "Crystal Shard 122/122 Skyridge",
        "search_query": "\"Crystal Shard\" 122/122 \"Skyridge\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1,
        "category": "crystal_cards",
    },
    {
        "card_name": "Crystal Energy 146/146 Aquapolis",
        "search_query": "\"Crystal Energy\" 146/146 \"Aquapolis\" -lot -bundle -collection -binder",
        "expected_price": 5,
        "min_price": 1,
        "category": "crystal_cards",
    },

    # ── PHANTASMAL FLAMES ──
    {
        "card_name": "Mega Charizard ex SIR",
        "search_query": "Mega Charizard ex 125 Phantasmal Flames",
        "expected_price": 1000,
        "min_price": 50,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Blastoise ex SIR",
        "search_query": "Mega Blastoise ex SIR Phantasmal Flames",
        "expected_price": 200,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Venusaur ex SIR",
        "search_query": "Mega Venusaur ex SIR Phantasmal Flames",
        "expected_price": 150,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Gengar ex SIR",
        "search_query": "Mega Gengar ex SIR Phantasmal Flames",
        "expected_price": 200,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Rayquaza ex SIR",
        "search_query": "Mega Rayquaza ex SIR Phantasmal Flames",
        "expected_price": 300,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Mewtwo ex SIR",
        "search_query": "Mega Mewtwo ex SIR Phantasmal Flames",
        "expected_price": 250,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Gardevoir ex SIR",
        "search_query": "Mega Gardevoir ex SIR Phantasmal Flames",
        "expected_price": 200,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Lucario ex SIR",
        "search_query": "Mega Lucario ex SIR Phantasmal Flames",
        "expected_price": 150,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Sceptile ex SIR",
        "search_query": "Mega Sceptile ex SIR Phantasmal Flames",
        "expected_price": 100,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Swampert ex SIR",
        "search_query": "Mega Swampert ex SIR Phantasmal Flames",
        "expected_price": 100,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Blaziken ex SIR",
        "search_query": "Mega Blaziken ex SIR Phantasmal Flames",
        "expected_price": 100,
        "min_price": 20,
        "category": "phantasmal_flames",
    },

    # ── ASCENDED HEROES ──
    {
        "card_name": "Pikachu ex SIR",
        "search_query": "Pikachu ex 276 Ascended Heroes",
        "expected_price": 1500,
        "min_price": 100,
        "category": "ascended_heroes",
    },
    {
        "card_name": "Dragonite ex SIR",
        "search_query": "Dragonite ex SIR Ascended Heroes",
        "expected_price": 200,
        "min_price": 20,
        "category": "ascended_heroes",
    },
    {
        "card_name": "Mewtwo ex SIR",
        "search_query": "Mewtwo ex SIR Ascended Heroes",
        "expected_price": 200,
        "min_price": 20,
        "category": "ascended_heroes",
    },
    {
        "card_name": "Mew ex SIR",
        "search_query": "Mew ex SIR Ascended Heroes",
        "expected_price": 150,
        "min_price": 20,
        "category": "ascended_heroes",
    },
    {
        "card_name": "Gyarados ex SIR",
        "search_query": "Gyarados ex SIR Ascended Heroes",
        "expected_price": 150,
        "min_price": 20,
        "category": "ascended_heroes",
    },
    {
        "card_name": "Arcanine ex SIR",
        "search_query": "Arcanine ex SIR Ascended Heroes",
        "expected_price": 100,
        "min_price": 20,
        "category": "ascended_heroes",
    },
]


# ── DATABASE ──────────────────────────────────────────────────────────────────

def init_sales_table():
    """Create sales history table with confidence scoring."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sales_history'")
    if c.fetchone():
        c.execute("PRAGMA table_info(sales_history)")
        columns = [row[1] for row in c.fetchall()]
        if "confidence_score" not in columns:
            print("  📦  Upgrading sales_history table...")
            c.execute("ALTER TABLE sales_history ADD COLUMN confidence_score INTEGER DEFAULT 50")
            c.execute("ALTER TABLE sales_history ADD COLUMN confidence_flags TEXT DEFAULT ''")
            c.execute("ALTER TABLE sales_history ADD COLUMN seller_feedback TEXT DEFAULT ''")
            c.execute("ALTER TABLE sales_history ADD COLUMN bid_count INTEGER DEFAULT 0")
            c.execute("ALTER TABLE sales_history ADD COLUMN best_offer INTEGER DEFAULT 0")
            conn.commit()
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS sales_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_name TEXT,
                title TEXT,
                sold_price REAL,
                sold_date TEXT,
                condition TEXT,
                listing_type TEXT,
                url TEXT,
                scraped_at TEXT,
                confidence_score INTEGER DEFAULT 50,
                confidence_flags TEXT DEFAULT '',
                seller_feedback TEXT DEFAULT '',
                bid_count INTEGER DEFAULT 0,
                best_offer INTEGER DEFAULT 0,
                UNIQUE(card_name, url)
            )
        """)

    c.execute("CREATE INDEX IF NOT EXISTS idx_sales_card_date ON sales_history(card_name, sold_date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sales_confidence ON sales_history(card_name, confidence_score)")
    conn.commit()
    conn.close()
    print("✅  Sales history table initialized")


# ── SELENIUM BROWSER ──────────────────────────────────────────────────────────

def create_browser(headless: bool = False):
    """Create a Chrome browser instance."""
    options = Options()

    if headless:
        options.add_argument("--headless=new")

    # Make it look like a real browser
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Random user agent
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    ]
    options.add_argument(f"--user-agent={random.choice(user_agents)}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Remove webdriver flag
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return driver


# ── URL BUILDER ───────────────────────────────────────────────────────────────

def build_sold_url(query: str, min_price: float = None, max_price: float = None,
                   page: int = 1) -> str:
    params = {
        "_nkw": query,
        "LH_Complete": "1",
        "LH_Sold": "1",
        "_sop": "13",
        "_pgn": str(page),
        "rt": "nc",
        "_ipg": "60",
    }
    if min_price:
        params["_udlo"] = str(min_price)
    if max_price:
        params["_udhi"] = str(max_price)

    return f"https://www.ebay.com/sch/i.html?{urllib.parse.urlencode(params)}"


# ── PARSERS ───────────────────────────────────────────────────────────────────

def parse_price(price_text: str) -> float:
    if not price_text:
        return 0.0
    cleaned = re.sub(r'[^\d.]', '', price_text.split("to")[0].strip())
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_date(date_text: str) -> str:
    if not date_text:
        return ""
    cleaned = date_text.replace("Sold", "").strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    for fmt in ("%b %d, %Y", "%d %b %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return cleaned


def parse_feedback(feedback_text: str) -> int:
    if not feedback_text:
        return 0
    nums = re.findall(r'[\d,]+', feedback_text.replace(",", ""))
    try:
        return int(nums[0]) if nums else 0
    except (ValueError, IndexError):
        return 0

# ── Title blacklist ──
BLACKLIST_KEYWORDS = [
    "repack", "mystery", "lot of", "bundle of", "custom",
    "proxy", "fake", "replica", "read description",
    "damaged", "poor condition",
    "japanese", "jp", "korean", "chinese",
    "complete set", "master set", "bulk lot",
    "booster box", "booster pack", "etb",
    "code card", "online code",
]

def is_blacklisted(title: str) -> bool:
    lower = title.lower()
    return any(kw in lower for kw in BLACKLIST_KEYWORDS)


# ── CONFIDENCE SCORING ────────────────────────────────────────────────────────

def calculate_confidence(sale: dict, expected_price: float, all_prices: list) -> tuple:
    """Calculate confidence score (0-100) for a sale."""
    score = 0
    flags = []

    listing_type = sale.get("listing_type", "")
    is_best_offer = sale.get("best_offer", False)

    if listing_type == "Buy It Now" and not is_best_offer:
        score += 30
        flags.append("BIN")
    elif is_best_offer:
        score += 20
        flags.append("OFFER_ACCEPTED")
    elif listing_type == "Auction":
        score += 0
        flags.append("AUCTION")
        if sale.get("bid_count", 0) == 1:
            score -= 20
            flags.append("SINGLE_BID")

    price = sale.get("sold_price", 0)
    if all_prices and len(all_prices) >= 3:
        import statistics
        median = statistics.median(all_prices)
        try:
            stdev = statistics.stdev(all_prices)
        except statistics.StatisticsError:
            stdev = median * 0.2

        if stdev > 0:
            z_score = abs(price - median) / stdev
            if z_score <= 1.0:
                score += 20
                flags.append("NORMAL_PRICE")
            elif z_score <= 2.0:
                score += 10
                flags.append("SLIGHT_OUTLIER")
            else:
                flags.append("PRICE_OUTLIER")
    elif expected_price > 0:
        deviation = abs(price - expected_price) / expected_price
        if deviation <= 0.25:
            score += 20
            flags.append("NORMAL_PRICE")
        elif deviation <= 0.50:
            score += 10
            flags.append("SLIGHT_OUTLIER")
        else:
            flags.append("PRICE_OUTLIER")

    if expected_price > 0 and price < expected_price * 0.5:
        score -= 10
        flags.append("SUSPICIOUSLY_CHEAP")

    feedback = parse_feedback(sale.get("seller_feedback", ""))
    if feedback >= 100:
        score += 15
        flags.append("TRUSTED_SELLER")
    elif feedback >= 50:
        score += 10
        flags.append("ESTABLISHED_SELLER")
    elif feedback >= 10:
        score += 5
        flags.append("SOME_FEEDBACK")
    else:
        flags.append("LOW_FEEDBACK")

    title = sale.get("title", "")
    if not is_blacklisted(title):
        score += 15
        flags.append("CLEAN_TITLE")
    else:
        flags.append("SUSPICIOUS_TITLE")

    score = max(0, min(100, score))
    return score, flags


# ── MAIN SCRAPING (SELENIUM) ─────────────────────────────────────────────────

def scrape_sold_listings(driver, query: str, expected_price: float = 0,
                         min_price: float = None, max_price: float = None,
                         pages: int = 2) -> list:
    """Scrape eBay sold listings using Selenium."""
    all_sales = []

    for page in range(1, pages + 1):
        url = build_sold_url(query, min_price, max_price, page)

        try:
            driver.get(url)
            time.sleep(random.uniform(4, 6))

            # Wait for items — try new selector first, then old
            item_selector = None
            for selector in [".s-card", ".s-item"]:
                try:
                    WebDriverWait(driver, 8).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    item_selector = selector
                    break
                except Exception:
                    continue

            if not item_selector:
                print(f"      ⚠️  Page {page} timed out or no results")
                continue

            soup = BeautifulSoup(driver.page_source, "html.parser")
            items = soup.select(item_selector)

            if not items:
                print(f"      ⚠️  No items found on page {page}")
                break

            page_count = 0
            for item in items:
                try:
                    # ── Check if this is actually a SOLD item ──
                    item_text = item.get_text().lower()
                    
                    # Skip items that are clearly active listings, not sold
                    if "new listing" in item_text and "sold" not in item_text:
                        continue

                    # ── Title — try multiple selectors ──
                    title = ""
                    for sel in [".s-card__title", ".s-item__title"]:
                        title_elem = item.select_one(sel)
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            break
                    # Fallback: find any link text or heading
                    if not title:
                        link = item.select_one("a")
                        if link:
                            title = link.get_text(strip=True)
                    if not title or title.lower() in ["shop on ebay", ""]:
                        continue
                    
                    # Strip "New Listing" prefix from title if present
                    if title.startswith("New Listing"):
                        title = title[len("New Listing"):].strip()
                    if title.startswith("New listing"):
                        title = title[len("New listing"):].strip()

                    # ── Price — look for price in multiple ways ──
                    price = 0.0
                    price_text = ""
                    for sel in [".s-card__price", ".s-item__price", "[class*='price']"]:
                        price_elem = item.select_one(sel)
                        if price_elem:
                            price_text = price_elem.get_text(strip=True)
                            price = parse_price(price_text)
                            if price > 0:
                                break

                    if "to" in price_text:
                        continue
                    if min_price and price < min_price:
                        continue
                    if max_price and price > max_price:
                        continue
                    if price <= 0:
                        continue

                    # ── Sold date ──
                    sold_date = ""
                    for sel in [".s-card__title--tagblock .POSITIVE",
                                ".s-item__title--tagblock .POSITIVE",
                                ".s-item__ended-date",
                                ".s-item__endedDate",
                                "[class*='ended']",
                                "[class*='sold']"]:
                        date_elem = item.select_one(sel)
                        if date_elem:
                            sold_date = parse_date(date_elem.get_text(strip=True))
                            if sold_date:
                                break
                    # Fallback: search all text for "Sold" pattern
                    if not sold_date:
                        all_text = item.get_text()
                        sold_match = re.search(r'Sold\s+(\w{3}\s+\d{1,2},?\s+\d{4})', all_text)
                        if sold_match:
                            sold_date = parse_date(sold_match.group(0))

                    # ── Condition ──
                    condition = "Unknown"
                    for sel in [".SECONDARY_INFO", "[class*='condition']", "[class*='subtitle']"]:
                        cond_elem = item.select_one(sel)
                        if cond_elem:
                            condition = cond_elem.get_text(strip=True)
                            break

                    # ── URL ──
                    item_url = ""
                    for sel in [".s-card__link", ".s-item__link", "a[href*='itm/']"]:
                        link_elem = item.select_one(sel)
                        if link_elem and link_elem.get("href"):
                            item_url = link_elem["href"]
                            break
                    if "?" in item_url:
                        item_url = item_url.split("?")[0]

                    # ── Listing type & bids ──
                    listing_type = "Buy It Now"
                    bid_count = 0
                    best_offer = False

                    for sel in [".s-item__bidCount", "[class*='bid']"]:
                        bid_elem = item.select_one(sel)
                        if bid_elem:
                            listing_type = "Auction"
                            bid_text = bid_elem.get_text(strip=True)
                            bid_nums = re.findall(r'\d+', bid_text)
                            bid_count = int(bid_nums[0]) if bid_nums else 0
                            break

                    # Best offer check
                    item_text = item.get_text().lower()
                    if "best offer" in item_text:
                        best_offer = True
                        if listing_type == "Buy It Now":
                            listing_type = "Best Offer"

                    # ── Seller info ──
                    seller_feedback = ""
                    for sel in [".s-item__seller-info-text", "[class*='seller']"]:
                        seller_elem = item.select_one(sel)
                        if seller_elem:
                            seller_feedback = seller_elem.get_text(strip=True)
                            break

                    all_sales.append({
                        "title": title,
                        "sold_price": price,
                        "sold_date": sold_date,
                        "condition": condition,
                        "listing_type": listing_type,
                        "url": item_url,
                        "bid_count": bid_count,
                        "best_offer": best_offer,
                        "seller_feedback": seller_feedback,
                    })
                    page_count += 1

                except Exception:
                    continue

            print(f"      📄  Page {page}: {page_count} listings scraped")

        except Exception as e:
            print(f"      ⚠️  Error on page {page}: {e}")
            continue

        # Delay between pages
        if page < pages:
            time.sleep(random.uniform(3, 6))

    # Calculate confidence scores
    all_prices = [s["sold_price"] for s in all_sales if s["sold_price"] > 0]
    for sale in all_sales:
        score, flags = calculate_confidence(sale, expected_price, all_prices)
        sale["confidence_score"] = score
        sale["confidence_flags"] = ",".join(flags)

    return all_sales


# ── MAIN COLLECTION ───────────────────────────────────────────────────────────

def collect_all_sales(verified_only: bool = False, headless: bool = False):
    """Scrape sold listings for all tracked cards."""
    mode = "VERIFIED ONLY" if verified_only else "ALL SALES"
    print(f"\n💰  Sales History Scraper [{mode}] — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("─" * 60)

    print("  🌐  Launching Chrome browser...")
    driver = create_browser(headless=headless)
    print("  ✅  Browser ready\n")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    scraped_at = datetime.now().isoformat()

    total_new = 0
    total_filtered = 0

    try:
        for card in CARDS_TO_SCRAPE:
            name = card["card_name"]
            query = card["search_query"]
            expected = card.get("expected_price", 0)
            print(f"  🔍  {name}")
            print(f"      Query: \"{query}\"")

            sales = scrape_sold_listings(
                driver,
                query,
                expected_price=expected,
                min_price=card.get("min_price"),
                max_price=card.get("max_price"),
                pages=2,
            )

            if not sales:
                print(f"      ⚠️  No sold listings found\n")
                continue

            high = [s for s in sales if s["confidence_score"] >= 70]
            medium = [s for s in sales if 40 <= s["confidence_score"] < 70]
            low = [s for s in sales if s["confidence_score"] < 40]

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

            total_new += new_count
            total_filtered += filtered_count

            prices_high = [s["sold_price"] for s in high if s["sold_price"] > 0]
            prices_all = [s["sold_price"] for s in sales if s["sold_price"] > 0]

            print(f"      ✅  Found {len(sales)} sales ({new_count} new, {filtered_count} filtered)")
            print(f"      📊  Confidence: {len(high)} high | {len(medium)} medium | {len(low)} low")

            if prices_high:
                import statistics
                median_h = statistics.median(prices_high)
                print(f"      💚  Verified median: ${median_h:,.2f}")

            if prices_all:
                import statistics
                median_a = statistics.median(prices_all)
                print(f"      💵  All-sales median: ${median_a:,.2f}")

            print()
            time.sleep(random.uniform(3, 6))

        # ── GRADED SEARCH PASS ──
        # For cards with expected_price >= $50, do additional searches
        # specifically for PSA and BGS graded versions
        GRADED_SEARCHES = ["PSA", "BGS", "CGC"]
        GRADED_THRESHOLD = 50  # Only search graded for cards worth $50+

        graded_cards = [c for c in CARDS_TO_SCRAPE if c.get("expected_price", 0) >= GRADED_THRESHOLD]

        if graded_cards:
            print(f"\n{'='*55}")
            print(f"  🏅  GRADED SEARCH PASS — {len(graded_cards)} cards × {len(GRADED_SEARCHES)} graders × 3 grades")
            print(f"{'='*55}\n")

            for card in graded_cards:
                name = card["card_name"]
                base_query = card["search_query"]

                # Build a SHORT graded query — strip card numbers and keep just
                # the pokemon name + set name. eBay works better with shorter queries.
                # "Pikachu ex 276 Ascended Heroes" -> "Pikachu ex Ascended Heroes"
                # "Charizard Gold Star 100 EX Dragon Frontiers" -> "Charizard Gold Star Dragon Frontiers"
                # "Umbreon ex 161/180 Prismatic Evolutions" -> "Umbreon ex Prismatic Evolutions"
                clean_query = re.sub(r'\d+/\d+', '', base_query)  # remove "161/180"
                clean_query = re.sub(r'\b\d{2,3}\b', '', clean_query)  # remove standalone 2-3 digit numbers
                clean_query = re.sub(r'\bEX\b', '', clean_query)  # remove "EX" prefix from set names
                clean_query = re.sub(r'\s+', ' ', clean_query).strip()

                for grader in GRADED_SEARCHES:
                    # Each grading company uses different grade scales
                    grade_scales = {
                        "PSA": ["10", "9", "8"],       # PSA uses whole numbers only
                        "BGS": ["10", "9.5", "9"],     # BGS uses half grades
                        "CGC": ["10", "9.5", "9"],     # CGC uses half grades
                    }
                    grades_to_search = grade_scales.get(grader, ["10", "9"])

                    for grade_num in grades_to_search:
                        graded_query = f"{grader} {grade_num} {clean_query}"
                        print(f"  🏅  {name} [{grader} {grade_num}]")
                        print(f"      Query: \"{graded_query}\"")

                        sales = scrape_sold_listings(
                            driver,
                            graded_query,
                            expected_price=card.get("expected_price", 0) * 2,
                            min_price=card.get("min_price", 0),
                            pages=1,
                        )

                    if not sales:
                        print(f"      ⚠️  No graded listings found\n")
                        continue

                    # FILTER: only keep listings that actually mention the grader in the title
                    # eBay returns irrelevant results even with PSA/BGS in the query
                    grader_aliases = {
                        "PSA": ["PSA", "PROFESSIONAL SPORTS AUTHENTICATOR"],
                        "BGS": ["BGS", "BECKETT", "BKT"],
                        "CGC": ["CGC"],
                    }
                    aliases = grader_aliases.get(grader, [grader])
                    graded_sales = [
                        s for s in sales
                        if any(alias in s["title"].upper() for alias in aliases)
                    ]

                    skipped = len(sales) - len(graded_sales)
                    if skipped > 0:
                        print(f"      🔍  {len(sales)} results, {skipped} skipped (no {grader} in title)")

                    new_count = 0
                    updated_count = 0
                    for sale in graded_sales:
                        if is_blacklisted(sale["title"]):
                            continue
                        try:
                            # First try to insert as new
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
                                total_new += 1
                            else:
                                # Record already exists — update title if the new one has grading info
                                # This catches cases where the same listing was scraped earlier
                                # with a truncated title that didn't include "PSA 10" etc.
                                c.execute("""
                                    UPDATE sales_history
                                    SET title = ?
                                    WHERE sold_price = ? AND sold_date = ? AND card_name = ?
                                    AND (title NOT LIKE '%PSA%' AND title NOT LIKE '%BGS%'
                                         AND title NOT LIKE '%CGC%' AND title NOT LIKE '%BECKETT%')
                                """, (
                                    sale["title"], sale["sold_price"],
                                    sale["sold_date"], name,
                                ))
                                if c.rowcount > 0:
                                    updated_count += 1
                        except sqlite3.IntegrityError:
                            pass

                    print(f"      ✅  {len(graded_sales)} graded listings, {new_count} new, {updated_count} updated")
                    print()
                    time.sleep(random.uniform(2, 4))

            # Re-parse grades for all new records
            from grade_parser import update_all_grades, init_grade_columns
            init_grade_columns()
            conn.commit()
            update_all_grades()

    finally:
        driver.quit()
        print("  🌐  Browser closed")

    conn.commit()
    conn.close()
    print(f"\n✅  Done! {total_new} new records, {total_filtered} filtered out\n")


# ── QUERY HELPERS (for dashboard / Lovable) ───────────────────────────────────

def get_sales_history(card_name: str = None, verified_only: bool = False) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    min_conf = 60 if verified_only else 0

    if card_name:
        c.execute("""
            SELECT * FROM sales_history
            WHERE card_name = ? AND confidence_score >= ?
            ORDER BY sold_date DESC
        """, (card_name, min_conf))
    else:
        c.execute("""
            SELECT * FROM sales_history
            WHERE confidence_score >= ?
            ORDER BY sold_date DESC
        """, (min_conf,))

    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def get_sales_summary(verified_only: bool = False) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    min_conf = 60 if verified_only else 0

    c.execute("""
        SELECT
            card_name,
            COUNT(*) as total_sales,
            ROUND(AVG(sold_price), 2) as avg_price,
            ROUND(MIN(sold_price), 2) as min_price,
            ROUND(MAX(sold_price), 2) as max_price,
            ROUND(AVG(confidence_score), 1) as avg_confidence,
            MIN(sold_date) as earliest_sale,
            MAX(sold_date) as latest_sale,
            SUM(CASE WHEN listing_type = 'Buy It Now' THEN 1 ELSE 0 END) as bin_count,
            SUM(CASE WHEN listing_type = 'Auction' THEN 1 ELSE 0 END) as auction_count,
            SUM(CASE WHEN listing_type = 'Best Offer' THEN 1 ELSE 0 END) as offer_count
        FROM sales_history
        WHERE sold_price > 0 AND confidence_score >= ?
        GROUP BY card_name
        ORDER BY avg_price DESC
    """, (min_conf,))

    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def get_price_over_time(card_name: str, verified_only: bool = False) -> list:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    min_conf = 60 if verified_only else 0

    c.execute("""
        SELECT
            sold_date,
            ROUND(AVG(sold_price), 2) as avg_price,
            COUNT(*) as num_sales,
            ROUND(MIN(sold_price), 2) as min_price,
            ROUND(MAX(sold_price), 2) as max_price,
            ROUND(AVG(confidence_score), 1) as avg_confidence
        FROM sales_history
        WHERE card_name = ? AND sold_price > 0 AND sold_date != ''
              AND confidence_score >= ?
        GROUP BY sold_date
        ORDER BY sold_date ASC
    """, (card_name, min_conf))

    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not HAS_SELENIUM:
        print("\n❌  Selenium not installed. Run:")
        print("    pip install selenium webdriver-manager beautifulsoup4\n")
        sys.exit(1)
    if not HAS_BS4:
        print("\n❌  BeautifulSoup not installed. Run:")
        print("    pip install beautifulsoup4\n")
        sys.exit(1)

    init_sales_table()

    verified = "--verified" in sys.argv
    headless = "--headless" in sys.argv

    if "--demo" in sys.argv:
        print("\n🎮  Demo mode — URLs that would be scraped:\n")
        for card in CARDS_TO_SCRAPE:
            url = build_sold_url(card["search_query"], card.get("min_price"), card.get("max_price"))
            print(f"  {card['card_name']} (expected ~${card.get('expected_price', '?')})")
            print(f"    {url}\n")
        print("  Run without --demo to scrape with Chrome.")
        print("  Add --headless to run without visible browser window.")
        print("  Add --verified to only keep high-confidence sales.\n")

    elif "--card" in sys.argv:
        idx = sys.argv.index("--card") + 1
        if idx < len(sys.argv):
            search = sys.argv[idx].lower()
            matching = [c for c in CARDS_TO_SCRAPE if search in c["card_name"].lower()]
            if matching:
                CARDS_TO_SCRAPE[:] = matching
                collect_all_sales(verified_only=verified, headless=headless)
            else:
                print(f"❌  No card matching '{search}'")
        else:
            print("❌  Provide a card name after --card")
    else:
        collect_all_sales(verified_only=verified, headless=headless)
