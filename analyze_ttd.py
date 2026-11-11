#!/usr/bin/env python3
"""
Analyze TTD darshan stats and find the least crowded times to visit.

    pip install pandas matplotlib seaborn
    python analyze_ttd.py ttd_darshan_stats.csv
    python analyze_ttd.py ttd_darshan_stats.csv --recent-from 2023   # plan using recent years only

Creates ./ttd_analysis/ with PNG charts, CSV tables and report.md
"""
import argparse, os, re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ap = argparse.ArgumentParser()
ap.add_argument("csv")
ap.add_argument("--recent-from", type=int, default=2023,
                help="year from which data is used for 'when should I go' advice "
                     "(2021-22 were COVID-affected, so they distort normal patterns)")
ap.add_argument("--min-valid", type=int, default=0,
                help="totals below this are treated as bad data (default 0: keep real low days such as COVID, eclipses)")
ap.add_argument("--keep-suspect", action="store_true",
                help="keep days the scraper flagged as questionable (title and post text disagree, repeated numbers)")
ap.add_argument("--max-valid", type=int, default=150000,
                help="totals above this are treated as bad data (e.g. a typo)")
ap.add_argument("--out", default="ttd_analysis")
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)
plt.rcParams.update({"figure.dpi": 130, "axes.grid": True, "grid.alpha": .3})

# ---------- load & clean ----------
df = pd.read_csv(args.csv, encoding="utf-8-sig", parse_dates=["date"])
df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
df["total_pilgrims"] = pd.to_numeric(df["total_pilgrims"], errors="coerce")
bad = df[(df.total_pilgrims.isna()) | (df.total_pilgrims < args.min_valid) | (df.total_pilgrims > args.max_valid)]
if "suspect" in df and not args.keep_suspect:
    bad = pd.concat([bad, df[df.suspect.fillna(False).astype(bool)]]).drop_duplicates("date")
bad.to_csv(f"{args.out}/suspect_rows.csv", index=False)
df = df.drop(bad.index)

# experimental: posted free-darshan wait (hours) from the scraper's wait_min / wait_max columns.
# TTD posts it for varying times of day and caps it at 24 H, so it is NOT used for any recommendation.
if {"wait_min", "wait_max"} <= set(df.columns):
    df["wait_h"] = (pd.to_numeric(df.wait_min, errors="coerce") + pd.to_numeric(df.wait_max, errors="coerce")) / 2
else:
    df["wait_h"] = np.nan

df["year"] = df.date.dt.year
df["month"] = df.date.dt.month
df["dow"] = df.date.dt.day_name()
df["woy"] = df.date.dt.isocalendar().week.astype(int)
df["doy"] = df.date.dt.dayofyear
df["is_weekend"] = df.date.dt.dayofweek >= 5
rec = df[df.year >= args.recent_from].copy()

DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
R = []  # report lines
def say(s=""): R.append(s)

# ---------- overall ----------
say(f"# TTD darshan analysis\n")
say(f"Data: {df.date.min().date()} to {df.date.max().date()}  ({len(df)} valid days, "
    f"{len(bad)} suspect rows removed -> see suspect_rows.csv)\n")
say(f"Planning window ('recent'): {args.recent_from}+  ({len(rec)} days)\n")

yr = df.groupby("year").total_pilgrims.agg(
    days="count", total="sum", daily_avg="mean", median="median", min="min", max="max").round(0)
yr.to_csv(f"{args.out}/yearly_summary.csv")
say("## Yearly summary\n"); say(yr.to_markdown()); say()

# ---------- extremes ----------
low = rec.nsmallest(20, "total_pilgrims")[["date", "dow", "total_pilgrims"]]
high = rec.nlargest(20, "total_pilgrims")[["date", "dow", "total_pilgrims"]]
low.to_csv(f"{args.out}/lowest_20_days.csv", index=False)
high.to_csv(f"{args.out}/highest_20_days.csv", index=False)
say("## 20 quietest days (recent window)\n"); say(low.to_markdown(index=False)); say()
say("## 20 busiest days (recent window)\n"); say(high.to_markdown(index=False)); say()

