#!/usr/bin/env python3
"""
country_data.py - search, download and plot country data from free public sources.
Understands plain country names, group names and indicator phrases.

Sources
  imf : IMF World Economic Outlook (DataMapper API) - ~130 macro indicators,
        ~200 economies + IMF aggregates, 1980 to projection years
  wb  : World Bank World Development Indicators - ~1,500 indicators,
        ~217 economies + regional/income aggregates

Main command (fetch + table + CSV + PNG chart in one go)
  python country_data.py show --what "gdp growth" --countries "France, Germany"
  python country_data.py show --what inflation --countries "G7" --start 2010
  python country_data.py show --what "government debt" --countries "euro area, United States"
  python country_data.py show --what "life expectancy" --countries "Nigeria, Kenya, Ghana"
  python country_data.py show --what PCPIPCH --countries all --top 20
  python country_data.py show --what "gdp growth" --countries world

Lookups
  python country_data.py resolve --countries "US, South Korea, ASEAN, emerging markets"
  python country_data.py countries --search korea
  python country_data.py groups
  python country_data.py indicators --source imf --search debt
  python country_data.py indicators --source wb --search "co2 per capita"
  python country_data.py info --what NGDP_RPCH

As a module
  from country_data import get_data, plot_data
  df = get_data("imf", "NGDP_RPCH", ["France", "G7"], 2000, 2030)   # years x ISO3
"""

import argparse
import difflib
import json
import re
import sys
import time
import unicodedata
from functools import lru_cache
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

for _s in (sys.stdout, sys.stderr):  # Windows consoles choke on names like "Türkiye"
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
IMF_BASE = "https://www.imf.org/external/datamapper/api/v1"
WB_BASE = "https://api.worldbank.org/v2"
# The IMF site rejects requests with no/browser-less user-agent; this one works.
HEADERS = {"User-Agent": "python-requests/2.34 country_data.py"}
CACHE_DIR = Path.home() / ".country_data_cache"
CACHE_DAYS = 7
THIS_YEAR = time.localtime().tm_year
# WEO country-group membership (from github.com/johnsonice/RA-Skills, MIT). Bundled; URL is fallback.
GROUPS_CSV = HERE / "country_group.csv"
GROUPS_CSV_URL = ("https://raw.githubusercontent.com/johnsonice/RA-Skills/main/"
                  "skills/imf-ra/country_group/country_group.csv")
SOURCE_NAMES = {"imf": "IMF World Economic Outlook", "wb": "World Bank WDI"}

# Keys are normalized (see _norm): lowercase ascii, punctuation -> spaces.
COUNTRY_ALIASES = {
    "us": "USA", "u s": "USA", "usa": "USA", "america": "USA", "united states of america": "USA",
    "uk": "GBR", "u k": "GBR", "britain": "GBR", "great britain": "GBR", "england": "GBR",
    "russia": "RUS", "korea": "KOR", "south korea": "KOR", "north korea": "PRK",
    "iran": "IRN", "turkey": "TUR", "turkiye": "TUR", "china": "CHN", "mainland china": "CHN",
    "hong kong": "HKG", "macau": "MAC", "macao": "MAC", "taiwan": "TWN", "vietnam": "VNM",
    "egypt": "EGY", "czechia": "CZE", "czech": "CZE", "slovakia": "SVK", "drc": "COD",
    "dr congo": "COD", "democratic republic congo": "COD", "congo": "COG",
    "ivory coast": "CIV", "cote d ivoire": "CIV", "syria": "SYR", "laos": "LAO",
    "venezuela": "VEN", "bolivia": "BOL", "tanzania": "TZA", "kyrgyzstan": "KGZ",
    "moldova": "MDA", "macedonia": "MKD", "north macedonia": "MKD", "bahamas": "BHS",
    "gambia": "GMB", "yemen": "YEM", "micronesia": "FSM", "cape verde": "CPV",
    "swaziland": "SWZ", "eswatini": "SWZ", "burma": "MMR", "holland": "NLD",
    "netherlands": "NLD", "uae": "ARE", "emirates": "ARE", "saudi": "SAU", "kosovo": "KOS",
}
# Plain-language group names -> abbreviation used in the WEO group CSV column names.
GROUP_ALIASES = {
    "advanced": "AE", "advanced economies": "AE", "advanced countries": "AE", "developed": "AE",
    "developed countries": "AE", "developed economies": "AE",
    "emerging": "EM", "emerging markets": "EM", "emerging economies": "EM",
    "emerging market economies": "EM", "emerging market": "EM",
    "emdes": "EMDE", "developing": "EMDE", "developing countries": "EMDE",
    "developing economies": "EMDE", "emerging and developing economies": "EMDE",
    "low income": "LIDC", "low income countries": "LIDC", "lics": "LIDC", "lidcs": "LIDC",
    "euro area": "EA", "eurozone": "EA", "euro zone": "EA", "european union": "EU",
    "sub saharan africa": "SSA", "latin america": "LAC", "asean": "ASEAN-5",
    "g 7": "G7", "g 20": "G20", "hipcs": "HIPC", "middle east and north africa": "MENA",
}
CODE_FIXES = {"imf": {"KOS": "UVK", "XKX": "UVK"}, "wb": {"KOS": "XKX", "UVK": "XKX"}}
WORLD_WORDS ={"world", "global", "whole world", "world economy"}
ALL_WORDS = {"all", "all countries", "every country", "everything", "all economies"}

