"""
PlanMyDarshan — when is Tirumala least crowded?  (Streamlit)

Run:
    pip install -r requirements.txt
    streamlit run app.py

Keep ttd_darshan_stats.csv next to this file (or upload it in the sidebar).
"""
import calendar
import io
import os
import re

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

st.set_page_config(page_title="PlanMyDarshan · Least crowded times at Tirumala", page_icon="🛕",
                   layout="wide", initial_sidebar_state="collapsed")

MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_FULL = list(calendar.month_name)[1:]
DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DEFAULT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ttd_darshan_stats.csv")

# crowd level palette: label, background, text colour
LEVELS = [("Quiet", "#2E9E6B", "#FFFFFF"), ("Light", "#9CCB5A", "#1F2D12"), ("Moderate", "#F4D35E", "#3A2E05"),
          ("Busy", "#F2994A", "#FFFFFF"), ("Very busy", "#D64545", "#FFFFFF")]
CROWD_SCALE = [c[1] for c in LEVELS]
# Fixed scale (pilgrims per day), chosen from the last 12 months of data (about 76k on an average day:
# the 10th/40th/60th/90th percentiles are roughly 65k/73k/78k/86k). Not percentiles of the shown days, so if
# every day is busy the colours say so.
LEVEL_CUTS = [65_000, 72_000, 80_000, 88_000]
LEVEL_RANGES = ["under 65k", "65–72k", "72–80k", "80–88k", "88k and above"]
LEGEND = "".join(f'<span><i style="background:{bg}"></i>{n} · {rg}</span>'
                 for (n, bg, _), rg in zip(LEVELS, LEVEL_RANGES))
# A month with fewer days than this is shown on charts but not ranked against full months.
PARTIAL_DAYS = 20

