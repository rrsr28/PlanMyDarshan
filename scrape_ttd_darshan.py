#!/usr/bin/env python3
"""
Scrape TTD daily darshan stats from https://news.tirumala.org/category/darshan/
Page 1 = newest, last page = oldest. Walks pages until it passes START_YEAR.

Usage:
    pip install requests beautifulsoup4
    python scrape_ttd_darshan.py                 # 2021 -> today
    python scrape_ttd_darshan.py --start-year 2019 --out ttd.csv

Output columns:
    date            ISO date the stat is FOR (from the post title)
    year_inferred   True if the title had no year and it was inferred
    total_pilgrims  integer
    tonsures        integer (blank if missing)
    hundi_cr        crores (float)
    laddu_lakh      lakhs (float)
    annaprasadam_lakh, aswini_hospital
    title, url, page, raw_text   (kept so nothing is lost; clean up later)
"""
import argparse, csv, re, sys, time
from datetime import date
import requests
from bs4 import BeautifulSoup

BASE = "https://news.tirumala.org/category/darshan/page/{}/"
HEADERS = {"User-Agent": "Mozilla/5.0 (research scraper; contact: you@example.com)"}

DATE_RE = re.compile(r"(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?")
TOTAL_RE = re.compile(r":\s*([\d,]+)\s*$")


def num(pattern, text):
    m = re.search(pattern, text, re.I)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def fetch(page, retries=4):
    for attempt in range(retries):
        try:
            r = requests.get(BASE.format(page), headers=HEADERS, timeout=30)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            print(f"  page {page} attempt {attempt+1} failed: {e}", file=sys.stderr)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"giving up on page {page}")


def parse_page(html, page):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for h2 in soup.find_all("h2"):
        a = h2.find("a", href=True)
        if not a or "news.tirumala.org" not in a["href"]:
            continue
        title = a.get_text(" ", strip=True)
        if "darshan" not in title.lower() and "pilgrim" not in title.lower():
            continue
        # body text: article container if present, else text up to next h2
        art = h2.find_parent("article")
        if art:
            body = art.get_text(" ", strip=True)
        else:
            parts = []
            for sib in h2.find_all_next():
                if sib.name == "h2":
                    break
                parts.append(sib.get_text(" ", strip=True))
            body = " ".join(parts)
        rows.append({"title": title, "url": a["href"], "page": page, "raw_text": body})
    return rows


def enrich(row):
    t = row["title"]
    m = DATE_RE.search(t)
    row["_d"], row["_m"], row["_y"] = None, None, None
    if m:
        row["_d"], row["_m"] = int(m.group(1)), int(m.group(2))
        if m.group(3):
            y = int(m.group(3))
            row["_y"] = y + 2000 if y < 100 else y
    tm = TOTAL_RE.search(t)
    row["total_pilgrims"] = int(tm.group(1).replace(",", "")) if tm else None
    # fallback: try body if title lacks the number
    if row["total_pilgrims"] is None:
        bm = re.search(r"had darshan on[^:]*:\s*([\d,]+)", row["raw_text"], re.I)
        if bm:
            row["total_pilgrims"] = int(bm.group(1).replace(",", ""))
    b = row["raw_text"]
    row["tonsures"] = num(r"Tonsures\s*:?\s*([\d,]+)", b)
    row["hundi_cr"] = num(r"Hundi[^:\d]*:?\s*([\d.]+)\s*CR", b)
    row["laddu_lakh"] = num(r"Laddu sale\W*([\d.]+)\s*Lac", b)
    row["annaprasadam_lakh"] = num(r"Annaprasadam\W*([\d.]+)\s*Lac", b)
    row["aswini_hospital"] = num(r"A[sc]?hwini hospital\W*([\d,]+)", b) or num(r"Aswini hospital\W*([\d,]+)", b)
    return row


def fill_years(rows):
    """Rows are newest -> oldest. Where the title has no year, infer it:
    walk backwards in time; whenever the month jumps UP vs the previous
    (newer) row, we crossed a New Year, so year -= 1."""
    cur_year, prev_month = None, None
    for r in rows:
        if r["_y"]:
            cur_year, prev_month = r["_y"], r["_m"]
            r["year_inferred"] = False
            continue
        r["year_inferred"] = True
        if cur_year is None or r["_m"] is None:
            continue
        if prev_month is not None and r["_m"] > prev_month:
            cur_year -= 1
        prev_month = r["_m"]
        r["_y"] = cur_year
    for r in rows:
        try:
            r["date"] = date(r["_y"], r["_m"], r["_d"]).isoformat()
        except (TypeError, ValueError):
            r["date"] = ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-year", type=int, default=2021)
    ap.add_argument("--out", default="ttd_darshan_stats.csv")
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--max-pages", type=int, default=700)
    args = ap.parse_args()

    all_rows = []
    for p in range(1, args.max_pages + 1):
        html = fetch(p)
        if html is None:
            print(f"page {p}: 404, finished."); break
        rows = [enrich(r) for r in parse_page(html, p)]
        all_rows.extend(rows)
        print(f"page {p}: {len(rows)} rows (total {len(all_rows)})")
        fill_years(all_rows)  # cheap; lets us check the year as we go
        dated = [r for r in rows if r.get("_y")]
        if dated and min(r["_y"] for r in dated) < args.start_year and \
           all(r["_y"] < args.start_year for r in dated):
            print(f"Passed {args.start_year}; stopping."); break
        time.sleep(args.delay)

    fill_years(all_rows)
    all_rows = [r for r in all_rows if r["date"] and int(r["date"][:4]) >= args.start_year]

    # de-duplicate by date (keep first = newest post)
    seen, out = set(), []
    for r in all_rows:
        if r["date"] in seen:
            continue
        seen.add(r["date"]); out.append(r)

    cols = ["date", "year_inferred", "total_pilgrims", "tonsures", "hundi_cr", "laddu_lakh",
            "annaprasadam_lakh", "aswini_hospital", "title", "url", "page", "raw_text"]
    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(out)
    print(f"Wrote {len(out)} rows to {args.out}")

    # gap report
    from datetime import timedelta
    ds = sorted(date.fromisoformat(r["date"]) for r in out)
    if ds:
        have = set(ds); d = ds[0]; missing = []
        while d <= ds[-1]:
            if d not in have: missing.append(d.isoformat())
            d += timedelta(days=1)
        print(f"Missing days in range: {len(missing)}")
        if missing: print("  e.g.", ", ".join(missing[:15]))


if __name__ == "__main__":
    main()