# ---------- day of week ----------
d = rec.groupby("dow").total_pilgrims.agg(["mean", "median"]).reindex(DOW).round(0)
d.to_csv(f"{args.out}/by_weekday.csv")
say("## By weekday (recent)\n"); say(d.to_markdown()); say()
fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(d.index, d["mean"], color=["#4c78a8"] * 5 + ["#e45756"] * 2)
ax.set_title("Average pilgrims by weekday"); ax.set_ylabel("pilgrims/day")
plt.xticks(rotation=30); plt.tight_layout(); plt.savefig(f"{args.out}/weekday.png"); plt.close()

# ---------- month ----------
m = rec.groupby("month").total_pilgrims.agg(["mean", "median", "min", "max"]).round(0)
m.index = [MON[i - 1] for i in m.index]
m.to_csv(f"{args.out}/by_month.csv")
say("## By month (recent)\n"); say(m.to_markdown()); say()
fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(m.index, m["mean"], color="#4c78a8")
ax.set_title("Average daily pilgrims by month"); ax.set_ylabel("pilgrims/day")
plt.tight_layout(); plt.savefig(f"{args.out}/month.png"); plt.close()

# ---------- year x month heatmap ----------
pv = df.pivot_table(index="year", columns="month", values="total_pilgrims", aggfunc="mean")
pv.columns = [MON[i - 1] for i in pv.columns]
pv.round(0).to_csv(f"{args.out}/year_month_matrix.csv")
fig, ax = plt.subplots(figsize=(10, 4 + .3 * len(pv)))
im = ax.imshow(pv.values, cmap="RdYlGn_r", aspect="auto")
ax.set_xticks(range(len(pv.columns))); ax.set_xticklabels(pv.columns)
ax.set_yticks(range(len(pv.index))); ax.set_yticklabels(pv.index); ax.grid(False)
for i in range(pv.shape[0]):
    for j in range(pv.shape[1]):
        v = pv.values[i, j]
        if not np.isnan(v): ax.text(j, i, f"{v/1000:.0f}k", ha="center", va="center", fontsize=8)
plt.colorbar(im, label="avg pilgrims/day"); ax.set_title("Average daily pilgrims: year x month (green = quiet)")
plt.tight_layout(); plt.savefig(f"{args.out}/heatmap_year_month.png"); plt.close()

# ---------- timeline ----------
s = df.set_index("date").total_pilgrims
fig, ax = plt.subplots(figsize=(13, 4.5))
ax.plot(s.index, s.values, lw=.5, alpha=.4, label="daily")
ax.plot(s.index, s.rolling(30, center=True, min_periods=15).mean(), lw=2, label="30-day avg")
ax.set_title("Daily pilgrims over time"); ax.legend(); ax.set_ylabel("pilgrims/day")
plt.tight_layout(); plt.savefig(f"{args.out}/timeline.png"); plt.close()

# ---------- BEST TIME TO GO: week-of-year across recent years ----------
# normalize each year by its own mean so that growth between years doesn't bias it
rec["rel"] = rec.total_pilgrims / rec.groupby("year").total_pilgrims.transform("mean")
wk = rec.groupby("woy").agg(avg=("total_pilgrims", "mean"), rel=("rel", "mean"),
                            years=("year", "nunique"), n=("date", "count"))
wk = wk[wk.n >= 4]
wk["approx_start"] = [pd.Timestamp.fromisocalendar(2025, int(w), 1).strftime("%d %b") for w in wk.index]
wk.round(2).to_csv(f"{args.out}/by_week_of_year.csv")
quiet = wk.nsmallest(10, "rel"); busy = wk.nlargest(10, "rel")
say("## Quietest weeks of the year (rel < 1 = quieter than that year's average)\n")
say(quiet[["approx_start", "avg", "rel", "years"]].round(2).to_markdown()); say()
say("## Busiest weeks of the year\n")
say(busy[["approx_start", "avg", "rel", "years"]].round(2).to_markdown()); say()
fig, ax = plt.subplots(figsize=(13, 4.5))
ax.plot(wk.index, wk["rel"], marker="o", ms=3)
ax.axhline(1, color="gray", ls="--")
ax.fill_between(wk.index, wk["rel"], 1, where=wk["rel"] < 1, color="green", alpha=.2)
ax.fill_between(wk.index, wk["rel"], 1, where=wk["rel"] >= 1, color="red", alpha=.15)
ax.set_xlabel("ISO week of year"); ax.set_ylabel("crowd vs yearly avg (1.0 = normal)")
ax.set_title(f"When is it quiet? (green = below average, {args.recent_from}+ data)")
plt.tight_layout(); plt.savefig(f"{args.out}/best_weeks.png"); plt.close()

