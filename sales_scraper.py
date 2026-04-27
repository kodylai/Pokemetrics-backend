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
import threading
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
        "card_name": "Alakazam 1/102 Base",
        "search_query": "Alakazam 1 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Blastoise 2/102 Base",
        "search_query": "Blastoise 2 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Chansey 3/102 Base",
        "search_query": "Chansey 3 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Charizard 4/102 Base",
        "search_query": "Charizard 4 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Clefairy 5/102 Base",
        "search_query": "Clefairy 5 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Gyarados 6/102 Base",
        "search_query": "Gyarados 6 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Hitmonchan 7/102 Base",
        "search_query": "Hitmonchan 7 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Machamp 8/102 Base",
        "search_query": "Machamp 8 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Magneton 9/102 Base",
        "search_query": "Magneton 9 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Mewtwo 10/102 Base",
        "search_query": "Mewtwo 10 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Nidoking 11/102 Base",
        "search_query": "Nidoking 11 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Ninetales 12/102 Base",
        "search_query": "Ninetales 12 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Poliwrath 13/102 Base",
        "search_query": "Poliwrath 13 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Raichu 14/102 Base",
        "search_query": "Raichu 14 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Venusaur 15/102 Base",
        "search_query": "Venusaur 15 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },
    {
        "card_name": "Zapdos 16/102 Base",
        "search_query": "Zapdos 16 Base -lot -bundle -collection -binder",
        "expected_price": 20,
        "min_price": 5.0,
        "category": "base_set",
    },

    # ── EVOLVING SKIES ──
    {
        "card_name": "Leafeon VMAX 8/203 Evolving Skies",
        "search_query": "Leafeon VMAX 8 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Trevenant VMAX 14/203 Evolving Skies",
        "search_query": "Trevenant VMAX 14 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Flareon VMAX 18/203 Evolving Skies",
        "search_query": "Flareon VMAX 18 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Gyarados VMAX 29/203 Evolving Skies",
        "search_query": "Gyarados VMAX 29 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Vaporeon VMAX 30/203 Evolving Skies",
        "search_query": "Vaporeon VMAX 30 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Glaceon VMAX 41/203 Evolving Skies",
        "search_query": "Glaceon VMAX 41 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Jolteon VMAX 51/203 Evolving Skies",
        "search_query": "Jolteon VMAX 51 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Dracozolt VMAX 59/203 Evolving Skies",
        "search_query": "Dracozolt VMAX 59 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Espeon VMAX 65/203 Evolving Skies",
        "search_query": "Espeon VMAX 65 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Sylveon VMAX 75/203 Evolving Skies",
        "search_query": "Sylveon VMAX 75 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Lycanroc VMAX 92/203 Evolving Skies",
        "search_query": "Lycanroc VMAX 92 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Umbreon VMAX 95/203 Evolving Skies",
        "search_query": "Umbreon VMAX 95 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Garbodor VMAX 101/203 Evolving Skies",
        "search_query": "Garbodor VMAX 101 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Rayquaza VMAX 111/203 Evolving Skies",
        "search_query": "Rayquaza VMAX 111 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Duraludon VMAX 123/203 Evolving Skies",
        "search_query": "Duraludon VMAX 123 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Leafeon V 166/203 Evolving Skies",
        "search_query": "Leafeon V 166 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Leafeon V 167/203 Evolving Skies",
        "search_query": "Leafeon V 167 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Trevenant V 168/203 Evolving Skies",
        "search_query": "Trevenant V 168 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Flareon V 169/203 Evolving Skies",
        "search_query": "Flareon V 169 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Volcarona V 170/203 Evolving Skies",
        "search_query": "Volcarona V 170 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Gyarados V 171/203 Evolving Skies",
        "search_query": "Gyarados V 171 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Vaporeon V 172/203 Evolving Skies",
        "search_query": "Vaporeon V 172 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Suicune V 173/203 Evolving Skies",
        "search_query": "Suicune V 173 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Glaceon V 174/203 Evolving Skies",
        "search_query": "Glaceon V 174 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Glaceon V 175/203 Evolving Skies",
        "search_query": "Glaceon V 175 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Arctovish V 176/203 Evolving Skies",
        "search_query": "Arctovish V 176 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Jolteon V 177/203 Evolving Skies",
        "search_query": "Jolteon V 177 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Dracozolt V 178/203 Evolving Skies",
        "search_query": "Dracozolt V 178 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Espeon V 179/203 Evolving Skies",
        "search_query": "Espeon V 179 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Espeon V 180/203 Evolving Skies",
        "search_query": "Espeon V 180 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Golurk V 181/203 Evolving Skies",
        "search_query": "Golurk V 181 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Golurk V 182/203 Evolving Skies",
        "search_query": "Golurk V 182 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Sylveon V 183/203 Evolving Skies",
        "search_query": "Sylveon V 183 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Sylveon V 184/203 Evolving Skies",
        "search_query": "Sylveon V 184 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Medicham V 185/203 Evolving Skies",
        "search_query": "Medicham V 185 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Medicham V 186/203 Evolving Skies",
        "search_query": "Medicham V 186 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Lycanroc V 187/203 Evolving Skies",
        "search_query": "Lycanroc V 187 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Umbreon V 188/203 Evolving Skies",
        "search_query": "Umbreon V 188 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Umbreon V 189/203 Evolving Skies",
        "search_query": "Umbreon V 189 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Garbodor V 190/203 Evolving Skies",
        "search_query": "Garbodor V 190 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Dragonite V 191/203 Evolving Skies",
        "search_query": "Dragonite V 191 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Dragonite V 192/203 Evolving Skies",
        "search_query": "Dragonite V 192 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Rayquaza V 193/203 Evolving Skies",
        "search_query": "Rayquaza V 193 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Rayquaza V 194/203 Evolving Skies",
        "search_query": "Rayquaza V 194 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Noivern V 195/203 Evolving Skies",
        "search_query": "Noivern V 195 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Noivern V 196/203 Evolving Skies",
        "search_query": "Noivern V 196 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Duraludon V 197/203 Evolving Skies",
        "search_query": "Duraludon V 197 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Duraludon V 198/203 Evolving Skies",
        "search_query": "Duraludon V 198 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Aroma Lady 199/203 Evolving Skies",
        "search_query": "Aroma Lady 199 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Copycat 200/203 Evolving Skies",
        "search_query": "Copycat 200 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Gordie 201/203 Evolving Skies",
        "search_query": "Gordie 201 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Raihan 202/203 Evolving Skies",
        "search_query": "Raihan 202 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Zinnia's Resolve 203/203 Evolving Skies",
        "search_query": "Zinnia's Resolve 203 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Leafeon VMAX 204/203 Evolving Skies",
        "search_query": "Leafeon VMAX 204 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Leafeon VMAX 205/203 Evolving Skies",
        "search_query": "Leafeon VMAX 205 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Trevenant VMAX 206/203 Evolving Skies",
        "search_query": "Trevenant VMAX 206 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Gyarados VMAX 207/203 Evolving Skies",
        "search_query": "Gyarados VMAX 207 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Glaceon VMAX 208/203 Evolving Skies",
        "search_query": "Glaceon VMAX 208 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Glaceon VMAX 209/203 Evolving Skies",
        "search_query": "Glaceon VMAX 209 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Dracozolt VMAX 210/203 Evolving Skies",
        "search_query": "Dracozolt VMAX 210 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Sylveon VMAX 211/203 Evolving Skies",
        "search_query": "Sylveon VMAX 211 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Sylveon VMAX 212/203 Evolving Skies",
        "search_query": "Sylveon VMAX 212 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Lycanroc VMAX 213/203 Evolving Skies",
        "search_query": "Lycanroc VMAX 213 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Umbreon VMAX 214/203 Evolving Skies",
        "search_query": "Umbreon VMAX 214 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Umbreon VMAX 215/203 Evolving Skies",
        "search_query": "Umbreon VMAX 215 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Garbodor VMAX 216/203 Evolving Skies",
        "search_query": "Garbodor VMAX 216 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Rayquaza VMAX 217/203 Evolving Skies",
        "search_query": "Rayquaza VMAX 217 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Rayquaza VMAX 218/203 Evolving Skies",
        "search_query": "Rayquaza VMAX 218 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Duraludon VMAX 219/203 Evolving Skies",
        "search_query": "Duraludon VMAX 219 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Duraludon VMAX 220/203 Evolving Skies",
        "search_query": "Duraludon VMAX 220 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Aroma Lady 221/203 Evolving Skies",
        "search_query": "Aroma Lady 221 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Copycat 222/203 Evolving Skies",
        "search_query": "Copycat 222 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Gordie 223/203 Evolving Skies",
        "search_query": "Gordie 223 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Raihan 224/203 Evolving Skies",
        "search_query": "Raihan 224 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Zinnia's Resolve 225/203 Evolving Skies",
        "search_query": "Zinnia's Resolve 225 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Froslass 226/203 Evolving Skies",
        "search_query": "Froslass 226 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Inteleon 227/203 Evolving Skies",
        "search_query": "Inteleon 227 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Cresselia 228/203 Evolving Skies",
        "search_query": "Cresselia 228 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Boost Shake 229/203 Evolving Skies",
        "search_query": "Boost Shake 229 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Crystal Cave 230/203 Evolving Skies",
        "search_query": "Crystal Cave 230 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Full Face Guard 231/203 Evolving Skies",
        "search_query": "Full Face Guard 231 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Stormy Mountains 232/203 Evolving Skies",
        "search_query": "Stormy Mountains 232 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Toy Catcher 233/203 Evolving Skies",
        "search_query": "Toy Catcher 233 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Turffield Stadium 234/203 Evolving Skies",
        "search_query": "Turffield Stadium 234 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Lightning Energy 235/203 Evolving Skies",
        "search_query": "Lightning Energy 235 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Darkness Energy 236/203 Evolving Skies",
        "search_query": "Darkness Energy 236 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },
    {
        "card_name": "Metal Energy 237/203 Evolving Skies",
        "search_query": "Metal Energy 237 Evolving Skies -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 20.0,
        "category": "evolving_skies",
    },

    # ── SURGING SPARKS ──
    {
        "card_name": "Durant ex 4/191 Surging Sparks",
        "search_query": "Durant ex 4 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Ceruledge ex 36/191 Surging Sparks",
        "search_query": "Ceruledge ex 36 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Scovillain ex 37/191 Surging Sparks",
        "search_query": "Scovillain ex 37 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Milotic ex 42/191 Surging Sparks",
        "search_query": "Milotic ex 42 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Black Kyurem ex 48/191 Surging Sparks",
        "search_query": "Black Kyurem ex 48 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Pikachu ex 57/191 Surging Sparks",
        "search_query": "Pikachu ex 57 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Kilowattrel ex 68/191 Surging Sparks",
        "search_query": "Kilowattrel ex 68 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Latias ex 76/191 Surging Sparks",
        "search_query": "Latias ex 76 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Sylveon ex 86/191 Surging Sparks",
        "search_query": "Sylveon ex 86 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Palossand ex 91/191 Surging Sparks",
        "search_query": "Palossand ex 91 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Flygon ex 106/191 Surging Sparks",
        "search_query": "Flygon ex 106 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Hydreigon ex 119/191 Surging Sparks",
        "search_query": "Hydreigon ex 119 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Archaludon ex 130/191 Surging Sparks",
        "search_query": "Archaludon ex 130 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Alolan Exeggutor ex 133/191 Surging Sparks",
        "search_query": "Alolan Exeggutor ex 133 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Tatsugiri ex 142/191 Surging Sparks",
        "search_query": "Tatsugiri ex 142 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Slaking ex 147/191 Surging Sparks",
        "search_query": "Slaking ex 147 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Cyclizar ex 159/191 Surging Sparks",
        "search_query": "Cyclizar ex 159 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Flamigo ex 160/191 Surging Sparks",
        "search_query": "Flamigo ex 160 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Amulet of Hope 162/191 Surging Sparks",
        "search_query": "Amulet of Hope 162 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Brilliant Blender 164/191 Surging Sparks",
        "search_query": "Brilliant Blender 164 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Energy Search Pro 176/191 Surging Sparks",
        "search_query": "Energy Search Pro 176 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Megaton Blower 182/191 Surging Sparks",
        "search_query": "Megaton Blower 182 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Miracle Headset 183/191 Surging Sparks",
        "search_query": "Miracle Headset 183 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Precious Trolley 185/191 Surging Sparks",
        "search_query": "Precious Trolley 185 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Scramble Switch 186/191 Surging Sparks",
        "search_query": "Scramble Switch 186 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Enriching Energy 191/191 Surging Sparks",
        "search_query": "Enriching Energy 191 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Exeggcute 192/191 Surging Sparks",
        "search_query": "Exeggcute 192 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Vivillon 193/191 Surging Sparks",
        "search_query": "Vivillon 193 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Shiinotic 194/191 Surging Sparks",
        "search_query": "Shiinotic 194 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Castform Sunny Form 195/191 Surging Sparks",
        "search_query": "Castform Sunny Form 195 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Larvesta 196/191 Surging Sparks",
        "search_query": "Larvesta 196 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Ceruledge 197/191 Surging Sparks",
        "search_query": "Ceruledge 197 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Feebas 198/191 Surging Sparks",
        "search_query": "Feebas 198 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Spheal 199/191 Surging Sparks",
        "search_query": "Spheal 199 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Bruxish 200/191 Surging Sparks",
        "search_query": "Bruxish 200 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Cetitan 201/191 Surging Sparks",
        "search_query": "Cetitan 201 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Stunfisk 202/191 Surging Sparks",
        "search_query": "Stunfisk 202 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Latios 203/191 Surging Sparks",
        "search_query": "Latios 203 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Mesprit 204/191 Surging Sparks",
        "search_query": "Mesprit 204 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Phanpy 205/191 Surging Sparks",
        "search_query": "Phanpy 205 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Vibrava 206/191 Surging Sparks",
        "search_query": "Vibrava 206 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Clobbopus 207/191 Surging Sparks",
        "search_query": "Clobbopus 207 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Alolan Dugtrio 208/191 Surging Sparks",
        "search_query": "Alolan Dugtrio 208 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Skarmory 209/191 Surging Sparks",
        "search_query": "Skarmory 209 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Flapple 210/191 Surging Sparks",
        "search_query": "Flapple 210 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Appletun 211/191 Surging Sparks",
        "search_query": "Appletun 211 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Slakoth 212/191 Surging Sparks",
        "search_query": "Slakoth 212 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Kecleon 213/191 Surging Sparks",
        "search_query": "Kecleon 213 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Braviary 214/191 Surging Sparks",
        "search_query": "Braviary 214 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Durant ex 215/191 Surging Sparks",
        "search_query": "Durant ex 215 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Scovillain ex 216/191 Surging Sparks",
        "search_query": "Scovillain ex 216 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Milotic ex 217/191 Surging Sparks",
        "search_query": "Milotic ex 217 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Black Kyurem ex 218/191 Surging Sparks",
        "search_query": "Black Kyurem ex 218 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Pikachu ex 219/191 Surging Sparks",
        "search_query": "Pikachu ex 219 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Latias ex 220/191 Surging Sparks",
        "search_query": "Latias ex 220 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Palossand ex 221/191 Surging Sparks",
        "search_query": "Palossand ex 221 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Flygon ex 222/191 Surging Sparks",
        "search_query": "Flygon ex 222 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Hydreigon ex 223/191 Surging Sparks",
        "search_query": "Hydreigon ex 223 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Archaludon ex 224/191 Surging Sparks",
        "search_query": "Archaludon ex 224 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Alolan Exeggutor ex 225/191 Surging Sparks",
        "search_query": "Alolan Exeggutor ex 225 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Tatsugiri ex 226/191 Surging Sparks",
        "search_query": "Tatsugiri ex 226 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Slaking ex 227/191 Surging Sparks",
        "search_query": "Slaking ex 227 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Cyclizar ex 228/191 Surging Sparks",
        "search_query": "Cyclizar ex 228 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Clemont's Quick Wit 229/191 Surging Sparks",
        "search_query": "Clemont's Quick Wit 229 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Cyrano 230/191 Surging Sparks",
        "search_query": "Cyrano 230 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Drasna 231/191 Surging Sparks",
        "search_query": "Drasna 231 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Drayton 232/191 Surging Sparks",
        "search_query": "Drayton 232 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Jasmine's Gaze 233/191 Surging Sparks",
        "search_query": "Jasmine's Gaze 233 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Lisia's Appeal 234/191 Surging Sparks",
        "search_query": "Lisia's Appeal 234 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Surfer 235/191 Surging Sparks",
        "search_query": "Surfer 235 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Durant ex 236/191 Surging Sparks",
        "search_query": "Durant ex 236 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Milotic ex 237/191 Surging Sparks",
        "search_query": "Milotic ex 237 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Pikachu ex 238/191 Surging Sparks",
        "search_query": "Pikachu ex 238 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Latias ex 239/191 Surging Sparks",
        "search_query": "Latias ex 239 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Hydreigon ex 240/191 Surging Sparks",
        "search_query": "Hydreigon ex 240 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Archaludon ex 241/191 Surging Sparks",
        "search_query": "Archaludon ex 241 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Alolan Exeggutor ex 242/191 Surging Sparks",
        "search_query": "Alolan Exeggutor ex 242 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Clemont's Quick Wit 243/191 Surging Sparks",
        "search_query": "Clemont's Quick Wit 243 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Drayton 244/191 Surging Sparks",
        "search_query": "Drayton 244 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Jasmine's Gaze 245/191 Surging Sparks",
        "search_query": "Jasmine's Gaze 245 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Lisia's Appeal 246/191 Surging Sparks",
        "search_query": "Lisia's Appeal 246 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Pikachu ex 247/191 Surging Sparks",
        "search_query": "Pikachu ex 247 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Alolan Exeggutor ex 248/191 Surging Sparks",
        "search_query": "Alolan Exeggutor ex 248 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Counter Gain 249/191 Surging Sparks",
        "search_query": "Counter Gain 249 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Gravity Mountain 250/191 Surging Sparks",
        "search_query": "Gravity Mountain 250 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Night Stretcher 251/191 Surging Sparks",
        "search_query": "Night Stretcher 251 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },
    {
        "card_name": "Jet Energy 252/191 Surging Sparks",
        "search_query": "Jet Energy 252 Surging Sparks -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 10.0,
        "category": "surging_sparks",
    },

    # ── NEO SHINING ──
    {
        "card_name": "Shining Celebi 106/105 Neo Destiny",
        "search_query": "Shining Celebi 106 Neo Destiny -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Charizard 107/105 Neo Destiny",
        "search_query": "Shining Charizard 107 Neo Destiny -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Kabutops 108/105 Neo Destiny",
        "search_query": "Shining Kabutops 108 Neo Destiny -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Mewtwo 109/105 Neo Destiny",
        "search_query": "Shining Mewtwo 109 Neo Destiny -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Noctowl 110/105 Neo Destiny",
        "search_query": "Shining Noctowl 110 Neo Destiny -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Raichu 111/105 Neo Destiny",
        "search_query": "Shining Raichu 111 Neo Destiny -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Steelix 112/105 Neo Destiny",
        "search_query": "Shining Steelix 112 Neo Destiny -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Tyranitar 113/105 Neo Destiny",
        "search_query": "Shining Tyranitar 113 Neo Destiny -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Gyarados 65/64 Neo Revelation",
        "search_query": "Shining Gyarados 65 Neo Revelation -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },
    {
        "card_name": "Shining Magikarp 66/64 Neo Revelation",
        "search_query": "Shining Magikarp 66 Neo Revelation -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 100.0,
        "category": "neo_shining",
    },

    # ── CRYSTAL CARDS ──
    {
        "card_name": "Crystal Shard 122/144 Skyridge",
        "search_query": "Crystal Shard 122 Skyridge -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 200.0,
        "category": "crystal_cards",
    },
    {
        "card_name": "Crystal Energy 146/147 Aquapolis",
        "search_query": "Crystal Energy 146 Aquapolis -lot -bundle -collection -binder",
        "expected_price": 100,
        "min_price": 200.0,
        "category": "crystal_cards",
    },

    # ── PHANTASMAL FLAMES ──
    {
        "card_name": "Mega Charizard ex SIR Phantasmal Flames",
        "search_query": "Mega Charizard ex SIR 125 Phantasmal Flames",
        "expected_price": 1000,
        "min_price": 50,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Blastoise ex SIR Phantasmal Flames",
        "search_query": "Mega Blastoise ex SIR Phantasmal Flames",
        "expected_price": 200,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Venusaur ex SIR Phantasmal Flames",
        "search_query": "Mega Venusaur ex SIR Phantasmal Flames",
        "expected_price": 150,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Gengar ex SIR Phantasmal Flames",
        "search_query": "Mega Gengar ex SIR Phantasmal Flames",
        "expected_price": 200,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Rayquaza ex SIR Phantasmal Flames",
        "search_query": "Mega Rayquaza ex SIR Phantasmal Flames",
        "expected_price": 300,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Mewtwo ex SIR Phantasmal Flames",
        "search_query": "Mega Mewtwo ex SIR Phantasmal Flames",
        "expected_price": 250,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Gardevoir ex SIR Phantasmal Flames",
        "search_query": "Mega Gardevoir ex SIR Phantasmal Flames",
        "expected_price": 200,
        "min_price": 20,
        "category": "phantasmal_flames",
    },
    {
        "card_name": "Mega Lucario ex SIR Phantasmal Flames",
        "search_query": "Mega Lucario ex SIR Phantasmal Flames",
        "expected_price": 150,
        "min_price": 20,
        "category": "phantasmal_flames",
    },

    # ── ASCENDED HEROES ──
    {
        "card_name": "Pikachu ex SIR Ascended Heroes",
        "search_query": "Pikachu ex 276 SIR Ascended Heroes",
        "expected_price": 1500,
        "min_price": 100,
        "category": "ascended_heroes",
    },
    {
        "card_name": "Dragonite ex SIR Ascended Heroes",
        "search_query": "Dragonite ex SIR Ascended Heroes",
        "expected_price": 200,
        "min_price": 20,
        "category": "ascended_heroes",
    },
    {
        "card_name": "Mewtwo ex SIR Ascended Heroes",
        "search_query": "Mewtwo ex SIR Ascended Heroes",
        "expected_price": 200,
        "min_price": 20,
        "category": "ascended_heroes",
    },
    {
        "card_name": "Mew ex SIR Ascended Heroes",
        "search_query": "Mew ex SIR Ascended Heroes",
        "expected_price": 150,
        "min_price": 20,
        "category": "ascended_heroes",
    },
    {
        "card_name": "Gyarados ex SIR Ascended Heroes",
        "search_query": "Gyarados ex SIR Ascended Heroes",
        "expected_price": 150,
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
SKIP_HOURS = 12
NUM_BROWSERS = 3


def get_last_scraped_times():
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
    last = last_scraped_times.get(card_name)
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
        return (datetime.now() - last_dt).total_seconds() / 3600 < skip_hours
    except (ValueError, TypeError):
        return False


def scrape_card_batch(cards_batch, verified_only, headless, batch_id):
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
