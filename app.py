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

# A month needs this many days of data to be ranked against other months.
# (A half-finished month, e.g. the current one, isn't a fair comparison with a full month.)
MIN_DAYS = 20

# crowd level palette: label, background, text colour
LEVELS = [("Quiet", "#2E9E6B", "#FFFFFF"), ("Light", "#9CCB5A", "#1F2D12"), ("Moderate", "#F4D35E", "#3A2E05"),
          ("Busy", "#F2994A", "#FFFFFF"), ("Very busy", "#D64545", "#FFFFFF")]
CROWD_SCALE = [c[1] for c in LEVELS]

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
def _wait_hours(t):
    """Average of the posted free-darshan (Sarvadarshanam) waiting time in hours."""
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
min_valid = st.sidebar.number_input("Ignore daily totals below", 0, 50000, 5000, 500)
max_valid = st.sidebar.number_input("Ignore daily totals above", 90000, 2_000_000, 150000, 10000)
normalize = st.sidebar.toggle(
    "Compare each year to its own average", True,
    help="Crowds have grown over the years. Turning this on removes that growth so that months can be "
         "compared fairly. 1.00 = a normal day that year; 0.90 = 10% quieter than normal.")
quiet_n = st.sidebar.slider("'Quiet month' = one of the quietest N months in a year", 2, 6, 4)

mask_ok = full.total_pilgrims.between(min_valid, max_valid)
bad = full[~mask_ok | full.total_pilgrims.isna()]
df = full[mask_ok].copy()
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

st.sidebar.caption(f"{len(df):,} days · {df.date.min():%d %b %Y} → {df.date.max():%d %b %Y} · "
                   f"{len(bad)} suspect rows ignored")

# ───────────────────────── aggregates ─────────────────────────
my = (df.groupby(["year", "month"])
        .agg(avg=("total_pilgrims", "mean"), rel=("rel", "mean"), n=("date", "count")).reset_index())
my = my[my.n >= MIN_DAYS].copy()
my["rank"] = my.groupby("year")[MVAL].rank(method="min")
my["n_in_year"] = my.groupby("year")["month"].transform("count")
my["pct"] = np.where(my.n_in_year > 1, (my["rank"] - 1) / (my.n_in_year - 1), 0.5)
my["is_quiet"] = my["rank"] <= quiet_n

wy = (df.groupby(["iso_year", "woy"])
        .agg(avg=("total_pilgrims", "mean"), rel=("rel", "mean"), n=("date", "count")).reset_index())
wy = wy[wy.n >= 5]
wk = (wy.groupby("woy").agg(avg=("avg", "mean"), rel=("rel", "mean"), rel_min=("rel", "min"),
                            rel_max=("rel", "max"), years=("iso_year", "nunique")).reset_index())
wk["dates"] = wk.woy.map(week_label)

mon = (df.groupby("month").agg(avg=("total_pilgrims", "mean"), median=("total_pilgrims", "median"),
                                rel=("rel", "mean"), std=("rel", "std"), lo=("total_pilgrims", "min"),
                                hi=("total_pilgrims", "max"), days=("date", "count"),
                                wait=("wait_h", "mean")).reset_index())
mon["name"] = mon.month.map(lambda m: MON[m - 1])
HAS_WAIT = df.wait_h.notna().sum() > 30

# ── simple forecasting model: season (week of year, smoothed) x weekday factor ──
dow_f = df.groupby("dow_i").rel.mean()
dow_f = dow_f / dow_f.mean()
df["seas"] = df.rel / df.dow_i.map(dow_f)
_s = df.groupby("woy").seas.mean().reindex(range(1, 54)).interpolate(limit_direction="both")
_ext = pd.concat([_s.iloc[-2:], _s, _s.iloc[:2]])
season = _ext.rolling(3, center=True).mean().iloc[2:-2]
season.index = range(1, 54)
_ts = df.set_index("date").total_pilgrims
baseline = _ts[_ts.index > _ts.index.max() - pd.Timedelta(days=365)].mean()