# ---------- best 7-day windows per year + weekday-only ----------
say("## Quietest 7-day window in each year\n")
rows = []
for y, g in df.groupby("year"):
    r7 = g.set_index("date").total_pilgrims.rolling("7D").mean()
    r7 = r7[r7.index >= g.date.min() + pd.Timedelta(days=6)]
    if len(r7):
        e = r7.idxmin(); rows.append((y, (e - pd.Timedelta(days=6)).date(), e.date(), round(r7.min())))
bw = pd.DataFrame(rows, columns=["year", "from", "to", "avg_per_day"])
bw.to_csv(f"{args.out}/quietest_7day_by_year.csv", index=False)
say(bw.to_markdown(index=False)); say()

# ---------- best weekday x month combos ----------
combo = rec.pivot_table(index="dow", columns="month", values="rel", aggfunc="mean").reindex(DOW)
combo.columns = [MON[i - 1] for i in combo.columns]
fig, ax = plt.subplots(figsize=(10, 4))
im = ax.imshow(combo.values, cmap="RdYlGn_r", aspect="auto")
ax.set_xticks(range(len(combo.columns))); ax.set_xticklabels(combo.columns)
ax.set_yticks(range(7)); ax.set_yticklabels(DOW); ax.grid(False)
for i in range(7):
    for j in range(combo.shape[1]):
        v = combo.values[i, j]
        if not np.isnan(v): ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8)
plt.colorbar(im, label="relative crowd"); ax.set_title("Weekday x month (green = quiet)")
plt.tight_layout(); plt.savefig(f"{args.out}/heatmap_weekday_month.png"); plt.close()

# ---------- other stats ----------
for col, label in [("tonsures", "Tonsures"), ("hundi_cr", "Hundi (crore)"),
                   ("laddu_lakh", "Laddus (lakh)")]:
    if col in df and df[col].notna().sum() > 30:
        fig, ax = plt.subplots(figsize=(13, 3.8))
        t = df.set_index("date")[col]
        ax.plot(t.index, t.values, lw=.4, alpha=.4)
        ax.plot(t.index, t.rolling(30, center=True, min_periods=15).mean(), lw=2)
        ax.set_title(f"{label} over time"); plt.tight_layout()
        plt.savefig(f"{args.out}/{col}.png"); plt.close()

if "hundi_cr" in df and df.hundi_cr.notna().any():
    c = df[["total_pilgrims", "hundi_cr", "tonsures", "laddu_lakh"]].corr().round(2)
    say("## Correlations\n"); say(c.to_markdown()); say()

if df.wait_h.notna().sum() > 30:
    w = rec.groupby("month").wait_h.mean().round(1); w.index = [MON[i - 1] for i in w.index]
    say("## Posted free-darshan wait by month (hours; EXPERIMENTAL, varies by time of day, capped at 24 H)\n"); say(w.to_markdown()); say()
    fig, ax = plt.subplots(figsize=(9, 4)); ax.bar(w.index, w.values, color="#f58518")
    ax.set_title("Average free-darshan waiting time (hours)"); plt.tight_layout()
    plt.savefig(f"{args.out}/wait_by_month.png"); plt.close()
    tc = rec[["total_pilgrims", "wait_h"]].corr().iloc[0, 1]
    say(f"Correlation between crowd and waiting time: {tc:.2f}\n")

# ---------- plain-language recommendation ----------
qm = rec.groupby("month").rel.mean().nsmallest(3).index
qd = rec.groupby("dow").rel.mean().nsmallest(3).index
say("## Quick take (auto-generated)\n")
say(f"- Quietest months: {', '.join(MON[i-1] for i in qm)}")
say(f"- Quietest weekdays: {', '.join(qd)}")
say(f"- Quietest weeks: starting around {', '.join(quiet.approx_start.head(5))}")
say("- Avoid the weeks listed as busiest; they usually line up with festivals, "
    "school holidays and long weekends (check against the Hindu/Telugu calendar).")
open(f"{args.out}/report.md", "w").write("\n".join(R))
print("\n".join(R[-8:]))
print(f"\nDone. Open the '{args.out}' folder.")