# Plain-language indicator phrases -> (source, code).
COMMON_INDICATORS = {
    "gdp growth": ("imf", "NGDP_RPCH"), "real gdp growth": ("imf", "NGDP_RPCH"),
    "growth": ("imf", "NGDP_RPCH"), "economic growth": ("imf", "NGDP_RPCH"),
    "inflation": ("imf", "PCPIPCH"), "cpi inflation": ("imf", "PCPIPCH"),
    "consumer price inflation": ("imf", "PCPIPCH"), "inflation rate": ("imf", "PCPIPCH"),
    "unemployment": ("imf", "LUR"), "unemployment rate": ("imf", "LUR"),
    "debt": ("imf", "GGXWDG_NGDP"), "government debt": ("imf", "GGXWDG_NGDP"),
    "public debt": ("imf", "GGXWDG_NGDP"), "debt to gdp": ("imf", "GGXWDG_NGDP"),
    "current account": ("imf", "BCA_NGDPD"), "current account balance": ("imf", "BCA_NGDPD"),
    "gdp": ("imf", "NGDPD"), "nominal gdp": ("imf", "NGDPD"), "gdp usd": ("imf", "NGDPD"),
    "gdp per capita": ("imf", "NGDPDPC"), "income per capita": ("imf", "NGDPDPC"),
    "fiscal balance": ("imf", "GGXCNL_NGDP"), "budget balance": ("imf", "GGXCNL_NGDP"),
    "deficit": ("imf", "GGXCNL_NGDP"), "fiscal deficit": ("imf", "GGXCNL_NGDP"),
    "government revenue": ("imf", "rev"), "government expenditure": ("imf", "exp"),
    "government spending": ("imf", "exp"),
    "population": ("wb", "SP.POP.TOTL"), "life expectancy": ("wb", "SP.DYN.LE00.IN"),
    "co2": ("wb", "EN.GHG.CO2.PC.CE.AR5"), "co2 emissions": ("wb", "EN.GHG.CO2.PC.CE.AR5"),
    "emissions per capita": ("wb", "EN.GHG.CO2.PC.CE.AR5"),
}
_STOP = {"the", "of", "in", "for", "a", "an", "data", "show", "plot", "chart", "me", "on"}
_NAME_NOISE = {"the", "of", "republic", "rep", "islamic", "principality", "grand", "duchy",
               "plurinational", "bolivarian", "sar", "province"}


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s.replace("&", " and "))
    return " ".join(w for w in s.split() if w not in _NAME_NOISE)