def predict(dates):
    d = pd.DatetimeIndex(dates)
    wkn = d.isocalendar().week.astype(int).values
    return season.reindex(wkn).values * dow_f.reindex(d.dayofweek).values * baseline


today = pd.Timestamp.today().normalize()
_year_ahead = pd.date_range(today, periods=365)
_pred_year = predict(_year_ahead)
DAY_CUTS = np.quantile(_pred_year, [.2, .4, .6, .8])


def lvl(v, cuts=DAY_CUTS):
    return int(np.searchsorted(cuts, v, side="right"))


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

tabs = st.tabs(["🏠 Plan my visit", "📅 Best months", "🗓️ Best weeks", "📈 Timelines",
                "🔥 Heatmaps", "🎯 Consistency", "📊 Other stats", "🧹 Data"])

# ═════════════════════════ PLAN MY VISIT ═════════════════════════
with tabs[0]:
    # ---- the short answer ----
    best3 = mon.nsmallest(3, "rel")
    worst2 = mon.nlargest(2, "rel")
    wd = df.groupby("dow", observed=True).total_pilgrims.mean()
    best_day, worst_day = wd.idxmin(), wd.idxmax()
    wkend = df[df.dow_i >= 5].total_pilgrims.mean()
    wkday = df[df.dow_i < 5].total_pilgrims.mean()

    section("The short answer", "When should I go?",
            "If you can choose, these are the times when Tirumala has historically had the fewest pilgrims.")
    html(f"""
    <div class="grid3">
    <div class="card good"><div class="lab">✅ Quietest months</div>
    <div class="big">{" · ".join(MONTH_FULL[int(m) - 1] for m in best3.month)}</div>
    <div class="note">About <b>{k(best3.avg.min())}–{k(best3.avg.max())}</b> pilgrims a day, noticeably fewer than the busy season.</div></div>
    <div class="card mid"><div class="lab">📆 Best day of the week</div>
    <div class="big">{best_day}</div>
    <div class="note">Around <b>{k(wd.min())}</b> pilgrims on an average {best_day}, compared with <b>{k(wd.max())}</b> on a {worst_day}.
    Weekdays average {k(wkday)}; weekends {k(wkend)}.</div></div>
    <div class="card bad"><div class="lab">⚠️ Busiest months</div>
    <div class="big">{" · ".join(MONTH_FULL[int(m) - 1] for m in worst2.month)}</div>
    <div class="note">Up to <b>{k(worst2.avg.max())}</b> pilgrims a day on average, and the very busiest days have reached about 98k.</div></div>
    </div>
    """)

    # ---- find my quietest day ----
    section("Plan your dates", "Find my quietest day",
            "Tell us when you can travel and we'll rank every day in that window from calmest to busiest.")
    c1, c2 = st.columns([2, 1])
    with c1:
        rng = st.date_input("I can travel between", value=((today + pd.Timedelta(days=14)).date(),
                                                          (today + pd.Timedelta(days=44)).date()),
                            min_value=today.date(), max_value=(today + pd.Timedelta(days=365)).date(),
                            format="DD/MM/YYYY", help="Pick the same date twice to check a single day.")
    with c2:
        skip_we = st.checkbox("Skip Saturdays & Sundays", value=False)
        st.caption("Estimates use past years' patterns. Festivals aren't predicted.")
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
                wait_txt = ""
                if HAS_WAIT and not np.isnan(mon.set_index("month").wait.get(d.month, np.nan)):
                    wait_txt = (f'<div class="w">⏱ Free-darshan wait is typically '
                                f'~{mon.set_index("month").wait[d.month]:.0f} h in {MON[d.month - 1]}</div>')
                cards += (f'<div class="rcard"><span class="rk">#{r}</span><div class="d">{d:%d %b %Y}</div>'
                          f'<div class="w">{d:%A}</div>{pill(lvl(pv[i]))}'
                          f'<div class="p">≈ {k(pv[i])} pilgrims</div>{wait_txt}</div>')
            html(f'<div class="rgrid">{cards}</div>')

            fig = go.Figure(go.Bar(
                x=win, y=pv, marker_color=[LEVELS[lvl(v)][1] for v in pv],
                customdata=[[f"{d:%A}", LEVELS[lvl(v)][0]] for d, v in zip(win, pv)],
                hovertemplate="%{x|%d %b %Y} · %{customdata[0]}<br>%{customdata[1]} · ≈ %{y:,.0f} pilgrims<extra></extra>"))
            fig.update_layout(yaxis_title="Expected pilgrims", bargap=.15,
                              yaxis_range=[max(0, pv.min() * .6), pv.max() * 1.08])
            st.plotly_chart(style(fig, 300), width="stretch")

    # ---- next 12 months calendar ----
    section("The year ahead", "Crowd calendar", "Green days are the calmest. Hover over a day for details.")
    leg = "".join(f'<span><i style="background:{bg}"></i>{n}</span>' for n, bg, _ in LEVELS)
    cal_html = f'<div class="legend">{leg}</div><div class="cgrid">'
    first = today.replace(day=1)
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
                v = float(predict([d])[0])
                n, bg, fg = LEVELS[lvl(v)]
                cells += (f'<div class="cd" style="background:{bg};color:{fg}" '
                          f'title="{d:%a %d %b %Y} · {n} (≈{k(v)})">{day}</div>')
        cal_html += f'<div class="cal"><div class="cm">{ms:%B %Y}</div><div class="cdays">{cells}</div></div>'
    html(cal_html + "</div>")

    # ---- month guide ----
    section("Month by month", "How busy is each month?",
            "Averages from past years. Even a 'Quiet' month is still a busy temple, just less so.")
    mcuts = np.quantile(mon.rel, [.2, .4, .6, .8])
    tiles = ""
    for _, r in mon.sort_values("month").iterrows():
        i = lvl(r.rel, mcuts)
        n, bg, fg = LEVELS[i]
        w = f'<div class="mwait">⏱ ~{r.wait:.0f} h free-darshan wait</div>' if HAS_WAIT and not np.isnan(r.wait) else ""
        tiles += (f'<div class="mtile" style="--c:{bg}"><div class="mname">{MONTH_FULL[int(r.month) - 1]}</div>'
                  f'<span class="mlevel" style="background:{bg};color:{fg}">{n}</span>'
                  f'<div class="mnum">≈ {k(r.avg)} <span>/ day</span></div>{w}</div>')
    html(f'<div class="mgrid">{tiles}</div>')

    # ---- weekday bars ----
    section("Day by day", "Which day of the week is calmest?")
    wcuts = np.quantile(wd.values, [.2, .4, .6, .8])
    mx = wd.max()
    rows = ""
    for dname, v in wd.items():
        _, bg, _ = LEVELS[lvl(v, wcuts)]
        rows += (f'<div class="wrow"><span class="n">{dname}</span>'
                 f'<div class="wbar"><i style="width:{v / mx * 100:.0f}%;background:{bg}"></i></div>'
                 f'<span class="v">{k(v)}</span></div>')
    html(f'<div class="card">{rows}</div>')

    # ---- good to know ----
    section("Before you book", "Good to know")
    low_wait = ""
    if HAS_WAIT:
        wmin = mon.loc[mon.wait.idxmin()]
        low_wait = (f"<li><b>Quiet isn't the same as short.</b> Even in {MONTH_FULL[int(wmin.month) - 1]}, the "
                    f"calmest month for waiting, free-darshan queues average around {wmin.wait:.0f} hours.</li>")
    html(f"""
    <div class="tips"><ul>
    <li><b>Weekends are busier.</b> Saturdays and Sundays average about {k(wkend)} pilgrims against {k(wkday)} on weekdays.</li>
    <li><b>Festivals and school holidays break the pattern.</b> Brahmotsavam, Vaikunta Ekadasi, Sankranti, summer vacation and long weekends can be far busier than any average. Check TTD's official calendar for your dates.</li>
    {low_wait}
    <li><b>These are estimates.</b> They come from how crowds behaved in {yr_range[0]}–{yr_range[1]}, adjusted for the weekday and time of year. Crowds have been growing, so expect numbers to be a little higher than past years.</li>
    <li><b>Not official.</b> This is an independent tool built from the daily statistics TTD publishes at news.tirumala.org.</li>
    </ul></div>
    """)
    with st.expander("Why do a couple of days show surprisingly low numbers?"):
        low = df.nsmallest(5, "total_pilgrims")[["date", "dow", "total_pilgrims"]]
        low.columns = ["Date", "Weekday", "Pilgrims"]
        st.dataframe(low.style.format({"Pilgrims": "{:,.0f}", "Date": "{:%d %b %Y}"}), hide_index=True)
        st.caption("Very low days such as 7 Sep 2025 and 3 Mar 2026 coincide with lunar eclipses, when the temple "
                   "closes for part of the day. They aren't a reliable 'quiet day' to aim for.")
    html('<div class="foot">Made with 🙏 · Data: news.tirumala.org · Independent project, not affiliated with TTD</div>')

