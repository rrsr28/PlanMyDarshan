"""
TTD Darshan Crowd Explorer  (Streamlit)

Run:
    pip install streamlit plotly pandas
    streamlit run app.py

Put ttd_darshan_stats.csv next to this file, or upload it in the sidebar.
"""
import io
import os
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="TTD Crowd Explorer", page_icon="🛕", layout="wide")

MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
GREEN_RED = "RdYlGn_r"  # green = quiet, red = busy
DEFAULT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ttd_darshan_stats.csv")


# ───────────────────────── data ─────────────────────────
def _wait_hours(t):
    """Average of the posted Sarvadarshanam waiting time (hours) from the raw post text."""
    if not isinstance(t, str):
        return np.nan
    m = re.search(r"Sarvadarshanam[^0-9]{0,40}?(\d+)\s*(?:[-–to]+\s*(\d+))?\s*H", t, re.I)
    if not m:
        return np.nan
    a = float(m.group(1))
    b = float(m.group(2)) if m.group(2) else a
    return (a + b) / 2


@st.cache_data(show_spinner=False)
def load(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig", parse_dates=["date"])
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    for c in ["total_pilgrims", "tonsures", "hundi_cr", "laddu_lakh", "annaprasadam_lakh", "aswini_hospital"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["wait_h"] = df["raw_text"].map(_wait_hours) if "raw_text" in df else np.nan
    return df


def week_label(w):
    for y in (2026, 2025):
        try:
            s = pd.Timestamp.fromisocalendar(y, int(w), 1)
            return f"{s:%d %b} – {s + pd.Timedelta(days=6):%d %b}"
        except ValueError:
            continue
    return ""


# ───────────────────────── sidebar ─────────────────────────
st.sidebar.title("🛕 TTD Crowd Explorer")
up = st.sidebar.file_uploader("Upload ttd_darshan_stats.csv", type="csv")
if up is not None:
    raw = up.getvalue()
elif os.path.exists(DEFAULT_CSV):
    raw = open(DEFAULT_CSV, "rb").read()
else:
    st.title("🛕 TTD Crowd Explorer")
    st.info("Upload `ttd_darshan_stats.csv` in the sidebar (or place it next to app.py).")
    st.stop()

full = load(raw)
y_min, y_max = int(full.date.dt.year.min()), int(full.date.dt.year.max())

st.sidebar.markdown("### Filters")
yr_range = st.sidebar.slider(
    "Years to analyse", y_min, y_max, (max(y_min, 2023), y_max),
    help="Default starts at 2023: 2021 was heavily COVID-affected and Jan–Feb 2022 was still depressed (~32k–39k/day), which makes those months look falsely quiet.")
min_valid = st.sidebar.number_input("Treat totals below as bad data", 0, 50000, 5000, 500)
max_valid = st.sidebar.number_input("Treat totals above as bad data", 90000, 2_000_000, 150000, 10000)
normalize = st.sidebar.toggle(
    "Normalise by year", True,
    help="Divide each day by that year's average, so growth between years doesn't distort seasonal comparisons. "
         "1.00 = a normal day in that year; 0.90 = 10% quieter than normal.")
min_days = st.sidebar.slider("Min. days of data for a month/week to count", 3, 28, 20)
quiet_n = st.sidebar.slider("'Quiet' = quietest N months in a year", 2, 6, 4)

mask_ok = full.total_pilgrims.between(min_valid, max_valid)
bad = full[~mask_ok | full.total_pilgrims.isna()]
df = full[mask_ok].copy()
df["year"] = df.date.dt.year
df = df[df.year.between(*yr_range)].copy()
df["month"] = df.date.dt.month
df["dow"] = pd.Categorical(df.date.dt.day_name(), DOW, ordered=True)
df["woy"] = df.date.dt.isocalendar().week.astype(int)
df["iso_year"] = df.date.dt.isocalendar().year.astype(int)
df["rel"] = df.total_pilgrims / df.groupby("year").total_pilgrims.transform("mean")
VAL = "rel" if normalize else "total_pilgrims"
VAL_LABEL = "Crowd vs yearly avg (1.0 = normal)" if normalize else "Pilgrims per day"
FMT = ".2f" if normalize else ",.0f"
MVAL = "rel" if normalize else "avg"  # column to use in month-year / week-year tables

if df.empty:
    st.warning("No data in the selected range.")
    st.stop()

st.sidebar.caption(
    f"{len(df):,} days · {df.date.min():%d %b %Y} → {df.date.max():%d %b %Y} · "
    f"{len(bad)} suspect rows ignored")

# ───────────────────────── shared aggregates ─────────────────────────
# month x year
my = (df.groupby(["year", "month"])
        .agg(avg=("total_pilgrims", "mean"), rel=("rel", "mean"), n=("date", "count"))
        .reset_index())
my = my[my.n >= min_days].copy()
my["rank"] = my.groupby("year")[MVAL].rank(method="min")
my["n_in_year"] = my.groupby("year")["month"].transform("count")
my["pct"] = np.where(my.n_in_year > 1, (my["rank"] - 1) / (my.n_in_year - 1), 0.5)
my["is_quiet"] = my["rank"] <= quiet_n

# week of year x year
wy = (df.groupby(["iso_year", "woy"])
        .agg(avg=("total_pilgrims", "mean"), rel=("rel", "mean"), n=("date", "count"))
        .reset_index())
wy = wy[wy.n >= max(4, min_days // 4)]
wk = (wy.groupby("woy").agg(avg=("avg", "mean"), rel=("rel", "mean"),
                            rel_min=("rel", "min"), rel_max=("rel", "max"),
                            years=("iso_year", "nunique")).reset_index())
wk["dates"] = wk.woy.map(week_label)

mon = (df.groupby("month").agg(avg=("total_pilgrims", "mean"), median=("total_pilgrims", "median"),
                                rel=("rel", "mean"), std=("rel", "std"),
                                lo=("total_pilgrims", "min"), hi=("total_pilgrims", "max"),
                                days=("date", "count")).reset_index())
mon["name"] = mon.month.map(lambda m: MON[m - 1])

# ───────────────────────── header + tabs ─────────────────────────
st.title("🛕 Tirumala Darshan — when is it least crowded?")
tabs = st.tabs(["📌 Summary", "📅 Best months", "🗓️ Best weeks", "📈 Timelines",
                "🔥 Heatmaps", "🎯 Consistency & best month/year", "📊 Other stats", "🧹 Data"])

# ═════════ Summary ═════════
with tabs[0]:
    q_months = mon.nsmallest(3, "rel")
    q_weeks = wk.nsmallest(3, "rel")
    wd = df.groupby("dow", observed=True)[VAL].mean()
    best_dow = wd.idxmin()
    c = st.columns(4)
    c[0].metric("Avg pilgrims / day", f"{df.total_pilgrims.mean():,.0f}")
    c[1].metric("Quietest month", MON[int(q_months.iloc[0].month) - 1],
                f"{q_months.iloc[0].avg:,.0f}/day", delta_color="off")
    c[2].metric("Quietest week", q_weeks.iloc[0].dates, f"{q_weeks.iloc[0].avg:,.0f}/day", delta_color="off")
    c[3].metric("Quietest weekday", best_dow, f"{df[df.dow == best_dow].total_pilgrims.mean():,.0f}/day",
                delta_color="off")

    left, right = st.columns(2)
    with left:
        st.subheader("Top 5 quietest weeks")
        t = wk.nsmallest(5, "rel")[["woy", "dates", "avg", "rel", "years"]]
        t.columns = ["ISO week", "Dates (approx.)", "Avg/day", "vs normal", "Years of data"]
        st.dataframe(t.style.format({"Avg/day": "{:,.0f}", "vs normal": "{:.2f}"}),
                     hide_index=True, width="stretch")
    with right:
        st.subheader("Top 5 busiest weeks")
        t = wk.nlargest(5, "rel")[["woy", "dates", "avg", "rel", "years"]]
        t.columns = ["ISO week", "Dates (approx.)", "Avg/day", "vs normal", "Years of data"]
        st.dataframe(t.style.format({"Avg/day": "{:,.0f}", "vs normal": "{:.2f}"}),
                     hide_index=True, width="stretch")

    st.subheader("Quietest days (excluding the extremes noted below)")
    low = df.nsmallest(10, "total_pilgrims")[["date", "dow", "total_pilgrims"]]
    low.columns = ["Date", "Weekday", "Pilgrims"]
    st.dataframe(low.style.format({"Pilgrims": "{:,.0f}", "Date": "{:%d %b %Y}"}),
                 hide_index=True, width="stretch")
    st.caption("⚠️ Very low outliers (e.g. ~27k on 7 Sep 2025 and 3 Mar 2026) coincide with lunar eclipses, when the "
               "temple closes for part of the day. They're not a reliable 'quiet day' to aim for.")

# ═════════ Best months ═════════
with tabs[1]:
    st.subheader("Average crowd by calendar month")
    metric = st.radio("Show", ["Average pilgrims/day", "Median pilgrims/day", "Relative to year"],
                      horizontal=True)
    col = {"Average pilgrims/day": "avg", "Median pilgrims/day": "median", "Relative to year": "rel"}[metric]
    d = mon.sort_values("month")
    colors = px.colors.sample_colorscale(GREEN_RED, (d[col] - d[col].min()) / (d[col].max() - d[col].min() + 1e-9))
    fig = go.Figure(go.Bar(x=d.name, y=d[col], marker_color=colors,
                           text=d[col].map(lambda v: f"{v:.2f}" if col == "rel" else f"{v/1000:.1f}k"),
                           textposition="outside"))
    fig.update_layout(yaxis_title=metric, height=450, margin=dict(t=30))
    st.plotly_chart(fig, width="stretch")
    t = d.sort_values("rel")[["name", "avg", "median", "rel", "lo", "hi", "days"]]
    t.columns = ["Month", "Avg/day", "Median/day", "vs normal", "Lowest day", "Highest day", "Days"]
    st.markdown("**Ranked quietest → busiest**")
    st.dataframe(t.style.format({"Avg/day": "{:,.0f}", "Median/day": "{:,.0f}", "vs normal": "{:.2f}",
                                 "Lowest day": "{:,.0f}", "Highest day": "{:,.0f}"}),
                 hide_index=True, width="stretch")

# ═════════ Best weeks ═════════
with tabs[2]:
    st.subheader("Crowd level by week of the year")
    topn = st.slider("Highlight the N quietest weeks", 3, 15, 8)
    w = wk.sort_values("woy").copy()
    qset = set(w.nsmallest(topn, "rel").woy)
    w["tag"] = np.where(w.woy.isin(qset), "Quietest", "Other")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=w.woy, y=w.rel_max, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=w.woy, y=w.rel_min, fill="tonexty", line=dict(width=0),
                             fillcolor="rgba(120,120,120,.15)", name="Range across years"))
    fig.add_trace(go.Scatter(x=w.woy, y=w.rel, mode="lines", line=dict(color="#4c78a8"), name="Average",
                             customdata=w.dates, hovertemplate="Week %{x} (%{customdata})<br>%{y:.2f}<extra></extra>"))
    q = w[w.tag == "Quietest"]
    fig.add_trace(go.Scatter(x=q.woy, y=q.rel, mode="markers", marker=dict(color="green", size=10),
                             name="Quietest", customdata=q.dates,
                             hovertemplate="Week %{x} (%{customdata})<br>%{y:.2f}<extra></extra>"))
    fig.add_hline(y=1, line_dash="dash", line_color="gray")
    fig.update_layout(height=470, xaxis_title="ISO week of year", yaxis_title="Crowd vs yearly avg (1.0 = normal)")
    st.plotly_chart(fig, width="stretch")
    t = w.sort_values("rel")[["woy", "dates", "avg", "rel", "rel_min", "rel_max", "years"]]
    t.columns = ["ISO week", "Dates (approx.)", "Avg/day", "vs normal", "Best year", "Worst year", "Years"]
    st.dataframe(t.style.format({"Avg/day": "{:,.0f}", "vs normal": "{:.2f}", "Best year": "{:.2f}",
                                 "Worst year": "{:.2f}"}), hide_index=True, width="stretch", height=420)
    st.caption("'Best year / Worst year' = the lowest and highest value this week has had in any single year. "
               "A narrow gap means the week is reliably that quiet/busy.")

# ═════════ Timelines ═════════
with tabs[3]:
    st.subheader("Monthly timeline")
    mt = df.groupby(df.date.dt.to_period("M")).agg(avg=("total_pilgrims", "mean"), n=("date", "count")).reset_index()
    mt = mt[mt.n >= min_days]
    mt["date"] = mt.date.dt.to_timestamp()
    fig = px.line(mt, x="date", y="avg", markers=True, labels={"avg": "Avg pilgrims/day", "date": ""})
    lowm = mt.nsmallest(5, "avg")
    fig.add_trace(go.Scatter(x=lowm.date, y=lowm.avg, mode="markers", marker=dict(color="green", size=12),
                             name="5 quietest months"))
    fig.update_layout(height=400)
    st.plotly_chart(fig, width="stretch")

    st.subheader("Month-by-month, one line per year")
    d = my.copy()
    d["Month"] = d.month.map(lambda m: MON[m - 1])
    fig = px.line(d, x="Month", y=MVAL, color=d.year.astype(str), markers=True,
                  category_orders={"Month": MON}, labels={MVAL: VAL_LABEL, "color": "Year"})
    fig.update_layout(height=420)
    st.plotly_chart(fig, width="stretch")

    st.subheader("Weekly timeline")
    wt = df.set_index("date").total_pilgrims.resample("W").agg(["mean", "count"])
    wt = wt[wt["count"] >= 4].reset_index()
    fig = px.line(wt, x="date", y="mean", labels={"mean": "Avg pilgrims/day", "date": ""})
    lw = wt.nsmallest(10, "mean")
    fig.add_trace(go.Scatter(x=lw.date, y=lw["mean"], mode="markers", marker=dict(color="green", size=9),
                             name="10 quietest weeks"))
    fig.update_layout(height=400)
    st.plotly_chart(fig, width="stretch")

    st.subheader("Daily data with rolling average")
    win = st.slider("Rolling window (days)", 7, 90, 30)
    s = df.set_index("date").total_pilgrims
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", line=dict(width=.7, color="#bbb"), name="Daily"))
    fig.add_trace(go.Scatter(x=s.index, y=s.rolling(win, center=True, min_periods=win // 2).mean(),
                             line=dict(width=2.5, color="#e45756"), name=f"{win}-day avg"))
    fig.update_layout(height=420, yaxis_title="Pilgrims/day")
    st.plotly_chart(fig, width="stretch")

# ═════════ Heatmaps ═════════
with tabs[4]:
    st.subheader("Month × year")
    p = my.pivot(index="year", columns="month", values=MVAL)
    p = p.reindex(columns=range(1, 13))
    p.columns = MON
    fig = px.imshow(p, color_continuous_scale=GREEN_RED, aspect="auto", text_auto=FMT,
                    labels=dict(color=VAL_LABEL))
    fig.update_layout(height=140 + 55 * len(p))
    st.plotly_chart(fig, width="stretch")

    st.subheader("Week of year × year")
    p = wy.pivot(index="iso_year", columns="woy", values="rel" if normalize else "avg")
    fig = px.imshow(p, color_continuous_scale=GREEN_RED, aspect="auto", labels=dict(x="ISO week", y="Year",
                    color=VAL_LABEL))
    fig.update_xaxes(dtick=2)
    fig.update_layout(height=150 + 50 * len(p))
    st.plotly_chart(fig, width="stretch")
    st.caption("Vertical green bands = weeks that are quiet in *every* year; vertical red bands = reliably busy.")

    st.subheader("Weekday × month")
    p = df.pivot_table(index="dow", columns="month", values=VAL, aggfunc="mean", observed=True)
    p = p.reindex(index=DOW, columns=range(1, 13))
    p.columns = MON
    fig = px.imshow(p, color_continuous_scale=GREEN_RED, aspect="auto", text_auto=FMT,
                    labels=dict(color=VAL_LABEL))
    fig.update_layout(height=450)
    st.plotly_chart(fig, width="stretch")

    st.subheader("Weekday × week of year")
    p = df.pivot_table(index="dow", columns="woy", values=VAL, aggfunc="mean", observed=True).reindex(DOW)
    fig = px.imshow(p, color_continuous_scale=GREEN_RED, aspect="auto", labels=dict(x="ISO week", color=VAL_LABEL))
    fig.update_layout(height=350)
    st.plotly_chart(fig, width="stretch")

# ═════════ Consistency ═════════
with tabs[5]:
    st.subheader("🎯 Which months are consistently quiet?")
    st.write(f"For each year the months are ranked from quietest to busiest. A month is **quiet** in a year if it "
             f"is one of that year's **{quiet_n} quietest** months (change in the sidebar). Months with fewer than "
             f"{min_days} days of data are skipped, so a partial year (like the current one) only ranks the months it has.")

    g = my.groupby("month").agg(
        years=("year", "nunique"),
        quiet_years=("is_quiet", "sum"),
        avg_rank=("rank", "mean"),
        best_rank=("rank", "min"),
        worst_rank=("rank", "max"),
        avg_pct=("pct", "mean"),
        mean_val=(MVAL, "mean"),
        std_val=(MVAL, "std"),
        avg=("avg", "mean"),
    ).reset_index()
    g["Month"] = g.month.map(lambda m: MON[m - 1])
    g["quiet_share"] = g.quiet_years / g.years
    g["consistency"] = g.quiet_share  # share of years in the quiet group
    g = g.sort_values(["quiet_share", "avg_pct"], ascending=[False, True])

    def verdict(r):
        if r.quiet_share == 1:
            return "✅ Quiet every year"
        if r.quiet_share >= .75:
            return "🟢 Usually quiet"
        if r.quiet_share >= .4:
            return "🟡 Mixed"
        if r.quiet_share > 0:
            return "🟠 Rarely quiet"
        return "🔴 Never quiet"
    g["Verdict"] = g.apply(verdict, axis=1)

    show = g[["Month", "Verdict", "quiet_years", "years", "avg_rank", "best_rank", "worst_rank", "avg", "std_val"]].copy()
    show.columns = ["Month", "Verdict", "Quiet in (yrs)", "Of (yrs)", "Avg rank", "Best rank", "Worst rank",
                    "Avg/day", "Variability (std)"]
    st.dataframe(show.style.format({"Avg rank": "{:.1f}", "Avg/day": "{:,.0f}", "Variability (std)": "{:.3f}"}),
                 hide_index=True, width="stretch")
    st.caption("Rank 1 = quietest month of that year. 'Variability' is how much that month's level swings from year "
               "to year (lower = more predictable).")

    cL, cR = st.columns(2)
    with cL:
        st.markdown("**Rank of each month in each year** (1 = quietest)")
        p = my.pivot(index="year", columns="month", values="rank").reindex(columns=range(1, 13))
        p.columns = MON
        fig = px.imshow(p, color_continuous_scale=GREEN_RED, aspect="auto", text_auto=".0f",
                        labels=dict(color="Rank"))
        fig.update_layout(height=140 + 55 * len(p))
        st.plotly_chart(fig, width="stretch")
    with cR:
        st.markdown("**Average vs. year-to-year swing**")
        fig = px.scatter(g, x="avg_rank", y="std_val", text="Month", size_max=18,
                         labels={"avg_rank": "Average rank (lower = quieter)",
                                 "std_val": "Variability (lower = more consistent)"})
        fig.update_traces(textposition="top center", marker=dict(size=12, color="#4c78a8"))
        fig.update_layout(height=140 + 55 * len(p))
        st.plotly_chart(fig, width="stretch")
        st.caption("Bottom-left = quiet *and* predictable: the safest months to pick.")

    st.divider()
    st.subheader("🏆 Quietest month in each year")
    rows = []
    for y, grp in my.groupby("year"):
        grp = grp.sort_values(MVAL)
        top = grp.head(3)
        busiest = grp.iloc[-1]
        rows.append({
            "Year": y,
            "Quietest": MON[int(top.iloc[0].month) - 1],
            "Avg/day": top.iloc[0].avg,
            "2nd": MON[int(top.iloc[1].month) - 1] if len(top) > 1 else "",
            "3rd": MON[int(top.iloc[2].month) - 1] if len(top) > 2 else "",
            "Busiest": MON[int(busiest.month) - 1],
            "Busiest avg/day": busiest.avg,
            "Months counted": len(grp),
        })
    best = pd.DataFrame(rows)
    st.dataframe(best.style.format({"Avg/day": "{:,.0f}", "Busiest avg/day": "{:,.0f}"}),
                 hide_index=True, width="stretch")
    st.caption("When 'normalise by year' is on, months are ranked by crowd relative to that year's average; "
               "'Avg/day' is always the raw average pilgrims/day.")

    d = my.copy()
    d["Month"] = d.month.map(lambda m: MON[m - 1])
    d["Year"] = d.year.astype(str)
    d["Quietest"] = d.groupby("year")[MVAL].transform("min") == d[MVAL]
    fig = px.bar(d, x="Month", y="avg", facet_col="Year", facet_col_wrap=3, color="Quietest",
                 color_discrete_map={True: "#2ca02c", False: "#9ecae1"},
                 category_orders={"Month": MON}, labels={"avg": "Avg/day"})
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    fig.update_layout(height=250 * int(np.ceil(d.year.nunique() / 3)), showlegend=False)
    st.plotly_chart(fig, width="stretch")

# ═════════ Other stats ═════════
with tabs[6]:
    opts = {"Tonsures": "tonsures", "Hundi collection (₹ crore)": "hundi_cr", "Laddu sales (lakh)": "laddu_lakh",
            "Annaprasadam (lakh)": "annaprasadam_lakh", "Aswini hospital patients": "aswini_hospital",
            "Free-darshan wait (hours)": "wait_h"}
    opts = {k: v for k, v in opts.items() if v in df and df[v].notna().sum() > 30}
    pick = st.selectbox("Metric", list(opts))
    col = opts[pick]
    a, b = st.columns(2)
    with a:
        m = df.groupby("month")[col].mean().reindex(range(1, 13))
        fig = px.bar(x=MON, y=m.values, labels={"x": "", "y": pick}, title=f"{pick} — average by month")
        st.plotly_chart(fig, width="stretch")
    with b:
        m = df.groupby("dow", observed=True)[col].mean()
        fig = px.bar(x=m.index.astype(str), y=m.values, labels={"x": "", "y": pick},
                     title=f"{pick} — average by weekday")
        st.plotly_chart(fig, width="stretch")
    s = df.set_index("date")[col]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", line=dict(width=.6, color="#bbb"), name="Daily"))
    fig.add_trace(go.Scatter(x=s.index, y=s.rolling(30, center=True, min_periods=15).mean(),
                             line=dict(width=2.5), name="30-day avg"))
    fig.update_layout(height=380, title=f"{pick} over time")
    st.plotly_chart(fig, width="stretch")

    st.subheader("Yearly summary")
    ys = df.groupby("year").total_pilgrims.agg(Days="count", Total="sum", Avg="mean", Median="median",
                                               Min="min", Max="max").reset_index()
    st.dataframe(ys.style.format({"Total": "{:,.0f}", "Avg": "{:,.0f}", "Median": "{:,.0f}",
                                  "Min": "{:,.0f}", "Max": "{:,.0f}", "year": "{}"}),
                 hide_index=True, width="stretch")
    num_cols = [c for c in ["total_pilgrims", "tonsures", "hundi_cr", "laddu_lakh", "annaprasadam_lakh",
                            "aswini_hospital", "wait_h"] if c in df]
    st.subheader("Correlations")
    cm = df[num_cols].corr().round(2)
    fig = px.imshow(cm, text_auto=True, color_continuous_scale="RdBu_r", zmin=-1, zmax=1, aspect="auto")
    fig.update_layout(height=450)
    st.plotly_chart(fig, width="stretch")

# ═════════ Data ═════════
with tabs[7]:
    st.subheader("Data quality")
    full_range = pd.date_range(full.date.min(), full.date.max())
    missing = full_range.difference(full.date)
    c = st.columns(3)
    c[0].metric("Rows in CSV", f"{len(full):,}")
    c[1].metric("Suspect rows ignored", len(bad))
    c[2].metric("Missing calendar days", len(missing))
    st.markdown("**Ignored rows** (outside the min/max thresholds in the sidebar)")
    st.dataframe(bad[["date", "total_pilgrims", "title"]], hide_index=True, width="stretch")
    if len(missing):
        with st.expander(f"{len(missing)} missing days"):
            st.write(", ".join(d.strftime("%d %b %Y") for d in missing))
    st.markdown("**Download**")
    st.download_button("Cleaned daily data (CSV)",
                       df.drop(columns=["raw_text"], errors="ignore").to_csv(index=False).encode(),
                       "ttd_clean.csv", "text/csv")
    st.download_button("Month × year summary (CSV)", my.to_csv(index=False).encode(), "month_year.csv", "text/csv")
    st.download_button("Week-of-year summary (CSV)", wk.to_csv(index=False).encode(), "weeks.csv", "text/csv")