# --------------------------------------------------------------------------- #
# HTTP + cache
# --------------------------------------------------------------------------- #
def _get_json(url, params=None, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=60)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == retries - 1:
                raise RuntimeError(f"Request failed: {url} ({e})") from e
            time.sleep(2 * (attempt + 1))


def _cached(name, loader):
    """Cache slow metadata calls (country/indicator lists) on disk for a week."""
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{name}.json"
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_DAYS * 86400:
        return json.loads(path.read_text(encoding="utf-8"))
    data = loader()
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


# --------------------------------------------------------------------------- #
# Metadata: countries, groups, indicators
# --------------------------------------------------------------------------- #
def imf_countries():
    return _cached("imf_countries", lambda: {
        k: v.get("label") for k, v in _get_json(f"{IMF_BASE}/countries")["countries"].items()})


def imf_aggregates():
    """IMF aggregate codes (ADVEC, EURO, WEOWORLD...) - published as their own series."""
    def load():
        out = {}
        for kind in ("groups", "regions"):
            for k, v in _get_json(f"{IMF_BASE}/{kind}")[kind].items():
                out[k] = (v.get("label") or "").strip()
        return out
    return _cached("imf_aggregates", load)


def imf_indicators():
    def load():
        data = _get_json(f"{IMF_BASE}/indicators")["indicators"]
        return {k: {"label": (v.get("label") or "").strip(), "unit": (v.get("unit") or "").strip(),
                    "source": v.get("source") or "", "description": v.get("description") or ""}
                for k, v in data.items() if k}
    return _cached("imf_indicators", load)


def _wb_pages(url, params):
    params = {**params, "format": "json", "per_page": 20000}
    first = _get_json(url, params)
    if not isinstance(first, list) or len(first) < 2:
        msg = first[0].get("message") if isinstance(first, list) and first else first
        raise RuntimeError(f"World Bank API error: {msg}")
    rows, pages = list(first[1] or []), first[0].get("pages", 1)
    for p in range(2, pages + 1):
        rows += _get_json(url, {**params, "page": p})[1] or []
    return rows


def wb_countries():
    """{iso3: {label, region, income, aggregate}}"""
    def load():
        return {c["id"]: {"label": c["name"],
                          "region": c["region"]["value"].strip(),
                          "income": c["incomeLevel"]["value"].strip(),
                          "aggregate": c["region"]["value"].strip() == "Aggregates"}
                for c in _wb_pages(f"{WB_BASE}/country", {})}
    return _cached("wb_countries", load)


def wb_indicators():
    def load():
        return {i["id"]: {"label": i["name"], "unit": i.get("unit") or "",
                          "source": "World Development Indicators",
                          "description": i.get("sourceNote") or ""}
                for i in _wb_pages(f"{WB_BASE}/source/2/indicator", {})}
    return _cached("wb_indicators", load)


@lru_cache(maxsize=1)
def _groups_table():
    if GROUPS_CSV.exists():
        return pd.read_csv(GROUPS_CSV, encoding="utf-8-sig")
    r = requests.get(GROUPS_CSV_URL, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.content.decode("utf-8-sig")))


@lru_cache(maxsize=1)
def weo_groups():
    """{group name: [ISO3 members]}"""
    df = _groups_table()
    return {c: df.loc[df[c] == 1, "countrycode"].tolist() for c in df.columns[5:]}


def find_group(query):
    """'G7', 'AE', 'advanced economies', 'euro area', 'ASEAN-5' ... -> WEO group name or None."""
    n = _norm(query)
    target = _norm(GROUP_ALIASES.get(n, query))
    groups = list(weo_groups())
    exact = []
    for name in groups:
        abbrevs = [_norm(a) for a in re.findall(r"\(([^)]+)\)", name)]
        plain = _norm(re.sub(r"\([^)]*\)", " ", name))
        if target in abbrevs or target in (plain, _norm(name)):
            exact.append(name)
    if exact:  # "(SSA)" also tags "SSA: Oil Exporters" etc. - the shortest name is the whole group
        return min(exact, key=len)
    if len(n) >= 4:
        hits = [g for g in groups if not g.startswith("SPR-")
                and _norm(re.sub(r"\([^)]*\)", " ", g)).startswith(n)]
        if len(hits) == 1:
            return hits[0]
    return None