# ═════════════════════════ BEST MONTHS ═════════════════════════
with tabs[1]:
    st.subheader("Average crowd by calendar month")
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
with tabs[2]:
    st.subheader("Crowd level by week of the year")
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
with tabs[3]:
    st.subheader("Monthly timeline")
    mt = df.groupby(df.date.dt.to_period("M")).agg(avg=("total_pilgrims", "mean"), n=("date", "count")).reset_index()
    mt = mt[mt.n >= MIN_DAYS]
    mt["date"] = mt.date.dt.to_timestamp()
    fig = px.line(mt, x="date", y="avg", markers=True, labels={"avg": "Avg pilgrims/day", "date": ""})
    lowm = mt.nsmallest(5, "avg")
    fig.add_trace(go.Scatter(x=lowm.date, y=lowm.avg, mode="markers", marker=dict(color="#2E9E6B", size=13),
                             name="5 quietest months"))
    st.plotly_chart(style(fig, 400), width="stretch")
    st.caption("Months with fewer than 20 days of data (such as the current, unfinished month) are left out.")

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
with tabs[4]:
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
with tabs[5]:
    st.subheader("🎯 Which months are consistently quiet?")
    st.write(f"For each year the months are ranked from quietest to busiest. A month is **quiet** in a year if it "
             f"is one of that year's **{quiet_n} quietest** months (change in the sidebar settings). "
             f"A month needs at least {MIN_DAYS} days of data to be ranked, because a half-finished month "
             f"(like the current one) isn't a fair comparison with a full one.")

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
with tabs[6]:
    opts = {"Tonsures": "tonsures", "Hundi collection (₹ crore)": "hundi_cr", "Laddu sales (lakh)": "laddu_lakh",
            "Annaprasadam (lakh)": "annaprasadam_lakh", "Aswini hospital patients": "aswini_hospital",
            "Free-darshan wait (hours)": "wait_h"}
    opts = {kk: v for kk, v in opts.items() if v in df and df[v].notna().sum() > 30}
    pick = st.selectbox("Metric", list(opts))
    col = opts[pick]
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
with tabs[7]:
    st.subheader("Data quality")
    full_range = pd.date_range(full.date.min(), full.date.max())
    missing = full_range.difference(full.date)
    c = st.columns(3)
    c[0].metric("Rows in CSV", f"{len(full):,}")
    c[1].metric("Suspect rows ignored", len(bad))
    c[2].metric("Missing calendar days", len(missing))
    st.markdown("**Ignored rows** (outside the min/max limits in the settings)")
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