# ───────────────────────── theme: CSS + plotly template ─────────────────────────
pio.templates["tirumala"] = go.layout.Template(layout=dict(
    font=dict(family="Inter, sans-serif", color="#2B1B12", size=13),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    colorway=["#B5471B", "#E8801A", "#C99A2E", "#7A1F1F", "#2E9E6B", "#4C78A8", "#8C6D62", "#D64545"],
    xaxis=dict(gridcolor="#EADFCB", linecolor="#D9CBB2", zerolinecolor="#EADFCB"),
    yaxis=dict(gridcolor="#EADFCB", linecolor="#D9CBB2", zerolinecolor="#EADFCB"),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
    hoverlabel=dict(font_family="Inter, sans-serif"),
    margin=dict(t=40, r=20, l=10, b=10),
))
pio.templates.default = "tirumala"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=Inter:wght@400;500;600;700&display=swap');
:root{--ink:#2B1B12;--muted:#7A675A;--saffron:#E8801A;--maroon:#7A1F1F;--gold:#C99A2E;--cream:#FBF7F0;--sand:#F3EADB;--line:#EADFCB;}
html, body, .stApp, .stMarkdown, p, li, label, input, textarea, [data-testid="stMetricValue"]{font-family:'Inter',sans-serif;}
.stApp{background:radial-gradient(1100px 520px at 90% -8%, #FDE6C4 0%, rgba(253,230,196,0) 62%),
       radial-gradient(900px 400px at -10% 30%, #F9E3D6 0%, rgba(249,227,214,0) 60%), var(--cream);color:var(--ink);}
.block-container{padding-top:1.2rem;padding-bottom:3rem;max-width:1180px;}
[data-testid="stHeader"]{background:transparent;}
h1,h2,h3{font-family:'Fraunces',serif !important;color:var(--maroon) !important;letter-spacing:-.01em;}
h2{font-size:1.7rem !important;margin-top:.6rem !important;}
[data-testid="stSidebar"]{background:var(--sand);}
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid var(--line);flex-wrap:wrap;}
.stTabs [data-baseweb="tab"]{height:46px;border-radius:12px 12px 0 0;padding:0 16px;color:var(--muted);font-weight:600;}
.stTabs [aria-selected="true"]{color:var(--maroon);background:rgba(232,128,26,.10);}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:16px;padding:14px 18px;box-shadow:0 4px 18px rgba(122,31,31,.05);}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:14px;overflow:hidden;}
.stButton>button,.stDownloadButton>button{border-radius:12px;border:1px solid var(--line);font-weight:600;}

/* hero */
.hero{position:relative;overflow:hidden;border-radius:26px;padding:44px 44px 36px;margin-bottom:26px;color:#fff;
  background:linear-gradient(120deg,#5E1414 0%,#8E2A16 45%,#D9731A 100%);box-shadow:0 18px 50px rgba(94,20,20,.28);}
.hero:before{content:"";position:absolute;inset:0;background:
  radial-gradient(circle at 88% 20%, rgba(255,214,140,.38) 0, rgba(255,214,140,0) 38%),
  repeating-linear-gradient(135deg, rgba(255,255,255,.035) 0 2px, transparent 2px 14px);}
.hero>*{position:relative;}
.hero .badge{display:inline-block;padding:6px 14px;border-radius:999px;background:rgba(255,255,255,.16);
  border:1px solid rgba(255,255,255,.28);font-size:.82rem;font-weight:600;letter-spacing:.04em;backdrop-filter:blur(4px);}
.hero .title{font-family:'Fraunces',serif;font-weight:700;font-size:3.1rem;line-height:1.05;margin:16px 0 10px;color:#FFF3DC;}
.hero .sub{font-size:1.12rem;max-width:720px;line-height:1.55;color:#FBE8CC;margin:0 0 22px;}
.chips{display:flex;flex-wrap:wrap;gap:10px;}
.chip{padding:8px 14px;border-radius:12px;background:rgba(0,0,0,.20);font-size:.88rem;font-weight:500;color:#FFEBD0;}
.chip b{color:#fff;font-weight:700;}

/* cards */
.sec{margin:34px 0 6px;}
.sec .k{font-size:.78rem;font-weight:700;letter-spacing:.14em;color:var(--saffron);text-transform:uppercase;}
.sec .t{font-family:'Fraunces',serif;font-size:1.75rem;font-weight:700;color:var(--maroon);margin:2px 0 4px;}
.sec .d{color:var(--muted);font-size:1rem;margin-bottom:12px;max-width:760px;}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px;}
.card{background:#fff;border:1px solid var(--line);border-radius:20px;padding:22px 24px;box-shadow:0 8px 28px rgba(122,31,31,.07);}
.card .lab{font-size:.78rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);}
.card .big{font-family:'Fraunces',serif;font-size:2rem;font-weight:700;line-height:1.15;margin:8px 0 6px;}
.card .note{color:var(--muted);font-size:.95rem;line-height:1.5;}
.card.good{border-top:5px solid #2E9E6B;}.card.good .big{color:#1F7A52;}
.card.bad{border-top:5px solid #D64545;}.card.bad .big{color:#B83232;}
.card.mid{border-top:5px solid var(--gold);}.card.mid .big{color:#9A6B10;}

/* month tiles */
.mgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;}
.mtile{background:#fff;border:1px solid var(--line);border-top:5px solid var(--c);border-radius:16px;padding:16px 16px 14px;
  box-shadow:0 6px 20px rgba(122,31,31,.06);transition:transform .15s ease, box-shadow .15s ease;}
.mtile:hover{transform:translateY(-3px);box-shadow:0 12px 28px rgba(122,31,31,.13);}
.mname{font-family:'Fraunces',serif;font-weight:700;font-size:1.3rem;color:var(--ink);}
.mlevel{display:inline-block;margin:6px 0 10px;padding:3px 11px;border-radius:999px;font-size:.78rem;font-weight:700;}
.mnum{font-weight:700;font-size:1.05rem;}.mnum span{font-weight:500;color:var(--muted);font-size:.85rem;}
.mwait{color:var(--muted);font-size:.85rem;margin-top:3px;}

/* weekday bars */
.wrow{display:grid;grid-template-columns:110px 1fr 64px;align-items:center;gap:12px;margin:9px 0;}
.wrow .n{font-weight:600;}.wrow .v{text-align:right;font-weight:700;}
.wbar{height:16px;border-radius:999px;background:var(--sand);overflow:hidden;}
.wbar i{display:block;height:100%;border-radius:999px;}

/* result cards */
.rgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin:8px 0 6px;}
.rcard{background:#fff;border:1px solid var(--line);border-radius:18px;padding:16px 18px;box-shadow:0 6px 20px rgba(122,31,31,.07);position:relative;}
.rcard .rk{position:absolute;top:12px;right:14px;font-family:'Fraunces',serif;font-size:1.6rem;font-weight:700;color:#E7D6BC;}
.rcard .d{font-family:'Fraunces',serif;font-weight:700;font-size:1.25rem;color:var(--maroon);}
.rcard .w{color:var(--muted);font-size:.9rem;margin-bottom:8px;}
.pill{display:inline-block;padding:3px 11px;border-radius:999px;font-size:.78rem;font-weight:700;}
.rcard .p{margin-top:8px;font-weight:600;}

/* calendar */
.cgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px;}
.cal{background:#fff;border:1px solid var(--line);border-radius:18px;padding:14px 14px 12px;box-shadow:0 6px 20px rgba(122,31,31,.06);}
.cal .cm{font-family:'Fraunces',serif;font-weight:700;color:var(--maroon);margin:0 0 8px 2px;font-size:1.05rem;}
.cdays{display:grid;grid-template-columns:repeat(7,1fr);gap:3px;}
.ch{font-size:.65rem;font-weight:700;color:var(--muted);text-align:center;padding-bottom:2px;}
.cd{aspect-ratio:1/1;display:flex;align-items:center;justify-content:center;border-radius:7px;font-size:.72rem;font-weight:600;}
.cd.e{background:transparent;}.cd.past{background:#F1ECE3;color:#B9AC9B;}
.legend{display:flex;flex-wrap:wrap;gap:12px;margin:6px 0 14px;font-size:.85rem;color:var(--muted);}
.legend i{display:inline-block;width:12px;height:12px;border-radius:4px;margin-right:6px;vertical-align:-1px;}

/* tips */
.tips{background:linear-gradient(135deg,#FFF6E6,#FFFFFF);border:1px solid #F0DDB8;border-radius:20px;padding:22px 26px;}
.tips ul{margin:8px 0 0 0;padding-left:20px;}.tips li{margin:9px 0;line-height:1.55;}
.foot{text-align:center;color:var(--muted);font-size:.85rem;margin-top:36px;}
@media (max-width:640px){.hero{padding:28px 22px}.hero .title{font-size:2.2rem}.wrow{grid-template-columns:84px 1fr 52px}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def H(s: str) -> str:
    """Collapse an HTML snippet to one line so Markdown never treats it as a code block."""
    return " ".join(line.strip() for line in s.strip().splitlines() if line.strip())


def html(s: str):
    st.markdown(H(s), unsafe_allow_html=True)


def section(kicker, title, desc=""):
    html(f'<div class="sec"><div class="k">{kicker}</div><div class="t">{title}</div>'
         f'<div class="d">{desc}</div></div>')


def style(fig, h=420):
    fig.update_layout(height=h)
    return fig


# ───────────────────────── data ─────────────────────────
@st.cache_data(show_spinner=False)
def load(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig", parse_dates=["date"])
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    for c in ["total_pilgrims", "tonsures", "hundi_cr", "laddu_lakh", "annaprasadam_lakh", "aswini_hospital"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    # Posted free-darshan wait (hours). Experimental: TTD posts it for varying times of day and caps it at 24 H.
    if {"wait_min", "wait_max"} <= set(df.columns):
        df["wait_h"] = (pd.to_numeric(df.wait_min, errors="coerce") + pd.to_numeric(df.wait_max, errors="coerce")) / 2
    else:
        df["wait_h"] = np.nan
    df["suspect"] = df["suspect"].fillna(False).astype(bool) if "suspect" in df else False
    for c in ("suspect_reason", "data_fix"):
        df[c] = df[c].fillna("") if c in df else ""
    return df


def week_label(w):
    for y in (2026, 2025):
        try:
            s = pd.Timestamp.fromisocalendar(y, int(w), 1)
            return f"{s:%d %b} – {s + pd.Timedelta(days=6):%d %b}"
        except ValueError:
            continue
    return ""


# ───────────────────────── sidebar (advanced) ─────────────────────────
st.sidebar.title("⚙️ Settings")
st.sidebar.caption("Most people can ignore these. They change which years the numbers are based on.")
up = st.sidebar.file_uploader("Use your own CSV (optional)", type="csv")
if up is not None:
    raw = up.getvalue()
elif os.path.exists(DEFAULT_CSV):
    raw = open(DEFAULT_CSV, "rb").read()
else:
    st.title("🛕 PlanMyDarshan")
    st.info("Upload `ttd_darshan_stats.csv` in the sidebar (or place it next to app.py).")
    st.stop()

full = load(raw)
y_min, y_max = int(full.date.dt.year.min()), int(full.date.dt.year.max())

yr_range = st.sidebar.slider(
    "Years to use", y_min, y_max, (max(y_min, 2023), y_max),
    help="Default starts at 2023: 2021 was heavily COVID-affected and Jan–Feb 2022 was still depressed "
         "(~32k–39k/day), which makes those months look falsely quiet.")
min_valid = st.sidebar.number_input("Ignore daily totals below", 0, 50000, 0, 500,
    help="Default 0 = nothing is hidden. Real low days (COVID, eclipse closures, storms) are kept.")
max_valid = st.sidebar.number_input("Ignore daily totals above", 90000, 2_000_000, 150000, 10000)
normalize = st.sidebar.toggle(
    "Compare each year to its own average", True,
    help="Crowds have grown over the years. Turning this on removes that growth so that months can be "
         "compared fairly. 1.00 = a normal day that year; 0.90 = 10% quieter than normal.")
quiet_n = st.sidebar.slider("'Quiet month' = one of the quietest N months in a year", 2, 6, 4)
drop_suspect = st.sidebar.toggle(
    "Leave out days with questionable data", True,
    help="TTD's own posts sometimes disagree with themselves (title vs text) or repeat yesterday's number. "
         "Those days are flagged. Turn this off to include them anyway. The 🔍 Unusual days tab always shows them.")

mask_ok = full.total_pilgrims.between(min_valid, max_valid)
bad = full[~mask_ok | full.total_pilgrims.isna()]
keep = mask_ok & ~full.suspect if drop_suspect else mask_ok
df = full[keep].copy()
df["year"] = df.date.dt.year
df = df[df.year.between(*yr_range)].copy()
if df.empty:
    st.warning("No data in the selected range.")
    st.stop()
df["month"] = df.date.dt.month
df["dow_i"] = df.date.dt.dayofweek
df["dow"] = pd.Categorical(df.date.dt.day_name(), DOW, ordered=True)
df["woy"] = df.date.dt.isocalendar().week.astype(int)
df["iso_year"] = df.date.dt.isocalendar().year.astype(int)
df["rel"] = df.total_pilgrims / df.groupby("year").total_pilgrims.transform("mean")
VAL = "rel" if normalize else "total_pilgrims"
MVAL = "rel" if normalize else "avg"
VAL_LABEL = "Crowd vs yearly avg (1.0 = normal)" if normalize else "Pilgrims per day"
FMT = ".2f" if normalize else ",.0f"

n_susp = int((full.suspect & full.date.dt.year.between(*yr_range)).sum())   # within the selected years
st.sidebar.caption(f"{len(df):,} days · {df.date.min():%d %b %Y} → {df.date.max():%d %b %Y} · "
                   f"{len(bad)} outside your limits · {n_susp} questionable days {'left out' if drop_suspect else 'kept'}")
n_years = int(df.year.nunique())
DATA_NOTE = f"Based on {n_years} years of data ({df.year.min()}–{df.year.max()}, {len(df):,} days)."

# ───────────────────────── aggregates ─────────────────────────
my_all = (df.groupby(["year", "month"])
            .agg(avg=("total_pilgrims", "mean"), rel=("rel", "mean"), n=("date", "count")).reset_index())
my_all["partial"] = my_all.n < PARTIAL_DAYS
_p = my_all[my_all.partial]
UNFINISHED_NOTE = ("" if _p.empty else
    "Every day counts in the averages. " + ", ".join(f"{MON[int(m) - 1]} {int(y)} ({int(n)} days)" for y, m, n in
                                                    zip(_p.year, _p.month, _p.n)) +
    " has too few days so far to be compared fairly with full months, so it is shown on charts but not ranked yet.")
my = my_all[~my_all.partial].copy()                       # full months only: used for ranking and heatmaps
my["rank"] = my.groupby("year")[MVAL].rank(method="min")
my["n_in_year"] = my.groupby("year")["month"].transform("count")
my["pct"] = np.where(my.n_in_year > 1, (my["rank"] - 1) / (my.n_in_year - 1), 0.5)
my["is_quiet"] = my["rank"] <= quiet_n

wy = (df.groupby(["iso_year", "woy"])
        .agg(avg=("total_pilgrims", "mean"), rel=("rel", "mean"), n=("date", "count")).reset_index())
wy = wy[wy.iso_year.between(*yr_range)]
wk = (wy.groupby("woy").agg(avg=("avg", "mean"), rel=("rel", "mean"), rel_min=("rel", "min"),
                            rel_max=("rel", "max"), years=("iso_year", "nunique")).reset_index())
wk["dates"] = wk.woy.map(week_label)

mon = (df.groupby("month").agg(avg=("total_pilgrims", "mean"), median=("total_pilgrims", "median"),
                                rel=("rel", "mean"), std=("rel", "std"), lo=("total_pilgrims", "min"),
                                hi=("total_pilgrims", "max"), days=("date", "count")).reset_index())
mon["name"] = mon.month.map(lambda m: MON[m - 1])

# ── simple forecasting model: season (week of year, smoothed) x weekday factor ──
# The date finder ignores extreme one-off days (e.g. eclipse closures) so they don't distort predictions.
dff = df[df.rel >= 0.55].copy()
dow_f = dff.groupby("dow_i").rel.mean()
dow_f = dow_f / dow_f.mean()
dff["seas"] = dff.rel / dff.dow_i.map(dow_f)
_s = dff.groupby("woy").seas.mean().reindex(range(1, 54)).interpolate(limit_direction="both")
_ext = pd.concat([_s.iloc[-2:], _s, _s.iloc[:2]])
season = _ext.rolling(3, center=True).mean().iloc[2:-2]
season.index = range(1, 54)
dff["_pred_rel"] = dff.woy.map(season).values * dff.dow_i.map(dow_f).values
BAND_LO, BAND_HI = (dff.rel / dff["_pred_rel"]).quantile([.1, .9]).tolist()   # typical 80% range around a forecast
_ts = dff.set_index("date").total_pilgrims
baseline = _ts[_ts.index > _ts.index.max() - pd.Timedelta(days=365)].mean()


def predict(dates):
    d = pd.DatetimeIndex(dates)
    wkn = d.isocalendar().week.astype(int).values
    return season.reindex(wkn).values * dow_f.reindex(d.dayofweek).values * baseline


today = pd.Timestamp.today().normalize()


def lvl(v):
    """Crowd level 0 (Quiet) .. 4 (Very busy) on the fixed LEVEL_CUTS scale."""
    return int(np.searchsorted(LEVEL_CUTS, v, side="right"))


def pill(i):
    n, bg, fg = LEVELS[i]
    return f'<span class="pill" style="background:{bg};color:{fg}">{n}</span>'


def k(v):
    return f"{v / 1000:,.0f}k"


# ───────────────────────── hero ─────────────────────────
last_day = full.date.max()
html(f"""
<div class="hero">
<span class="badge">🛕 TIRUMALA TIRUPATI DEVASTHANAMS · CROWD GUIDE</span>
<div class="title">PlanMyDarshan</div>
<div class="sub">Find the quietest days to visit Tirumala. Built from {len(full):,} days of real,
daily pilgrim counts published by TTD, so you can pick your dates with confidence.</div>
<div class="chips">
<span class="chip">📊 <b>{y_min}–{y_max}</b> daily data</span>
<span class="chip">🙏 <b>{df.total_pilgrims.mean() / 1000:,.0f}k</b> pilgrims on an average day</span>
<span class="chip">🗓️ Updated to <b>{last_day:%d %b %Y}</b></span>
</div>
</div>
""")

tabs = st.tabs(["🏠 Plan my visit", "🔍 Unusual days", "📅 Best months", "🗓️ Best weeks", "📈 Timelines",
                "🔥 Heatmaps", "🎯 Consistency", "📊 Other stats", "🧹 Data"])

# ═════════════════════════ PLAN MY VISIT ═════════════════════════
with tabs[0]:
    # ---- the short answer ----
    now_m = mon.assign(now=mon.rel * baseline)           # typical day in each month, at today's crowd level
    best3 = now_m.nsmallest(3, "rel")
    worst2 = now_m.nlargest(2, "rel")
    wd_now = pd.Series((dow_f * baseline).reindex(range(7)).values, index=DOW)
    best_day, worst_day = wd_now.idxmin(), wd_now.idxmax()
    wkday = float(dow_f.reindex(range(5)).mean() * baseline)
    wkend = float(dow_f.reindex([5, 6]).mean() * baseline)

    section("The short answer", "When should I go?",
            f"If you can choose, these are the times that have usually been calmer. {DATA_NOTE} "
            "These are patterns, not guarantees.")
    html(f"""
    <div class="grid3">
    <div class="card good"><div class="lab">✅ Usually the quietest months</div>
    <div class="big">{" · ".join(MONTH_FULL[int(m) - 1] for m in best3.month)}</div>
    <div class="note">A typical day has about <b>{k(best3.now.min()) if k(best3.now.min()) == k(best3.now.max()) else k(best3.now.min()) + "–" + k(best3.now.max())}</b> pilgrims at today's crowd levels
    (an average day is about {k(baseline)}).</div></div>
    <div class="card mid"><div class="lab">📆 Usually the calmest weekday</div>
    <div class="big">{best_day}</div>
    <div class="note">About <b>{k(wd_now.min())}</b> on a typical {best_day}, compared with <b>{k(wd_now.max())}</b> on a {worst_day}.
    Weekdays average {k(wkday)}; weekends {k(wkend)}.</div></div>
    <div class="card bad"><div class="lab">⚠️ Usually the busiest months</div>
    <div class="big">{" · ".join(MONTH_FULL[int(m) - 1] for m in worst2.month)}</div>
    <div class="note">A typical day has about <b>{k(worst2.now.max())}</b> pilgrims at the peak, and the very busiest days have reached about 98k.</div></div>
    </div>
    """)

    # ---- find my likely quietest day ----
    section("Plan your dates", "Find my likely quietest day",
            "Tell us when you can travel and we'll rank the days in that window from likely calmest to likely busiest.")
    c1, c2 = st.columns([2, 1])
    with c1:
        rng = st.date_input("I can travel between", value=((today + pd.Timedelta(days=14)).date(),
                                                          (today + pd.Timedelta(days=44)).date()),
                            min_value=today.date(), max_value=(today + pd.Timedelta(days=365)).date(),
                            format="DD/MM/YYYY", help="Pick the same date twice to check a single day.")
    with c2:
        skip_we = st.checkbox("Skip Saturdays & Sundays", value=False)
        st.caption(f"Each time of year has only {n_years} past years behind it, so treat this as a guide. "
                   "Festivals and holidays aren't predicted.")
    if isinstance(rng, (list, tuple)) and len(rng) == 2:
        win = pd.date_range(rng[0], rng[1])
        if skip_we:
            win = win[win.dayofweek < 5]
        if len(win) == 0:
            st.info("No weekdays in that window. Try a longer range.")
        else:
            pv = predict(win)
            order = np.argsort(pv, kind="stable")[:5]
            cards = ""
            for r, i in enumerate(order, 1):
                d = win[i]
                cards += (f'<div class="rcard"><span class="rk">#{r}</span><div class="d">{d:%d %b %Y}</div>'
                          f'<div class="w">{d:%A}</div>{pill(lvl(pv[i]))}'
                          f'<div class="p">usually {k(pv[i] * BAND_LO)}–{k(pv[i] * BAND_HI)} pilgrims</div></div>')
            html(f'<div class="rgrid">{cards}</div>')

            fig = go.Figure(go.Bar(
                x=win, y=pv, marker_color=[LEVELS[lvl(v)][1] for v in pv],
                customdata=[[f"{d:%A}", LEVELS[lvl(v)][0], v * BAND_LO, v * BAND_HI] for d, v in zip(win, pv)],
                hovertemplate=("%{x|%d %b %Y} · %{customdata[0]}<br>%{customdata[1]} · usually "
                               "%{customdata[2]:,.0f}–%{customdata[3]:,.0f} pilgrims<extra></extra>")))
            fig.update_layout(yaxis_title="Expected pilgrims (typical)", bargap=.15,
                              yaxis_range=[max(0, pv.min() * .6), pv.max() * 1.08])
            st.plotly_chart(style(fig, 300), width="stretch")
            st.markdown(f'<div class="legend">{LEGEND}</div>', unsafe_allow_html=True)

    # ---- next 12 months calendar ----
    section("The year ahead", "Crowd calendar",
            "Colours use a fixed scale (see the key), not rankings, so if every day is busy you'll see mostly orange "
            f"and red. Hover over a day for details. {DATA_NOTE}")
    first = today.replace(day=1)
    cal_days = pd.date_range(first, first + pd.DateOffset(months=12) - pd.Timedelta(days=1))
    cal_pred = dict(zip(cal_days, predict(cal_days)))
    cal_html = f'<div class="legend">{LEGEND}</div><div class="cgrid">'
    for mi in range(12):
        ms = first + pd.DateOffset(months=mi)
        cells = '<div class="ch">M</div><div class="ch">T</div><div class="ch">W</div><div class="ch">T</div>' \
                '<div class="ch">F</div><div class="ch">S</div><div class="ch">S</div>'
        for week in calendar.Calendar(0).monthdayscalendar(ms.year, ms.month):
            for day in week:
                if day == 0:
                    cells += '<div class="cd e"></div>'
                    continue
                d = pd.Timestamp(ms.year, ms.month, day)
                if d < today:
                    cells += f'<div class="cd past" title="{d:%a %d %b}">{day}</div>'
                    continue
                v = float(cal_pred[d])
                n, bg, fg = LEVELS[lvl(v)]
                cells += (f'<div class="cd" style="background:{bg};color:{fg}" '
                          f'title="{d:%a %d %b %Y} · {n} (about {k(v)})">{day}</div>')
        cal_html += f'<div class="cal"><div class="cm">{ms:%B %Y}</div><div class="cdays">{cells}</div></div>'
    html(cal_html + "</div>")

    # ---- month guide ----
    section("Month by month", "How busy is each month?",
            f"A typical day in each month, scaled to today's crowd level (about {k(baseline)} a day over the last "
            f"12 months). {DATA_NOTE} Even a calmer month is still a busy temple.")
    tiles = ""
    for _, r in now_m.sort_values("month").iterrows():
        n, bg, fg = LEVELS[lvl(r.now)]
        tiles += (f'<div class="mtile" style="--c:{bg}"><div class="mname">{MONTH_FULL[int(r.month) - 1]}</div>'
                  f'<span class="mlevel" style="background:{bg};color:{fg}">{n}</span>'
                  f'<div class="mnum">about {k(r.now)} <span>/ typical day</span></div></div>')
    html(f'<div class="legend">{LEGEND}</div><div class="mgrid">{tiles}</div>')

    # ---- weekday bars ----
    section("Day by day", "Which day of the week is calmest?")
    mx = wd_now.max()
    rows = ""
    for dname, v in wd_now.items():
        _, bg, _ = LEVELS[lvl(v)]
        rows += (f'<div class="wrow"><span class="n">{dname}</span>'
                 f'<div class="wbar"><i style="width:{v / mx * 100:.0f}%;background:{bg}"></i></div>'
                 f'<span class="v">{k(v)}</span></div>')
    html(f'<div class="card">{rows}</div>')

    # ---- good to know ----
    section("Before you book", "Good to know")
    html(f"""
    <div class="tips"><ul>
    <li><b>Weekends are busier.</b> Saturdays and Sundays are typically around {k(wkend)} pilgrims against {k(wkday)} on weekdays.</li>
    <li><b>Festivals and school holidays break the pattern.</b> Brahmotsavam, Vaikunta Ekadasi, Sankranti, summer vacation and long weekends can be far busier than any average. Check TTD's official calendar for your dates.</li>
    <li><b>Quiet isn't the same as short.</b> Free-darshan queues can still run many hours on calmer days. Check TTD's live waiting-time information before you travel.</li>
    <li><b>These are estimates.</b> {DATA_NOTE} They are adjusted for the weekday and time of year, and scaled to the last 12 months' crowd level, because crowds have been growing.</li>
    <li><b>Not official.</b> This is an independent tool built from the daily statistics TTD publishes at news.tirumala.org.</li>
    </ul></div>
    """)
    with st.expander("Why do a couple of days show surprisingly low numbers?"):
        low = df.nsmallest(5, "total_pilgrims")[["date", "dow", "total_pilgrims"]]
        low.columns = ["Date", "Weekday", "Pilgrims"]
        st.dataframe(low.style.format({"Pilgrims": "{:,.0f}", "Date": "{:%d %b %Y}"}), hide_index=True)
        st.caption("Very low days such as 7 Sep 2025 and 3 Mar 2026 were lunar-eclipse closures, when the temple "
                   "shuts for hours. They aren't a reliable 'quiet day' to aim for. See the 🔍 Unusual days tab "
                   "for every extreme day and what was reported as the cause.")
    html('<div class="foot">Made with 🙏 · Data: news.tirumala.org · Independent project, not affiliated with TTD</div>')

# ═════════════════════════ UNUSUAL DAYS ═════════════════════════
# Entries with a source link were matched to a news report. Entries without one (Diwali dates, COVID-period
# labels) are general knowledge, not individually sourced. Diwali dates can differ by a day between regions.
KNOWN = {   # date: (type, what was reported, source URL or "")
    "2021-11-04": ("Diwali", "Diwali", ""),
    "2022-10-24": ("Diwali", "Diwali (Deepavali Asthanam at the temple)",
                   "https://www.sakshipost.com/news/andhrapradesh/tirumala-temple-remain-closed-solar-eclipse-tomorrow-163438"),
    "2023-11-12": ("Diwali", "Diwali", ""),
    "2024-10-31": ("Diwali", "Diwali (some regions marked it on 1 Nov)", ""),
    "2025-10-20": ("Diwali", "Diwali", ""),
    "2026-11-08": ("Diwali", "Diwali", ""),
    "2022-10-25": ("Temple closed", "Solar eclipse: temple shut about 11 hours (8:11 am to 7:30 pm)",
                   "https://thehansindia.com/amp/news/cities/tirupathi/tirumala-temple-to-remain-closed-for-about-12-hrs-on-oct-25-nov-8-760885"),
    "2022-11-08": ("Temple closed", "Lunar eclipse: temple shut about 11 hours (8:40 am to 7:20 pm)",
                   "https://www.lokmattimes.com/national/major-temples-in-telugu-states-shut-due-to-lunar-eclipse/amp/"),
    "2025-09-07": ("Temple closed", "Lunar eclipse: temple shut from 3:30 pm until 3 am",
                   "https://telanganatoday.com/tirumala-temple-to-remain-closed-due-to-lunar-eclipse-on-september-7"),
    "2026-03-03": ("Temple closed", "Lunar eclipse: temple shut 9 am to 7:30 pm",
                   "https://www.deccanherald.com/india/andhra-pradesh/tirumala-temple-to-shut-for-over-10-hours-on-march-3-due-to-lunar-eclipse-3851180"),
    "2023-10-28": ("Eclipse night", "Partial lunar eclipse that night (no temple-closure report found)", ""),
    "2021-11-19": ("Flood", "Floods and landslides: temple closed to devotees, ghat roads shut",
                   "https://www.thequint.com/amp/story/news/india/tirumala-temple-shut-for-devotees-as-flood-causes-landslides-on-ghats"),
    "2023-12-04": ("Storm", "Cyclone Michaung: heavy rain in Tirumala and Tirupati (4 to 6 Dec)",
                   "https://deccanchronicle.com/nation/in-other-news/041223/tirumala-dams-full-due-to-heavy-rains-brought-by-cyclone-michaung.html"),
    "2023-12-05": ("Storm", "Cyclone Michaung: heavy rain in Tirumala and Tirupati (4 to 6 Dec)",
                   "https://deccanchronicle.com/nation/in-other-news/041223/tirumala-dams-full-due-to-heavy-rains-brought-by-cyclone-michaung.html"),
    "2023-12-06": ("Storm", "Cyclone Michaung: heavy rain in Tirumala and Tirupati (4 to 6 Dec)",
                   "https://deccanchronicle.com/nation/in-other-news/041223/tirumala-dams-full-due-to-heavy-rains-brought-by-cyclone-michaung.html"),
    "2022-12-09": ("Storm", "Cyclone Mandous: heavy rain, darshan hampered",
                   "https://theprint.in/india/cyclone-mandous-tirupati-temple-premises-waterlogged-devotees-face-problems/1258031"),
}

with tabs[1]:
    section("Beyond the averages", "Unusual days",
            "Averages hide the extremes. Here are the lowest and highest days on record, what caused them, "
            "and whether festivals like Diwali really change the crowd.")
    scope = st.radio("Which years?", [f"All years ({y_min}–{y_max})", f"Only {yr_range[0]}–{yr_range[1]} (set in Settings)"],
                     horizontal=True)
    valid = full[full.total_pilgrims.between(min_valid, max_valid)].sort_values("date")
    ser = valid[~valid.suspect].set_index("date").total_pilgrims      # baseline for "normal day" comparisons
    o = valid.copy()
    if scope.startswith("Only"):
        o = o[o.date.dt.year.between(*yr_range)]
    o = o.reset_index(drop=True)

    def typical(d):
        vals = [ser.get(d + pd.Timedelta(days=j)) for j in (-21, -14, -7, 7, 14, 21)]
        vals = [v for v in vals if v is not None and not pd.isna(v)]
        return float(np.median(vals)) if len(vals) >= 3 else np.nan

    def reason(d, tot):
        kn = KNOWN.get(f"{d:%Y-%m-%d}")
        if kn:
            return kn[1]
        if pd.Timestamp("2021-04-01") <= d <= pd.Timestamp("2021-07-31") and tot < 20000:
            return "COVID second-wave period (travel and darshan restrictions)"
        if pd.Timestamp("2022-01-01") <= d <= pd.Timestamp("2022-02-28") and tot < 40000:
            return "COVID Omicron-wave period (reduced travel)"
        return ""

    o["typical"] = o.date.map(typical)
    o["vs_typical"] = o.total_pilgrims / o.typical - 1
    o["why"] = [reason(d, t) for d, t in zip(o.date, o.total_pilgrims)]
    o["ttd_note"] = o["title"].str.extract(r"\(([^)]+)\)")[0].fillna("")
    o["source"] = o.date.map(lambda d: KNOWN.get(f"{d:%Y-%m-%d}", ("", "", ""))[2])
    o["dow_name"] = o.date.dt.day_name()

    lo1 = o.loc[o.total_pilgrims.idxmin()]
    hi1 = o.loc[o.total_pilgrims.idxmax()]
    n4 = int((o.total_pilgrims < 10000).sum())
    yrs4 = sorted(o[o.total_pilgrims < 10000].date.dt.year.unique())
    n_hi = int((o.total_pilgrims >= 90000).sum())
    n_lo = int((o.total_pilgrims < 50000).sum())
    yrs4_txt = ", ".join(str(y) for y in yrs4) if yrs4 else "none"
    html(f"""
    <div class="grid3">
    <div class="card bad"><div class="lab">Lowest day on record</div><div class="big">{lo1.total_pilgrims:,.0f}</div>
    <div class="note">{lo1.date:%a %d %b %Y}. {lo1.why or "No known reason found."}</div></div>
    <div class="card good"><div class="lab">Busiest day on record</div><div class="big">{hi1.total_pilgrims:,.0f}</div>
    <div class="note">{hi1.date:%a %d %b %Y}. {hi1.ttd_note or ""}</div></div>
    <div class="card mid"><div class="lab">Days under 10,000 pilgrims</div><div class="big">{n4}</div>
    <div class="note">Years it happened: <b>{yrs4_txt}</b>. Four-digit days were a COVID-era thing.</div></div>
    <div class="card mid"><div class="lab">Days under 50k · over 90k</div><div class="big">{n_lo:,} · {n_hi:,}</div>
    <div class="note">out of {len(o):,} days in this view.</div></div>
    </div>
    """)

    # ---- timeline with the extremes highlighted ----
    section("Every day, with the extremes marked", "",
            "Grey line = every day. Red dots = the lowest days (maroon = since COVID), amber dots = the busiest. Hover for the cause.")
    lows = o.nsmallest(15, "total_pilgrims")
    lows_post = o[o.date >= "2022-01-01"].nsmallest(10, "total_pilgrims")
    highs = o.nlargest(10, "total_pilgrims")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=o.date, y=o.total_pilgrims, mode="lines", line=dict(width=1, color="#C9B79C"),
                             name="Daily", hovertemplate="%{x|%d %b %Y}: %{y:,.0f}<extra></extra>"))
    for dd, color, nm in [(lows, "#D64545", "Lowest days (mostly COVID 2021)"),
                          (lows_post, "#7A1F1F", "Lowest days since 2022"), (highs, "#F2994A", "Busiest days")]:
        fig.add_trace(go.Scatter(
            x=dd.date, y=dd.total_pilgrims, mode="markers", name=nm,
            marker=dict(size=11, color=color, line=dict(color="#fff", width=2)),
            customdata=np.stack([dd.why.replace("", "No known reason found") if nm != "Busiest days" else dd.why.replace("", " "), dd.ttd_note], axis=1),
            hovertemplate="%{x|%d %b %Y}: %{y:,.0f}<br>%{customdata[0]}<br>%{customdata[1]}<extra></extra>"))
    fig.update_layout(yaxis_title="Pilgrims per day", legend=dict(orientation="h", y=1.1))
    st.plotly_chart(style(fig, 430), width="stretch")

    # ---- tables ----
    def table(dd, blank="No known reason found"):
        t = dd[["date", "dow_name", "total_pilgrims", "vs_typical", "why", "source", "ttd_note", "suspect_reason"]].copy()
        t["why"] = t["why"].replace("", blank)
        t.columns = ["Date", "Weekday", "Pilgrims", "vs a normal day*", "Why (reported)", "Source", "TTD's own note",
                     "Data check"]
        return t.style.format({"Date": "{:%d %b %Y}", "Pilgrims": "{:,.0f}", "vs a normal day*": "{:+.0%}"}, na_rep="")

    SRC = {"Source": st.column_config.LinkColumn("Source", display_text=r"https?://(?:www\.)?([^/]+)")}
    nshow = st.slider("How many days to list", 10, 60, 25)
    post = o[o.date >= "2022-01-01"]
    covid = o[o.date < "2022-01-01"]
    st.markdown("### 🔻 Quietest days since COVID (2022 onwards)")
    st.dataframe(table(post.nsmallest(nshow, "total_pilgrims")), hide_index=True, width="stretch", column_config=SRC)
    if len(covid):
        with st.expander("🔻 Quietest days during COVID (2021)"):
            st.dataframe(table(covid.nsmallest(nshow, "total_pilgrims")), hide_index=True, width="stretch", column_config=SRC)
    st.markdown("### 🔺 Busiest days ever")
    st.dataframe(table(o.nlargest(nshow, "total_pilgrims"), blank="—"), hide_index=True, width="stretch", column_config=SRC)
    st.caption("*Compared with the median of the same weekday in the 3 weeks before and after (days flagged as "
               "questionable are not used for that baseline). 'Why (reported)': rows with a Source link are matched to a "
               "news report; rows without one are general-knowledge labels (e.g. COVID periods, Diwali). "
               "'No known reason found' means we haven't found a cause. 'Data check' shows where TTD's own title and post text disagree.")

    # ---- did festivals / events change the crowd? ----
    section("Festival check", "Did Diwali or other events really change the crowd?",
            "Each event day compared with the same weekday in the 3 weeks before and after.")
    rows = []
    for dstr, (typ, desc, _src) in sorted(KNOWN.items()):
        d = pd.Timestamp(dstr)
        if d in ser.index and not np.isnan(typical(d)):
            rows.append({"Type": typ, "Date": d, "Weekday": d.strftime("%a"), "What was reported": desc,
                         "Pilgrims": ser[d], "Normal for that weekday": typical(d),
                         "Difference": ser[d] / typical(d) - 1, "Source": KNOWN[dstr][2]})
    ev = pd.DataFrame(rows)
    if len(ev):
        diw = ev[ev.Type == "Diwali"]
        if len(diw):
            med = diw.Difference.median()
            html(f"""
            <div class="tips"><b>Diwali:</b> across the {len(diw)} Diwali days in the data, attendance was typically
            <b>{abs(med):.0%} {"lower" if med < 0 else "higher"}</b> than a normal {"day" if len(diw) > 1 else diw.Weekday.iloc[0]} around it
            (range {diw.Difference.min():+.0%} to {diw.Difference.max():+.0%}). That is only {len(diw)} observations, but it gives no sign
            that people stay away in large numbers.
            The big collapses in this table are <b>closures and storms</b>, not festivals.</div>
            """)
        st.dataframe(ev.style.format({"Date": "{:%d %b %Y}", "Pilgrims": "{:,.0f}",
                                      "Normal for that weekday": "{:,.0f}", "Difference": "{:+.0%}"}, na_rep=""),
                     hide_index=True, width="stretch", column_config=SRC)

    ordinary = o[(o.date >= "2022-01-01") & (o.why == "")]
    if len(ordinary):
        om = ordinary.nsmallest(1, "total_pilgrims").iloc[0]
        html(f"""
        <div class="tips"><ul>
        <li><b>So is it always ~50k?</b> No. A normal day is roughly 55k to 90k. Outside COVID, the lowest day with no known cause since 2022
        was <b>{om.total_pilgrims:,.0f}</b> ({om.date:%d %b %Y}).</li>
        <li><b>Crashes are rare and have causes:</b> temple closures for eclipses, floods and cyclone rain.
        Most of the extremely low days in 2021 were the COVID second wave.</li>
        <li><b>Plan around them:</b> if an eclipse or a cyclone warning falls on your dates, expect disruption, not a calm visit.</li>
        </ul></div>
        """)

# ═════════════════════════ BEST MONTHS ═════════════════════════
with tabs[2]:
    st.subheader("Average crowd by calendar month")
    st.caption(DATA_NOTE)
    metric = st.radio("Show", ["Average pilgrims/day", "Median pilgrims/day", "Relative to year"], horizontal=True)
    col = {"Average pilgrims/day": "avg", "Median pilgrims/day": "median", "Relative to year": "rel"}[metric]
    d = mon.sort_values("month")
    colors = px.colors.sample_colorscale(CROWD_SCALE, (d[col] - d[col].min()) / (d[col].max() - d[col].min() + 1e-9))
    fig = go.Figure(go.Bar(x=d.name, y=d[col], marker_color=colors,
                           text=d[col].map(lambda v: f"{v:.2f}" if col == "rel" else f"{v / 1000:.1f}k"),
                           textposition="outside"))
    fig.update_layout(yaxis_title=metric)
    st.plotly_chart(style(fig, 450), width="stretch")
    t = d.sort_values("rel")[["name", "avg", "median", "rel", "lo", "hi", "days"]]
    t.columns = ["Month", "Avg/day", "Median/day", "vs normal", "Lowest day", "Highest day", "Days"]
    st.markdown("**Ranked quietest → busiest**")
    st.dataframe(t.style.format({"Avg/day": "{:,.0f}", "Median/day": "{:,.0f}", "vs normal": "{:.2f}",
                                 "Lowest day": "{:,.0f}", "Highest day": "{:,.0f}"}),
                 hide_index=True, width="stretch")

# ═════════════════════════ BEST WEEKS ═════════════════════════
with tabs[3]:
    st.subheader("Crowd level by week of the year")
    st.caption(f"{DATA_NOTE} Each week of the year has only {n_years} past years behind it (see the Years column), "
               "so treat individual weeks as indicative, not exact.")
    topn = st.slider("Highlight the N quietest weeks", 3, 15, 8)
    w = wk.sort_values("woy").copy()
    qset = set(w.nsmallest(topn, "rel").woy)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=w.woy, y=w.rel_max, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=w.woy, y=w.rel_min, fill="tonexty", line=dict(width=0),
                             fillcolor="rgba(181,71,27,.12)", name="Range across years"))
    fig.add_trace(go.Scatter(x=w.woy, y=w.rel, mode="lines", line=dict(color="#B5471B", width=3), name="Average",
                             customdata=w.dates, hovertemplate="Week %{x} (%{customdata})<br>%{y:.2f}<extra></extra>"))
    q = w[w.woy.isin(qset)]
    fig.add_trace(go.Scatter(x=q.woy, y=q.rel, mode="markers", marker=dict(color="#2E9E6B", size=11,
                             line=dict(color="#fff", width=2)), name="Quietest", customdata=q.dates,
                             hovertemplate="Week %{x} (%{customdata})<br>%{y:.2f}<extra></extra>"))
    fig.add_hline(y=1, line_dash="dash", line_color="#9A8A7A")
    fig.update_layout(xaxis_title="ISO week of year", yaxis_title="Crowd vs yearly avg (1.0 = normal)")
    st.plotly_chart(style(fig, 470), width="stretch")
    t = w.sort_values("rel")[["woy", "dates", "avg", "rel", "rel_min", "rel_max", "years"]]
    t.columns = ["ISO week", "Dates (approx.)", "Avg/day", "vs normal", "Best year", "Worst year", "Years"]
    st.dataframe(t.style.format({"Avg/day": "{:,.0f}", "vs normal": "{:.2f}", "Best year": "{:.2f}",
                                 "Worst year": "{:.2f}"}), hide_index=True, width="stretch", height=420)
    st.caption("'Best year / Worst year' = the lowest and highest value this week has had in any single year. "
               "A narrow gap means the week is reliably that quiet/busy.")

# ═════════════════════════ TIMELINES ═════════════════════════
with tabs[4]:
    st.subheader("Monthly timeline")
    mt = df.groupby(df.date.dt.to_period("M")).agg(avg=("total_pilgrims", "mean"), n=("date", "count")).reset_index()
    mt["date"] = mt.date.dt.to_timestamp()
    mt["partial"] = mt.n < PARTIAL_DAYS
    fig = px.line(mt, x="date", y="avg", markers=True, labels={"avg": "Avg pilgrims/day", "date": ""})
    if mt.partial.any():
        pm = mt[mt.partial]
        fig.add_trace(go.Scatter(x=pm.date, y=pm.avg, mode="markers", name="Unfinished month (few days so far)",
                                 marker=dict(size=12, color="rgba(0,0,0,0)", line=dict(color="#7A1F1F", width=2))))
    lowm = mt[~mt.partial].nsmallest(5, "avg")
    fig.add_trace(go.Scatter(x=lowm.date, y=lowm.avg, mode="markers", marker=dict(color="#2E9E6B", size=13),
                             name="5 quietest months"))
    st.plotly_chart(style(fig, 400), width="stretch")
    st.caption(UNFINISHED_NOTE)

    st.subheader("Month-by-month, one line per year")
    d = my.copy()
    d["Month"] = d.month.map(lambda m: MON[m - 1])
    fig = px.line(d, x="Month", y=MVAL, color=d.year.astype(str), markers=True,
                  category_orders={"Month": MON}, labels={MVAL: VAL_LABEL, "color": "Year"})
    st.plotly_chart(style(fig, 420), width="stretch")

    st.subheader("Weekly timeline")
    wt = df.set_index("date").total_pilgrims.resample("W").agg(["mean", "count"])
    wt = wt[wt["count"] >= 4].reset_index()
    fig = px.line(wt, x="date", y="mean", labels={"mean": "Avg pilgrims/day", "date": ""})
    lw = wt.nsmallest(10, "mean")
    fig.add_trace(go.Scatter(x=lw.date, y=lw["mean"], mode="markers", marker=dict(color="#2E9E6B", size=10),
                             name="10 quietest weeks"))
    st.plotly_chart(style(fig, 400), width="stretch")

    st.subheader("Daily data with rolling average")
    winr = st.slider("Rolling window (days)", 7, 90, 30)
    s = df.set_index("date").total_pilgrims
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", line=dict(width=.8, color="#D9CBB2"), name="Daily"))
    fig.add_trace(go.Scatter(x=s.index, y=s.rolling(winr, center=True, min_periods=winr // 2).mean(),
                             line=dict(width=3, color="#B5471B"), name=f"{winr}-day avg"))
    fig.update_layout(yaxis_title="Pilgrims/day")
    st.plotly_chart(style(fig, 420), width="stretch")

# ═════════════════════════ HEATMAPS ═════════════════════════
with tabs[5]:
    st.subheader("Month × year")
    p = my.pivot(index="year", columns="month", values=MVAL).reindex(columns=range(1, 13))
    p.index = p.index.astype(str)
    p.columns = MON
    fig = px.imshow(p, color_continuous_scale=CROWD_SCALE, aspect="auto", text_auto=FMT,
                    labels=dict(color=VAL_LABEL))
    st.plotly_chart(style(fig, 140 + 55 * len(p)), width="stretch")

    st.subheader("Week of year × year")
    p = wy.pivot(index="iso_year", columns="woy", values="rel" if normalize else "avg")
    p.index = p.index.astype(str)
    fig = px.imshow(p, color_continuous_scale=CROWD_SCALE, aspect="auto",
                    labels=dict(x="ISO week", y="Year", color=VAL_LABEL))
    fig.update_xaxes(dtick=2)
    st.plotly_chart(style(fig, 150 + 50 * len(p)), width="stretch")
    st.caption("Vertical green bands = weeks that are quiet in *every* year; vertical red bands = reliably busy.")

    st.subheader("Weekday × month")
    p = df.pivot_table(index="dow", columns="month", values=VAL, aggfunc="mean", observed=True)
    p = p.reindex(index=DOW, columns=range(1, 13))
    p.columns = MON
    fig = px.imshow(p, color_continuous_scale=CROWD_SCALE, aspect="auto", text_auto=FMT,
                    labels=dict(color=VAL_LABEL))
    st.plotly_chart(style(fig, 450), width="stretch")

    st.subheader("Weekday × week of year")
    p = df.pivot_table(index="dow", columns="woy", values=VAL, aggfunc="mean", observed=True).reindex(DOW)
    fig = px.imshow(p, color_continuous_scale=CROWD_SCALE, aspect="auto",
                    labels=dict(x="ISO week", color=VAL_LABEL))
    st.plotly_chart(style(fig, 350), width="stretch")

# ═════════════════════════ CONSISTENCY ═════════════════════════
with tabs[6]:
    st.subheader("🎯 Which months are consistently quiet?")
    st.write(f"For each year the months are ranked from quietest to busiest. A month is **quiet** in a year if it "
             f"is one of that year's **{quiet_n} quietest** months (change in the sidebar settings). "
             + UNFINISHED_NOTE)

    g = my.groupby("month").agg(
        years=("year", "nunique"), quiet_years=("is_quiet", "sum"), avg_rank=("rank", "mean"),
        best_rank=("rank", "min"), worst_rank=("rank", "max"), avg_pct=("pct", "mean"),
        mean_val=(MVAL, "mean"), std_val=(MVAL, "std"), avg=("avg", "mean")).reset_index()
    g["Month"] = g.month.map(lambda m: MON[m - 1])
    g["quiet_share"] = g.quiet_years / g.years
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
    st.dataframe(show.style.format({"Avg rank": "{:.1f}", "Best rank": "{:.0f}", "Worst rank": "{:.0f}", "Avg/day": "{:,.0f}", "Variability (std)": "{:.3f}"}),
                 hide_index=True, width="stretch")
    st.caption("Rank 1 = quietest month of that year. 'Variability' is how much that month's level swings from year "
               "to year (lower = more predictable).")

    cL, cR = st.columns(2)
    with cL:
        st.markdown("**Rank of each month in each year** (1 = quietest)")
        p = my.pivot(index="year", columns="month", values="rank").reindex(columns=range(1, 13))
        p.index = p.index.astype(str)
        p.columns = MON
        fig = px.imshow(p, color_continuous_scale=CROWD_SCALE, aspect="auto", text_auto=".0f", labels=dict(color="Rank"))
        st.plotly_chart(style(fig, 140 + 55 * len(p)), width="stretch")
    with cR:
        st.markdown("**Average vs. year-to-year swing**")
        fig = px.scatter(g, x="avg_rank", y="std_val", text="Month",
                         labels={"avg_rank": "Average rank (lower = quieter)",
                                 "std_val": "Variability (lower = more consistent)"})
        fig.update_traces(textposition="top center", marker=dict(size=13, color="#B5471B"))
        st.plotly_chart(style(fig, 140 + 55 * len(p)), width="stretch")
        st.caption("Bottom-left = quiet *and* predictable: the safest months to pick.")

    st.divider()
    st.subheader("🏆 Quietest month in each year")
    rows = []
    for y, grp in my.groupby("year"):
        grp = grp.sort_values(MVAL)
        top = grp.head(3)
        busiest = grp.iloc[-1]
        rows.append({"Year": y, "Quietest": MON[int(top.iloc[0].month) - 1], "Avg/day": top.iloc[0].avg,
                     "2nd": MON[int(top.iloc[1].month) - 1] if len(top) > 1 else "",
                     "3rd": MON[int(top.iloc[2].month) - 1] if len(top) > 2 else "",
                     "Busiest": MON[int(busiest.month) - 1], "Busiest avg/day": busiest.avg,
                     "Months counted": len(grp)})
    best = pd.DataFrame(rows)
    st.dataframe(best.style.format({"Avg/day": "{:,.0f}", "Busiest avg/day": "{:,.0f}"}),
                 hide_index=True, width="stretch")
    st.caption("When 'compare each year to its own average' is on, months are ranked by crowd relative to that "
               "year's average; 'Avg/day' is always the raw average pilgrims/day.")

    d = my.copy()
    d["Month"] = d.month.map(lambda m: MON[m - 1])
    d["Year"] = d.year.astype(str)
    d["Quietest"] = d.groupby("year")[MVAL].transform("min") == d[MVAL]
    fig = px.bar(d, x="Month", y="avg", facet_col="Year", facet_col_wrap=3, color="Quietest",
                 color_discrete_map={True: "#2E9E6B", False: "#E8C9A0"},
                 category_orders={"Month": MON}, labels={"avg": "Avg/day"})
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    fig.update_layout(showlegend=False)
    st.plotly_chart(style(fig, 250 * int(np.ceil(d.year.nunique() / 3))), width="stretch")

# ═════════════════════════ OTHER STATS ═════════════════════════
with tabs[7]:
    opts = {"Tonsures": "tonsures", "Hundi collection (₹ crore)": "hundi_cr", "Laddu sales (lakh)": "laddu_lakh",
            "Annaprasadam (lakh)": "annaprasadam_lakh", "Aswini hospital patients": "aswini_hospital",
            "Free-darshan wait (hours, experimental)": "wait_h"}
    opts = {kk: v for kk, v in opts.items() if v in df and df[v].notna().sum() > 30}
    pick = st.selectbox("Metric", list(opts))
    col = opts[pick]
    if col == "wait_h":
        _w = df[df.wait_h.notna()]
        st.warning(f"Experimental. TTD posts the waiting time for varying times of day (e.g. 'after 7am ... 14 H'), "
                   f"so it is not a reliable measure of a day. It exists for {df.wait_h.notna().mean():.0%} of days and "
                   f"{(_w.wait_capped == True).mean():.0%} of those show the 24 H display cap. It isn't used for any "
                   f"recommendation in this app.")
    a, b = st.columns(2)
    with a:
        m = df.groupby("month")[col].mean().reindex(range(1, 13))
        fig = px.bar(x=MON, y=m.values, labels={"x": "", "y": pick}, title=f"{pick}: average by month")
        fig.update_traces(marker_color="#E8801A")
        st.plotly_chart(style(fig, 360), width="stretch")
    with b:
        m = df.groupby("dow", observed=True)[col].mean()
        fig = px.bar(x=m.index.astype(str), y=m.values, labels={"x": "", "y": pick}, title=f"{pick}: average by weekday")
        fig.update_traces(marker_color="#B5471B")
        st.plotly_chart(style(fig, 360), width="stretch")
    s = df.set_index("date")[col]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", line=dict(width=.7, color="#D9CBB2"), name="Daily"))
    fig.add_trace(go.Scatter(x=s.index, y=s.rolling(30, center=True, min_periods=15).mean(),
                             line=dict(width=3, color="#B5471B"), name="30-day avg"))
    fig.update_layout(title=f"{pick} over time")
    st.plotly_chart(style(fig, 380), width="stretch")

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
    st.plotly_chart(style(fig, 450), width="stretch")

# ═════════════════════════ DATA ═════════════════════════
with tabs[8]:
    st.subheader("Data quality")
    full_range = pd.date_range(full.date.min(), full.date.max())
    missing = full_range.difference(full.date)
    fixed = full[full["data_fix"] != ""]
    sus = full[full.suspect]
    c = st.columns(4)
    c[0].metric("Rows in CSV", f"{len(full):,}")
    c[1].metric("Questionable days", len(sus))
    c[2].metric("Missing calendar days", len(missing))
    c[3].metric("Values overridden by hand", len(fixed))
    if len(sus):
        with st.expander(f"{len(sus)} questionable days (TTD's title and post text disagree, or the number repeats the day before)"):
            st.caption(f"Currently {'left out of' if drop_suspect else 'included in'} the analysis (see Settings). "
                       "The shown total is the number in TTD's post title.")
            st.dataframe(sus[["date", "total_pilgrims", "body_total", "suspect_reason"]].rename(columns={
                "total_pilgrims": "Title total", "body_total": "Post-text total", "suspect_reason": "Why flagged"}),
                hide_index=True, width="stretch")
    if len(fixed):
        with st.expander(f"{len(fixed)} values overridden by hand (scripts/overrides.csv)"):
            st.dataframe(fixed[["date", "total_pilgrims", "data_fix"]].rename(
                columns={"total_pilgrims": "Used value", "data_fix": "What was fixed"}),
                hide_index=True, width="stretch")
    st.markdown("**Rows outside your min/max limits** (Settings)")
    st.dataframe(bad[["date", "total_pilgrims", "title"]], hide_index=True, width="stretch")
    if len(missing):
        with st.expander(f"{len(missing)} missing days"):
            st.write(", ".join(d.strftime("%d %b %Y") for d in missing))
    st.markdown("**Download**")
    st.download_button("Cleaned daily data (CSV)",
                       df.drop(columns=["raw_text", "seas"], errors="ignore").to_csv(index=False).encode(),
                       "ttd_clean.csv", "text/csv")
    st.download_button("Month × year summary (CSV)", my.to_csv(index=False).encode(), "month_year.csv", "text/csv")
    st.download_button("Week-of-year summary (CSV)", wk.to_csv(index=False).encode(), "weeks.csv", "text/csv")