@lru_cache(maxsize=1)
def country_names():
    """{iso3: short readable name} for real countries."""
    names = {k: v["label"] for k, v in wb_countries().items() if not v["aggregate"]}
    names.update({k: v for k, v in imf_countries().items() if v})
    df = _groups_table()
    names.update(dict(zip(df["countrycode"], df["countryname_s"])))
    return names


def display_names():
    names = {k: v["label"] for k, v in wb_countries().items()}
    names.update(imf_aggregates())
    names.update(country_names())
    return names


@lru_cache(maxsize=1)
def _country_index():
    """normalized name -> ISO3 (None when a name is ambiguous)."""
    idx = {}

    def add(key, iso):
        if not key:
            return
        if key in idx and idx[key] != iso:
            idx[key] = None
        else:
            idx.setdefault(key, iso)

    df = _groups_table()
    sources = [country_names().items(), zip(df["countrycode"], df["countryname"]),
               ((k, v["label"]) for k, v in wb_countries().items() if not v["aggregate"]),
               imf_countries().items()]
    for pairs in sources:
        for iso, name in pairs:
            if not isinstance(name, str):
                continue
            add(_norm(name), iso)
            add(_norm(name.split(",")[0]), iso)
            add(_norm(re.sub(r"\([^)]*\)", " ", name)), iso)
    return idx


def all_countries(source):
    if source == "imf":
        return sorted(k for k in imf_countries() if k not in imf_aggregates())
    return sorted(k for k, v in wb_countries().items() if not v["aggregate"])


# --------------------------------------------------------------------------- #
# Resolution: free text -> codes
# --------------------------------------------------------------------------- #
def _resolve_one(text, source):
    """Returns (codes, explanation) or None."""
    t = text.strip()
    n = _norm(t)
    if not n:
        return [], None
    if n in ALL_WORDS:
        codes = all_countries(source)
        return codes, f"{t} -> all {len(codes)} economies"
    if n in WORLD_WORDS:
        code = "WEOWORLD" if source == "imf" else "WLD"
        return [code], f"{t} -> world aggregate ({code})"

    up = t.upper()
    agg = imf_aggregates() if source == "imf" else {
        k: v["label"] for k, v in wb_countries().items() if v["aggregate"]}
    if up in agg:
        return [up], f"{t} -> aggregate series {up} ({agg[up]})"
    if up in country_names():
        return [up], None
    if n in COUNTRY_ALIASES:
        iso = COUNTRY_ALIASES[n]
        return [iso], f"{t} -> {country_names().get(iso, iso)} ({iso})"
    idx = _country_index()
    if idx.get(n):
        return [idx[n]], None

    group = find_group(t)
    if group:
        members = weo_groups()[group]
        return members, f"{t} -> WEO group '{group}' ({len(members)} countries)"

    for code, label in agg.items():  # e.g. "Euro area" wording of an aggregate label
        if _norm(label) == n:
            return [code], f"{t} -> aggregate series {code} ({label})"

    if len(n) >= 4:
        hits = {iso for key, iso in idx.items() if iso and (" " + key).find(" " + n) >= 0}
        if len(hits) == 1:
            iso = hits.pop()
            return [iso], f"{t} -> {country_names().get(iso, iso)} ({iso})"
    close = difflib.get_close_matches(n, [k for k, v in idx.items() if v], n=1, cutoff=0.85)
    if close:
        iso = idx[close[0]]
        return [iso], f"{t} -> {country_names().get(iso, iso)} ({iso}) [closest match]"
    return None


