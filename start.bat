@echo off
echo =======================================
echo  Pokemon Card Price Model - Setup
echo =======================================
echo.

REM Install dependencies
echo Installing Python dependencies...
pip install flask pandas scikit-learn numpy
echo.

REM Initialize DB with demo data (remove --demo for real eBay data)
echo Initializing database with demo data...
python collector.py --demo
echo.

REM Create a scheduled task to run collector every 4 hours
echo.
echo ── OPTIONAL: Auto-collect every 4 hours ──
echo To set up automatic eBay price collection:
echo   1. Set your eBay API keys:
echo      set EBAY_CLIENT_ID=your_id
echo      set EBAY_CLIENT_SECRET=your_secret
echo   2. Create a scheduled task:
echo      schtasks /create /tn "PokemonPriceCollector" /tr "python %cd%\collector.py" /sc HOURLY /mo 4
echo   3. To remove: schtasks /delete /tn "PokemonPriceCollector"
echo.

REM Start dashboard
echo =======================================
echo  Starting Dashboard
echo  Open: http://localhost:5000
echo =======================================
python dashboard.py
