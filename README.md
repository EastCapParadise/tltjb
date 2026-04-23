# TLTJB — The League That Johnny Built

## Setup

1. Clone this repo
2. Install deps: `pip install pandas openpyxl requests`
3. Place the Excel file in `data/`
4. Update ESPN cookies in `config.json` if needed
5. Run the data pipeline: `python scripts/build_data.py`
6. Open `index.html` locally, or push to GitHub Pages

## Updating the Site

After each season (or mid-season for ESPN live data):
```bash
python scripts/build_data.py
git add data/data.json
git commit -m "Update data - YYYY season"
git push
```

## File Structure

```
tltjb/
├── index.html          # Homepage
├── seasons.html        # Season hub
├── owners.html         # Owner profiles
├── head-to-head.html   # Rivalry page
├── playoffs.html       # Playoffs & championships
├── records.html        # Records & milestones
├── assets/
│   ├── style.css       # All styles
│   ├── utils.js        # Shared JS utilities
│   ├── nav.js          # Nav/footer injection
│   └── images/
│       └── logo.png
├── data/
│   ├── TLTJB_historical_stats_Dec25.xlsx
│   └── data.json       # Generated — do not edit manually
├── scripts/
│   └── build_data.py   # Data pipeline
└── config.json         # League config
```

## GitHub Pages

Site is hosted at: https://eastcapparadise.github.io/tltjb