def resolve_countries(countries, source="imf", verbose=True):
    """Free text ('France, Germany and G7') or a list -> list of ISO3/aggregate codes."""
    if countries is None:
        countries = ["all"]
    parts = countries if isinstance(countries, (list, tuple)) else [countries]
    pieces = []
    for p in parts:  # whole string first, so "Korea, Republic of" still works
        pieces += [p] if _resolve_one(p, source) is not None else re.split(r"[,;+]", p)

    out, notes, failed = [], [], []
    for piece in pieces:
        res = _resolve_one(piece, source)
        if res is None and re.search(r"\band\b|&", piece):
            subs = [_resolve_one(s, source) for s in re.split(r"\band\b|&", piece)]
            if all(s is not None for s in subs):
                res = ([c for s in subs for c in s[0]], "; ".join(s[1] for s in subs if s[1]) or None)
        if res is None:
            failed.append(piece.strip())
            continue
        out += res[0]
        if res[1]:
            notes.append(res[1])

    if failed:
        keys = [k for k, v in _country_index().items() if v] + [_norm(g) for g in weo_groups()]
        tips = []
        for f in failed:
            sugg = difflib.get_close_matches(_norm(f), keys, n=3, cutoff=0.5)
            tips.append(f"'{f}'" + (f" (did you mean: {', '.join(sugg)}?)" if sugg else ""))
        raise RuntimeError("Could not recognise: " + "; ".join(tips) +
                           "\nTry: country_data.py countries --search <name>  or  groups")
    if verbose:
        for n in notes:
            print(f"  {n}", file=sys.stderr)
    return list(dict.fromkeys(out))


def _score(tokens, text):
    return sum(1 for t in tokens if re.search(rf"\b{re.escape(t)}", text)) / len(tokens)


def resolve_indicator(what, source="auto"):
    """Code or phrase -> (source, code, [alternative (source, code, label)])."""
    w = what.strip()
    sources = ["imf", "wb"] if source == "auto" else [source]
    for s in sources:
        meta = imf_indicators() if s == "imf" else wb_indicators()
        for cand in (w, w.upper()):
            if cand in meta:
                return s, cand, []
    n = _norm(w)
    if n in COMMON_INDICATORS and COMMON_INDICATORS[n][0] in sources:
        s, code = COMMON_INDICATORS[n]
        return s, code, []

    tokens = [t for t in n.split() if t not in _STOP] or n.split()
    ranked = []
    for s in sources:
        meta = imf_indicators() if s == "imf" else wb_indicators()
        for code, m in meta.items():
            sc = _score(tokens, _norm(m["label"] + " " + code))
            if sc >= 0.5:
                bonus = 0.05 if s == "imf" else 0
                ranked.append((sc + bonus - len(m["label"]) / 2000, s, code, m["label"]))
    if not ranked:
        raise RuntimeError(f"No indicator matches '{what}'. "
                           "Try: country_data.py indicators --source wb --search <words>")
    ranked.sort(reverse=True)
    _, s, code, _ = ranked[0]
    return s, code, [(r[1], r[2], r[3]) for r in ranked[1:6]]


def list_countries(search=None):
    imf, wb = set(imf_countries()) - set(imf_aggregates()), set(all_countries("wb"))
    codes = sorted(imf | wb)
    wbm = wb_countries()
    df = pd.DataFrame({
        "iso3": codes,
        "name": [country_names().get(c, c) for c in codes],
        "in_imf": [c in imf for c in codes],
        "in_wb": [c in wb for c in codes],
        "wb_region": [wbm.get(c, {}).get("region", "") for c in codes],
        "wb_income": [wbm.get(c, {}).get("income", "") for c in codes],
    })
    if search:
        s = _norm(search)
        df = df[df["iso3"].str.lower().eq(s) | df["name"].map(_norm).str.contains(s, regex=False)]
    return df.reset_index(drop=True)


