# Pokemetrics

A full-stack Pokemon card market analytics platform that tracks real eBay sold prices, separates graded vs raw sales, and surfaces market intelligence across 400+ cards.

Built as both a personal tool for card collecting/investing and a portfolio project demonstrating full-stack data engineering, statistical modeling, and frontend development.

## What It Does

**Real Market Data** — Scrapes actual eBay sold listings (not asking prices) via Selenium. Tracks completed transactions with price, date, listing type, seller info, and confidence scoring.

**Grade Separation** — Parses PSA, BGS, CGC, ACE, and AGS grades from listing titles. Shows price breakdowns per grade so you can see that a PSA 10 Umbreon ex sells for $2.5K while a Raw copy sells for $1.4K.

**Confidence Scoring** — Each sale gets a 0-100 confidence score based on listing type (BIN vs auction), bid count, price outlier detection, seller feedback, and blacklisted keywords. Filter to verified sales only for cleaner data.

**Price Prediction Model** — Log-linear regression using Pull Cost and Desirability scores to predict card prices. R² of ~88%. Flags cards as overvalued or undervalued vs model prediction.

**Market Dynamics** — Demand pressure, supply saturation shift, and market signals (HEATING / COOLING / TIGHTENING / LOOSENING / STABLE) per card based on listing flow analysis.

**Portfolio Tracker** — Add your collection with quantity, purchase price, and condition. See live P&L per card and total portfolio value using real market data.

## Cards Tracked

| Category | Cards | Examples |
|----------|-------|---------|
| Gold Stars | 27 | Charizard ★, Umbreon ★, Rayquaza ★, Pikachu ★ |
| Prismatic Evolutions | 180 | Umbreon ex SIR, Sylveon ex, Eevee ex |
| 151 | 207 | Charizard ex SIR, Mew ex, Venusaur ex |
| Base Set | Holos | Charizard, Blastoise, Venusaur |
| Evolving Skies | Alt Arts | Umbreon VMAX, Rayquaza VMAX |
| Neo Destiny | Shining | Shining Charizard, Shining Mewtwo |
| Skyridge/Aquapolis | Crystal | Crystal Charizard, Crystal Lugia |
| Modern Sets | SIRs | Mega Charizard ex, Pikachu ex |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python, Flask, SQLite |
| Data Collection | Selenium, BeautifulSoup, eBay Browse API |
| Analytics | scikit-learn, pandas, numpy |
| Frontend | React, TypeScript, TanStack Router/Query, Tailwind CSS |
| Card Data | PokemonTCG API (images, metadata) |
| Design | Lovable (initial scaffolding), hand-refined |

## Architecture

```
┌─────────────────────────────────┐
│  Pokemetrics React Frontend     │
│  localhost:8080                  │
│  ┌────────┬────────┬──────────┐ │
│  │ Gallery│Currents│Portfolio │ │
│  │  +     │  +     │  +       │ │
│  │ Detail │ Detail │ P&L      │ │
│  │ Panel  │ Panel  │ Tracking │ │
│  └────┬───┴────┬───┴─────┬───┘ │
└───────┼────────┼─────────┼─────┘
        │        │         │
        ▼        ▼         ▼
┌─────────────────────────────────┐
│  Flask API · localhost:5000     │
│                                 │
│  /api/sales/summary             │
│  /api/sales/trend/<card>        │
│  /api/grades/<card>             │
│  /api/images                    │
│  /api/model                     │
│  /api/dynamics                  │
│  /api/portfolios                │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  SQLite · pokemon_cards.db      │
│                                 │
│  sales_history (26K+ records)   │
│  cards, card_images             │
│  portfolios, portfolio_cards    │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  eBay Selenium Scraper          │
│  + Graded Search Pass           │
│  + Confidence Scoring           │
│  + Grade Parser                 │
│                                 │
│  PokemonTCG API (images)        │
└─────────────────────────────────┘
```

## API Endpoints

| Endpoint | Description |
|----------|------------|
| `GET /api/sales/summary` | Sales summary per card with avg, min, max, volume |
| `GET /api/sales/<card>` | Individual sales for a card |
| `GET /api/sales/trend/<card>` | Daily price trend for charting |
| `GET /api/grades/<card>` | Price breakdown by grade (PSA 10, BGS 9.5, Raw, etc.) |
| `GET /api/images` | Card image URLs from database |
| `GET /api/model` | Price prediction model results |
| `GET /api/dynamics` | Market dynamics signals |
| `GET /api/portfolios` | Portfolio CRUD + valuation |
| `GET /api/portfolios/<id>/value` | Live portfolio valuation with P&L |

