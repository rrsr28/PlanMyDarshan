# PlanMyDarshan

Interactive Streamlit dashboard of daily Tirumala (TTD) darshan statistics, 2021 to present,
built to find the least crowded months and weeks to plan your visit.

Data source: https://news.tirumala.org/category/darshan/

## Run locally
    pip install -r requirements.txt
    streamlit run app.py

## Update the data
    python scripts/scrape_ttd_darshan.py --out ttd_darshan_stats.csv