def list_indicators(source, search=None):
    meta = imf_indicators() if source == "imf" else wb_indicators()
    df = pd.DataFrame([{"code": k, **v} for k, v in meta.items()])
    if search:
        text = (df["code"] + " " + df["label"] + " " + df["description"]).map(_norm)
        mask = pd.Series(True, index=df.index)
        for w in _norm(search).split():
            mask &= text.str.contains(w, regex=False)
        df = df[mask]
    return df.drop(columns="description").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def get_data(source, indicator, countries=None, start=None, end=None):
    """Wide DataFrame: index = year, columns = ISO3/aggregate codes.
    `countries` may be free text, a list of names/codes/groups, or None/'all'."""
    codes = resolve_countries(countries, source)
    fix = CODE_FIXES.get(source, {})  # e.g. Kosovo is KOS in the group file, UVK/XKX in the APIs
    codes = list(dict.fromkeys(fix.get(c, c) for c in codes))
    if source == "imf":
        # The DataMapper returns every economy for an indicator; filter locally.
        values = _get_json(f"{IMF_BASE}/{indicator}").get("values", {}).get(indicator)
        if not values:
            raise RuntimeError(f"No IMF data for indicator '{indicator}'.")
        df = pd.DataFrame({c: values[c] for c in codes if c in values})
    elif source == "wb":
        rows = []
        date = f"{start or 1960}:{end or 2100}"
        for i in range(0, len(codes), 60):  # keep URLs short
            chunk = ";".join(codes[i:i + 60])
            rows += [(r["countryiso3code"] or r["country"]["id"], r["date"], r["value"])
                     for r in _wb_pages(f"{WB_BASE}/country/{chunk}/indicator/{indicator}",
                                        {"date": date})
                     if r["value"] is not None]
        df = pd.DataFrame(rows, columns=["country", "year", "value"]).pivot_table(
            index="year", columns="country", values="value", aggfunc="first")
    else:
        raise ValueError("source must be 'imf' or 'wb'")

    if df.empty:
        raise RuntimeError(f"No data for {indicator} for: {', '.join(codes[:20])}")
    df.index = df.index.astype(int)
    df = df.sort_index()
    if start:
        df = df[df.index >= int(start)]
    if end:
        df = df[df.index <= int(end)]
    df.index.name = "year"
    df = df.dropna(how="all").dropna(axis=1, how="all")

    missing = [c for c in codes if c not in df.columns]
    if missing:
        shown = ", ".join(missing[:15]) + (" ..." if len(missing) > 15 else "")
        print(f"  no data for {len(missing)} of {len(codes)}: {shown}", file=sys.stderr)
    return df


def to_long(df):
    return df.reset_index().melt(id_vars="year", var_name="country", value_name="value").dropna()


def _meta(source, indicator):
    return (imf_indicators() if source == "imf" else wb_indicators()).get(indicator, {})


# --------------------------------------------------------------------------- #
# Plotting
# --------------------------------------------------------------------------- #
def plot_data(df, title="", unit="", source_note="", kind="line", top=None, year=None,
              names=None, out=None, show=False, forecast_from=None):
    """kind='line': one line per economy (best for <= ~12); kind='bar': ranking for one year."""
    import matplotlib
    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    names = names or {}
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

    if kind == "bar":
        year = year or _default_year(df, forecast_from)
        s = df.loc[year].dropna().sort_values(ascending=False)
        if top:
            s = s.head(top)
        s.index = [names.get(c, c) for c in s.index]
        fig, ax = plt.subplots(figsize=(9, max(3, 0.28 * len(s) + 1)))
        ax.barh(s.index[::-1], s.values[::-1], color="#2a6fb0")
        ax.axvline(0, color="#555", lw=0.8)
        ax.set_xlabel(unit)
        ax.grid(axis="x", alpha=0.3)
        ax.tick_params(axis="y", labelsize=8 if len(s) > 30 else 10)
        title = f"{title}, {year}"
    else:
        many = df.shape[1] > 12
        fig, ax = plt.subplots(figsize=(10, 5.5))
        for col in df.columns:
            ax.plot(df.index, df[col], lw=0.8 if many else 1.8, alpha=0.5 if many else 1,
                    label=names.get(col, col))
        if many:
            ax.plot(df.index, df.median(axis=1), color="black", lw=2.5, label="Median")
            ax.legend(handles=ax.lines[-1:], frameon=False)
        else:
            ax.legend(frameon=False, fontsize=9, ncol=2 if df.shape[1] > 6 else 1)
        if forecast_from and df.index.max() >= forecast_from:
            ax.axvspan(forecast_from - 0.5, df.index.max() + 0.5, color="grey", alpha=0.12)
            ax.text(forecast_from, ax.get_ylim()[1], " projections", va="top", fontsize=8, color="#555")
        if df.min().min() < 0 < df.max().max():
            ax.axhline(0, color="#555", lw=0.8)
        ax.set_ylabel(unit)
        ax.grid(axis="y", alpha=0.3)

    fmt = FuncFormatter(lambda v, _: f"{v:,.0f}" if abs(v) >= 1000 else f"{v:g}")
    (ax.xaxis if kind == "bar" else ax.yaxis).set_major_formatter(fmt)
    ax.set_title(title, loc="left", fontweight="bold")
    if source_note:
        fig.text(0.01, 0.01, f"Source: {source_note}", fontsize=8, color="#666")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    if out:
        fig.savefig(out, dpi=150)
    if show:
        plt.show()
    plt.close(fig)