## Frontend Features

- **Gallery** — Browse all tracked cards with category tabs (Gold Stars, Prismatic Evolutions, 151, Base Set, etc.) or search any card ever printed via PokemonTCG API
- **Card Detail Panel** — Click any card for a slide-out panel with price stats, interactive price history chart with hover tooltips, grade breakdown, and recent sales list
- **Currents** — Top gainers and losers with time range filtering (24h, 7d, 30d)
- **Portfolio** — Track your collection with live P&L, search any card to add
- **Ticker** — Scrolling market tape with card images and prices

## Data Pipeline

1. **Selenium Scraper** opens Chrome, navigates to eBay sold listings
2. **Raw Search** — scrapes sold prices for each card (2 pages per card)
3. **Graded Search Pass** — for cards worth $50+, runs additional searches for PSA 10/9/8, BGS 10/9.5/9, CGC 10/9.5/9
4. **Grade Parser** — extracts PSA, BGS, CGC, ACE, AGS grades from listing titles
5. **Confidence Scoring** — rates each sale 0-100 based on listing type, bids, price, seller
6. **Title Filtering** — blacklists lots, bundles, fakes, proxies, foreign language cards
7. **Image Fetcher** — queries PokemonTCG API for card images, stores in database

## Running Locally

**Backend:**
```bash
cd Project1
python -m venv .venv
.venv\Scripts\activate
pip install flask flask-cors selenium beautifulsoup4 webdriver-manager scikit-learn pandas
python dashboard.py
```

**Frontend:**
```bash
cd Pokemetrics-Site
npm install
npm run dev
```

**Scraping:**
```bash
cd Project1
python sales_scraper.py      # Scrape all cards
python fetch_images.py       # Fetch card images
python import_sets.py        # Generate config for new sets
```

## Sample Data

| Card | Median | PSA 10 | BGS 10 | Raw | Sales |
|------|--------|--------|--------|-----|-------|
| Umbreon ex 187 SAR | $1,337 | $2,500 | $4,200 | $1,400 | 128 |
| Charizard Gold Star | $3,500 | — | — | $4,300 | 22 |
| Pikachu ex SIR | $1,410 | — | — | $1,500 | 120 |
| Umbreon Gold Star | $8,167 | — | — | $8,200 | 15 |
| Rayquaza Gold Star | $5,584 | — | — | $5,600 | 18 |

## Project Structure

```
Pokemon Project/
├── Project1/                    # Flask backend
│   ├── dashboard.py             # API server
│   ├── sales_scraper.py         # eBay Selenium scraper
│   ├── grade_parser.py          # PSA/BGS/CGC grade detection
│   ├── fetch_images.py          # PokemonTCG API image fetcher
│   ├── import_sets.py           # Set card list generator
│   ├── model_engine.py          # Price prediction model
│   ├── market_collector.py      # Market dynamics tracker
│   ├── collector.py             # eBay API collector
│   ├── portfolio.py             # Portfolio manager
│   └── pokemon_cards.db         # SQLite database
│
└── Pokemetrics-Site/            # React frontend
    ├── src/
    │   ├── routes/
    │   │   ├── index.tsx        # Home page
    │   │   ├── cards.tsx        # Gallery with categories
    │   │   ├── trends.tsx       # Currents / movers
    │   │   └── portfolio.tsx    # Portfolio tracker
    │   ├── components/
    │   │   ├── CardDetailPanel.tsx  # Slide-out detail view
    │   │   ├── PriceChart.tsx      # Interactive price chart
    │   │   ├── CardRow.tsx         # Card list row
    │   │   ├── Sparkline.tsx       # Mini chart
    │   │   └── Ticker.tsx          # Scrolling price tape
    │   └── lib/
    │       ├── api.ts           # Backend API client
    │       ├── use-market.ts    # React Query hooks
    │       ├── pokemontcg.ts    # PokemonTCG API client
    │       └── market-data.ts   # Card types
    └── .env                     # VITE_API_BASE_URL
```

## Built By

Kody Lai — Stats & Data Science, UCSB '26

## License

MIT