def _default_year(df, forecast_from=None):
    """Latest year where at least half the economies report; never a projection year."""
    counts = df.notna().sum(axis=1)
    if forecast_from:
        counts = counts[counts.index < forecast_from] if (counts.index < forecast_from).any() else counts
    return int(counts[counts >= counts.max() / 2].index.max())


# --------------------------------------------------------------------------- #
# The one-shot command: resolve -> fetch -> table -> CSV -> chart
# --------------------------------------------------------------------------- #
def show(what, countries=None, source="auto", start=None, end=None, kind=None, top=None,
         year=None, outdir="country_data_output", chart=True, open_window=False, xlsx=False):
    src, code, alts = resolve_indicator(what, source)
    meta = _meta(src, code)
    label, unit = meta.get("label") or code, meta.get("unit") or ""
    if start is None and kind != "bar":
        start = 2000
    print(f"Indicator : {label} [{code}] - {SOURCE_NAMES[src]}" + (f", {unit}" if unit else ""))
    if alts:
        print("            other matches: " + "; ".join(f"{c} ({l}, {s})" for s, c, l in alts[:4]))

    df = get_data(src, code, countries, start, end)
    names = display_names()
    forecast = THIS_YEAR if src == "imf" else None
    print(f"Economies : {df.shape[1]}  |  Years: {df.index.min()}-{df.index.max()}"
          + (f"  |  {THIS_YEAR} onward are IMF projections" if forecast and df.index.max() >= THIS_YEAR else ""))

    kind = kind or ("bar" if df.shape[1] > 12 else "line")
    print()
    if df.shape[1] <= 12:
        table = df.tail(12).rename(columns=lambda c: names.get(c, c))
        print(table.round(2).to_string())
    else:
        y = year or _default_year(df, forecast)
        s = df.loc[y].dropna().sort_values(ascending=False).rename(index=lambda c: names.get(c, c))
        print(f"Ranking {y} ({len(s)} economies reporting) - top 10 / bottom 5:")
        print(pd.concat([s.head(10), s.tail(5)]).round(2).to_string())
        print(f"Median: {s.median():.2f}")

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{code}_{'_'.join(df.columns[:4])}"
                  + ("_etc" if df.shape[1] > 4 else "")).strip("_")
    data_path = out / f"{slug}.{'xlsx' if xlsx else 'csv'}"
    export = df.rename(columns=lambda c: f"{c} - {names.get(c, c)}")
    export.to_excel(data_path) if xlsx else export.to_csv(data_path)
    print(f"\nData saved : {data_path.resolve()}")

    if chart:
        png = out / f"{slug}_{kind}.png"
        plot_data(df, title=label, unit=unit, source_note=SOURCE_NAMES[src], kind=kind, top=top,
                  year=year, names=names, out=png, show=open_window, forecast_from=forecast)
        print(f"Chart saved: {png.resolve()}")
    return df


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _print(df, max_rows=300):
    with pd.option_context("display.max_rows", max_rows, "display.width", 200,
                           "display.max_colwidth", 70):
        print(df.to_string(index=False) if len(df) <= max_rows else df)


def interactive():
    print("Country data - IMF WEO & World Bank WDI  (Ctrl+C to quit)\n")
    what = input("What data? (e.g. 'gdp growth', 'inflation', 'life expectancy'): ").strip()
    c = input("Which countries / groups? (e.g. 'France, Germany', 'G7', 'all'): ").strip()
    start = input("From year [2000]: ").strip()
    show(what, c or "all", start=int(start) if start else None, open_window=True)


def main():
    if len(sys.argv) == 1:
        return interactive()

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    for name in ("show", "fetch", "plot"):
        s = sub.add_parser(name, help="get data (+ chart) for countries/groups"
                           if name == "show" else f"alias of show{' without chart' if name == 'fetch' else ''}")
        s.add_argument("--what", "--indicator", dest="what", required=True,
                       help="indicator code or phrase, e.g. NGDP_RPCH, 'gdp growth', 'life expectancy'")
        s.add_argument("--countries", default="all",
                       help="names, ISO3 codes, groups or 'all', e.g. 'France, US, G7' (default all)")
        s.add_argument("--source", choices=["auto", "imf", "wb"], default="auto")
        s.add_argument("--start", type=int)
        s.add_argument("--end", type=int)
        s.add_argument("--kind", choices=["line", "bar"], help="default: line if <=12 economies, else bar")
        s.add_argument("--top", type=int, help="bar chart: top N economies")
        s.add_argument("--year", type=int, help="bar chart / ranking year (default latest actual)")
        s.add_argument("--outdir", default="country_data_output")
        s.add_argument("--xlsx", action="store_true", help="save data as Excel instead of CSV")
        s.add_argument("--open", action="store_true", help="also open the chart in a window")

    s = sub.add_parser("resolve", help="show how names/groups are understood")
    s.add_argument("--countries", required=True)
    s.add_argument("--source", choices=["imf", "wb"], default="imf")
    s = sub.add_parser("countries", help="list every country (ISO3 codes)")
    s.add_argument("--search")
    sub.add_parser("groups", help="list group names and aggregate codes")
    s = sub.add_parser("indicators", help="search indicators")
    s.add_argument("--source", choices=["imf", "wb"], default="imf")
    s.add_argument("--search")
    s = sub.add_parser("info", help="full description of one indicator")
    s.add_argument("--what", "--indicator", dest="what", required=True)
    s.add_argument("--source", choices=["auto", "imf", "wb"], default="auto")

    a = p.parse_args()
    if a.cmd in ("show", "fetch", "plot"):
        show(a.what, a.countries, a.source, a.start, a.end, a.kind, a.top, a.year,
             a.outdir, chart=a.cmd != "fetch", open_window=a.open, xlsx=a.xlsx)
    elif a.cmd == "resolve":
        codes = resolve_countries(a.countries, a.source)
        names = display_names()
        for c in codes:
            print(f"{c}  {names.get(c, '')}")
    elif a.cmd == "countries":
        _print(list_countries(a.search))
    elif a.cmd == "groups":
        print("== Groups (expanded to member countries; use the name or the (ABBR)) ==")
        for g, m in weo_groups().items():
            print(f"  {g:<70} {len(m)}")
        print("\n== IMF aggregate series (use code with IMF indicators) ==")
        for k, v in imf_aggregates().items():
            print(f"  {k:<10} {v}")
        print("\n== World Bank aggregate series (use code with WB indicators) ==")
        for k, v in wb_countries().items():
            if v["aggregate"]:
                print(f"  {k:<10} {v['label']}")
    elif a.cmd == "indicators":
        _print(list_indicators(a.source, a.search))
    elif a.cmd == "info":
        src, code, _ = resolve_indicator(a.what, a.source)
        print(json.dumps({"source": src, "code": code, **_meta(src, code)}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, KeyboardInterrupt) as e:
        sys.exit(f"\nERROR: {e}" if str(e) else "")
