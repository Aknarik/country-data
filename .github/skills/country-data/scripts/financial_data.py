#!/usr/bin/env python3
"""
financial_data.py - IMF Financial Soundness Indicators (quarterly), BIS credit-to-GDP
ratios, and a one-sided Hodrick-Prescott filter for the credit-to-GDP gap.

Sources (public, no key needed)
  IMF FSI : IMF SDMX 3.0 API, dataflow IMF.STA:FSIC (core FSIs), quarterly
  BIS     : BIS SDMX API, dataflow WS_CREDIT_GAP - credit to the private non-financial
            sector from all sectors, % of GDP (adjusted for breaks), quarterly
  IMF MFS : IMF SDMX 3.0 API, dataflow IMF.STA:MFS_DC (depository corporations survey),
            annual, divided by nominal GDP from IMF.RES:WEO - used for Gulf countries that
            BIS does not cover (Kuwait, UAE, Qatar, Oman)

MFS credit measure
  Claims on other sectors (DCORP_A_ACO_S1_Z) minus claims on public non-financial
  corporations (DCORP_A_ACO_S11001), in domestic currency. The narrower "claims on
  private sector" series (DCORP_A_ACO_PS) has a reclassification break for Kuwait
  (about 98% of GDP in 2015 but 4% in 2024, the rest moved to other financial
  corporations), which would create a false gap; the measure used here is continuous.

One-sided HP filter
  For each period t, a standard (two-sided) HP filter is run on the data available
  up to t only, and the trend value at t is kept. This uses no future information,
  as in the Basel III countercyclical capital buffer guide.
  Default smoothing (lambda): quarterly 400,000; annual 100,000 (override with --lamb).
  gap = ratio - trend (percentage points of GDP).
  As BIS does, a trend is reported only once 10 years of data are available (--min-obs).
  With these defaults the quarterly trend reproduces BIS's published credit-to-GDP trend.

Usage
  python financial_data.py fsi    --countries "USA,GBR,KWT" --out fsi.csv
  python financial_data.py credit --countries "US,GB,DE"    --out credit_gap.csv
  python financial_data.py credit --countries all --out credit_gap.xlsx
  python financial_data.py credit --countries US --annual           # annual averages, lambda 100,000
  python financial_data.py credit --countries US --plot us_gap.png
  python financial_data.py mfs    --countries "KWT,ARE,QAT,OMN" --out gulf_gap.csv --plot gulf.png
  python financial_data.py mfs    --non-oil-gdp non_oil_gdp.csv --out gulf_nonoil_gap.csv --plot gulf.png

Non-oil GDP
  For large oil exporters the ratio can use non-oil GDP instead of total GDP, so that oil-price
  swings do not move the denominator. Public IMF data has no non-oil GDP series, so it is read
  from a user file (CSV or XLSX) with columns: country (ISO3), year, non_oil_gdp (millions of
  domestic currency, nominal), and optionally source. Only country-years in the file are used.

As a module
  from financial_data import fetch_fsi, fetch_bis_credit_gdp, hp_one_sided, credit_gap
  from financial_data import mfs_credit_to_gdp_with_gap
"""

import argparse
import sys
from io import StringIO

import numpy as np
import pandas as pd
import requests

IMF_SDMX = "https://api.imf.org/external/sdmx/3.0"
BIS_SDMX = "https://stats.bis.org/api/v2"
HEADERS = {"User-Agent": "python-requests/2.34 country_data.py"}
LAMBDA = {"Q": 400_000, "A": 100_000}
PERIODS_PER_YEAR = {"Q": 4, "A": 1}
MIN_YEARS = 10  # BIS publishes a trend only after 10 years of data
GULF_MFS = ["KWT", "ARE", "QAT", "OMN"]  # Saudi Arabia: use BIS (longer); Bahrain: no MFS data
GULF_NAMES = {"KWT": "Kuwait", "ARE": "United Arab Emirates", "QAT": "Qatar", "OMN": "Oman",
              "SAU": "Saudi Arabia", "BHR": "Bahrain"}
MFS_OTHER_SECTORS, MFS_PUBLIC_NFC = "DCORP_A_ACO_S1_Z", "DCORP_A_ACO_S11001"

# Core FSIs (IMF FSIC dataflow). Code -> short name.
CORE_FSI = {
    "FSI688_CFSI_PT": "Regulatory capital to risk-weighted assets",
    "FSI626_CFSI_PT": "Tier 1 capital to risk-weighted assets",
    "FSI15_CFSI_PT": "Common equity Tier 1 capital to risk-weighted assets",
    "T1KTA_CFSI_PT": "Tier 1 capital to assets",
    "AQ12_CFSI_PT": "Nonperforming loans to total gross loans",
    "FSI17_CFSI_PT": "Nonperforming loans net of provisions to capital",
    "AQ14_CFSI_PT": "Provisions to nonperforming loans",
    "AQ1_CFSI_PT": "Loan concentration by economic activity",
    "FSI524_CFSI_PT": "Residential real estate loans to total gross loans",
    "ROA_CFSI_PT": "Return on assets",
    "ROE_CFSI_PT": "Return on equity",
    "FSI99_CFSI_PT": "Interest margin to gross income",
    "FSI107_CFSI_PT": "Noninterest expenses to gross income",
    "FSI765_CFSI_PT": "Liquid assets to short-term liabilities",
    "FSI288_CFSI_PT": "Liquidity coverage ratio",
    "FSI289_CFSI_PT": "Net stable funding ratio",
    "FSI555_CFSI_PT": "Net open position in foreign exchange to capital",
}


def _get(url, params=None, headers=None, timeout=180):
    r = requests.get(url, params=params, headers={**HEADERS, **(headers or {})}, timeout=timeout)
    if r.status_code == 404:
        return ""
    r.raise_for_status()
    r.encoding = "utf-8"  # BIS/IMF send UTF-8 without declaring it
    return r.text


def _codes(countries):
    if countries is None or str(countries).strip().lower() in ("", "all", "*"):
        return "*"
    items = countries if isinstance(countries, (list, tuple)) else str(countries).split(",")
    return "+".join(c.strip().upper() for c in items if c.strip())


# --------------------------------------------------------------------------- #
# One-sided HP filter
# --------------------------------------------------------------------------- #
def hp_two_sided(y, lamb):
    """Standard HP trend: minimises sum (y - t)^2 + lamb * sum (second diff of t)^2."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 3:
        return y.copy()
    d = np.zeros((n - 2, n))
    idx = np.arange(n - 2)
    d[idx, idx], d[idx, idx + 1], d[idx, idx + 2] = 1.0, -2.0, 1.0
    return np.linalg.solve(np.eye(n) + lamb * d.T @ d, y)


def hp_one_sided(series, lamb=None, freq=None, min_obs=None):
    """One-sided (real-time) HP trend of a pandas Series indexed by period.

    trend[t] = last value of the two-sided HP trend fitted on observations up to t.
    lamb defaults to 400,000 for quarterly and 100,000 for annual data.
    Missing values are dropped first. min_obs (default: 10 years + 1 period) is the
    number of observations needed before a trend is reported; use 1 for all periods."""
    s = pd.Series(series).dropna().astype(float)
    freq = freq or _infer_freq(s.index)
    if lamb is None:
        lamb = LAMBDA[freq]
    if min_obs is None:
        min_obs = MIN_YEARS * PERIODS_PER_YEAR[freq] + 1
    y = s.to_numpy()
    trend = np.full(len(y), np.nan)
    for t in range(max(min_obs, 1), len(y) + 1):
        trend[t - 1] = hp_two_sided(y[:t], lamb)[-1]
    return pd.Series(trend, index=s.index, name="trend")


def _infer_freq(index):
    first = str(index[0])
    return "Q" if "Q" in first.upper() else "A"


def credit_gap(ratio, lamb=None, freq=None, min_obs=None):
    """DataFrame with ratio, one-sided HP trend and gap (ratio - trend)."""
    ratio = pd.Series(ratio).dropna().astype(float)
    trend = hp_one_sided(ratio, lamb, freq, min_obs)
    return pd.DataFrame({"ratio": ratio, "trend": trend, "gap": ratio - trend})


# --------------------------------------------------------------------------- #
# BIS credit-to-GDP
# --------------------------------------------------------------------------- #
def fetch_bis_credit_gdp(countries="all", start=None, include_bis_gap=True):
    """Long DataFrame: country, period, series (ratio / bis_trend / bis_gap), value.
    Countries are BIS 2-letter codes (US, GB, DE, XM = euro area...) or 'all'."""
    types = "A+B+C" if include_bis_gap else "A"
    params = {"format": "csv"}
    if start:
        params["startPeriod"] = str(start)
    text = _get(f"{BIS_SDMX}/data/dataflow/BIS/WS_CREDIT_GAP/1.0/Q.{_codes(countries)}.P.A.{types}",
                params)
    if not text:
        raise RuntimeError(f"No BIS credit-to-GDP data for {countries}")
    df = pd.read_csv(StringIO(text))
    names = {"A": "ratio", "B": "bis_trend", "C": "bis_gap"}
    return pd.DataFrame({"country": df["BORROWERS_CTY"], "period": df["TIME_PERIOD"],
                         "series": df["CG_DTYPE"].map(names), "value": df["OBS_VALUE"]})


def bis_country_names():
    """{BIS 2-letter code: name} for the credit-gap dataset (e.g. XM = Euro area)."""
    import json
    data = json.loads(_get(f"{BIS_SDMX}/structure/dataflow/BIS/WS_CREDIT_GAP/1.0",
                           {"references": "all"}))["data"]
    cl = next(c for c in data["codelists"] if "REF_AREA" in c["id"])
    return {c["id"]: c["name"] if isinstance(c["name"], str) else c["names"].get("en", c["id"])
            for c in cl["codes"]}


def iso2_to_iso3():
    """{ISO2: ISO3} from the World Bank country list (BIS uses ISO2 codes)."""
    import json
    rows = json.loads(_get("https://api.worldbank.org/v2/country",
                           {"format": "json", "per_page": 400}))[1]
    # aggregates excluded: e.g. World Bank "XM" = low income, but BIS "XM" = euro area
    return {r["iso2Code"]: r["id"] for r in rows
            if r.get("iso2Code") and r["region"]["value"].strip() != "Aggregates"}


def credit_to_gdp_with_gap(countries="all", annual=False, lamb=None, min_obs=None):
    """Ratio, our one-sided HP trend and gap per country (+ BIS's own trend/gap for reference).
    annual=True converts to calendar-year averages and uses the annual lambda."""
    raw = fetch_bis_credit_gdp(countries)
    wide = raw.pivot_table(index=["country", "period"], columns="series", values="value").reset_index()
    out = []
    for cty, g in wide.groupby("country"):
        g = g.drop(columns="country").set_index("period").sort_index()
        if annual:
            years = g.groupby(g.index.str[:4])
            g = years.mean(numeric_only=True)[years["ratio"].count() == 4]  # complete years only
            g = g.drop(columns=[c for c in ("bis_trend", "bis_gap") if c in g], errors="ignore")
        res = credit_gap(g["ratio"], lamb=lamb, freq="A" if annual else "Q", min_obs=min_obs)
        res = res.join(g.drop(columns="ratio"), how="left")
        res.insert(0, "country", cty)
        out.append(res.rename_axis("period").reset_index())
    return pd.concat(out, ignore_index=True)


# --------------------------------------------------------------------------- #
# IMF Monetary and Financial Statistics credit / WEO GDP (annual)
# --------------------------------------------------------------------------- #
def _imf_csv(flow, key):
    text = _get(f"{IMF_SDMX}/data/dataflow/{flow}/+/{key}", {"attributes": "none", "measures": "all"},
                headers={"Accept": "application/vnd.sdmx.data+csv;version=2.0.0"})
    return pd.read_csv(StringIO(text)) if text else pd.DataFrame()


def fetch_mfs_credit(countries=GULF_MFS):
    """Annual (end-year) depository corporations' credit to non-government, non-public-corporation
    sectors, domestic currency units: claims on other sectors - claims on public NFCs."""
    cty = _codes(countries)
    df = _imf_csv("IMF.STA/MFS_DC", f"{cty}.{MFS_OTHER_SECTORS}+{MFS_PUBLIC_NFC}.XDC.A")
    if df.empty:
        raise RuntimeError(f"No IMF MFS credit data for {countries}")
    w = df.pivot_table(index=["COUNTRY", "TIME_PERIOD"], columns="INDICATOR", values="OBS_VALUE")
    w[MFS_PUBLIC_NFC] = w.get(MFS_PUBLIC_NFC, 0).fillna(0) if MFS_PUBLIC_NFC in w else 0
    return (w[MFS_OTHER_SECTORS] - w[MFS_PUBLIC_NFC]).dropna().rename("credit")


def fetch_weo_gdp(countries=GULF_MFS):
    """Annual nominal GDP, domestic currency units (IMF WEO, NGDP)."""
    df = _imf_csv("IMF.RES/WEO", f"{_codes(countries)}.NGDP.A")
    if df.empty:
        raise RuntimeError(f"No WEO GDP for {countries}")
    return df.set_index(["COUNTRY", "TIME_PERIOD"])["OBS_VALUE"].rename("gdp")


def load_non_oil_gdp(path):
    """Non-oil GDP from a user CSV/XLSX: columns country (ISO3), year, non_oil_gdp (millions of
    domestic currency). Returned in currency units, indexed by (country, year), like fetch_weo_gdp."""
    df = pd.read_excel(path) if str(path).lower().endswith((".xlsx", ".xls")) else pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    df = df.dropna(subset=["country", "year", "non_oil_gdp"])
    df["country"] = df["country"].str.strip().str.upper()
    df["year"] = df["year"].astype(int)
    return df.set_index(["country", "year"])["non_oil_gdp"].astype(float).mul(1e6).rename("gdp")


def mfs_credit_to_gdp_with_gap(countries=GULF_MFS, lamb=None, min_obs=None, non_oil_gdp=None):
    """Credit-to-GDP ratio (%) = MFS credit / nominal GDP, with one-sided HP trend
    (annual, lambda 100,000 by default) and gap. GDP is WEO total GDP, or non-oil GDP from the
    file `non_oil_gdp` (see load_non_oil_gdp). Returns country, period, credit, gdp, ratio, trend, gap."""
    gdp = load_non_oil_gdp(non_oil_gdp) if non_oil_gdp else fetch_weo_gdp(countries)
    if non_oil_gdp:
        wanted = [c.strip().upper() for c in (countries if isinstance(countries, (list, tuple))
                                             else str(countries).split(","))]
        countries = [c for c in wanted if c in gdp.index.get_level_values(0)]
        if not countries:
            raise RuntimeError(f"No non-oil GDP in {non_oil_gdp} for {', '.join(wanted)}")
    both = pd.concat([fetch_mfs_credit(countries), gdp], axis=1, join="inner").dropna()
    out = []
    for cty, g in both.groupby(level=0):
        g = g.droplevel(0).sort_index()
        g.index = g.index.astype(str)
        res = credit_gap(100 * g["credit"] / g["gdp"], lamb=lamb, freq="A", min_obs=min_obs)
        res = g.join(res)
        res.insert(0, "country", cty)
        out.append(res.rename_axis("period").reset_index())
    if not out:
        raise RuntimeError(f"No overlapping MFS credit and WEO GDP data for {countries}")
    return pd.concat(out, ignore_index=True)


# --------------------------------------------------------------------------- #
# IMF Financial Soundness Indicators
# --------------------------------------------------------------------------- #
def fetch_fsi(countries="all", indicators=None, freq="Q", start=None):
    """Long DataFrame: country (ISO3), sector, indicator, indicator_name, period, value."""
    inds = "+".join(indicators or CORE_FSI)
    params = {"attributes": "none", "measures": "all"}
    if start:
        params["c[TIME_PERIOD]"] = f"ge:{start}"
    text = _get(f"{IMF_SDMX}/data/dataflow/IMF.STA/FSIC/+/{_codes(countries)}.*.{inds}.{freq}",
                params, headers={"Accept": "application/vnd.sdmx.data+csv;version=2.0.0"})
    if not text:
        raise RuntimeError(f"No FSI data for {countries}")
    df = pd.read_csv(StringIO(text))
    return pd.DataFrame({"country": df["COUNTRY"], "sector": df["SECTOR"],
                         "indicator": df["INDICATOR"],
                         "indicator_name": df["INDICATOR"].map(CORE_FSI).fillna(df["INDICATOR"]),
                         "period": df["TIME_PERIOD"], "value": df["OBS_VALUE"]})


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _save(df, out):
    if out.lower().endswith(".xlsx"):
        df.to_excel(out, index=False)
    else:
        df.to_csv(out, index=False)
    print(f"saved -> {out}")


def _plot_gap(df, out, names=None, source="Source: BIS credit-to-GDP statistics; trend: one-sided HP filter"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = names if names is not None else bis_country_names()
    for cty, g in df.groupby("country"):
        x = g["period"].astype(str)
        fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True,
                                     gridspec_kw={"height_ratios": [2, 1]})
        a1.plot(x, g["ratio"], lw=2, label="Credit-to-GDP ratio")
        a1.plot(x, g["trend"], lw=2, ls="--", label="One-sided HP trend")
        a1.set_ylabel("% of GDP"); a1.legend(frameon=False)
        a1.set_title(f"{names.get(cty, cty)}: credit-to-GDP ratio, trend and gap", loc="left",
                     weight="bold", color="#4B82AD")
        a2.bar(x, g["gap"], color=np.where(g["gap"] >= 0, "#c0392b", "#4B82AD"))
        a2.axhline(0, color="black", lw=0.8)
        a2.axhline(2, color="grey", ls=":", lw=1); a2.axhline(10, color="grey", ls=":", lw=1)
        a2.set_ylabel("Gap, pp")
        step = max(1, len(x) // 12)
        a2.set_xticks(range(0, len(x), step)); a2.set_xticklabels(x.iloc[::step], rotation=45)
        for a in (a1, a2):
            a.grid(alpha=0.3); a.spines[["top", "right"]].set_visible(False)
        fig.text(0.01, 0.01, source, fontsize=8, color="dimgray")
        fig.tight_layout(rect=(0, 0.03, 1, 1))
        path = out if df["country"].nunique() == 1 else out.replace(".png", f"_{cty}.png")
        fig.savefig(path, dpi=130); plt.close(fig)
        print(f"chart -> {path}")


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("fsi", help="IMF core Financial Soundness Indicators")
    s.add_argument("--countries", default="all", help="ISO3 codes, e.g. USA,GBR,KWT (default all)")
    s.add_argument("--freq", default="Q", choices=["Q", "A", "M"])
    s.add_argument("--start", help="e.g. 2015-Q1")
    s.add_argument("--out", default="fsi.csv")
    s = sub.add_parser("credit", help="BIS credit-to-GDP ratio + one-sided HP trend and gap")
    s.add_argument("--countries", default="all", help="BIS codes, e.g. US,GB,DE,XM (default all)")
    s.add_argument("--annual", action="store_true", help="use annual averages (lambda 100,000)")
    s.add_argument("--lamb", type=float, help="override the smoothing parameter")
    s.add_argument("--min-obs", type=int,
                   help="observations needed before a trend is reported (default 10 years)")
    s.add_argument("--out", default="credit_gap.csv")
    s.add_argument("--plot", help="also save a chart (PNG) per country")
    s = sub.add_parser("mfs", help="IMF MFS credit / WEO GDP (annual) + one-sided HP trend and gap")
    s.add_argument("--countries", default=",".join(GULF_MFS), help="ISO3 codes (default Gulf: KWT,ARE,QAT,OMN)")
    s.add_argument("--lamb", type=float, help="override the smoothing parameter (default 100,000)")
    s.add_argument("--min-obs", type=int, help="observations needed before a trend is reported (default 11)")
    s.add_argument("--non-oil-gdp", help="CSV/XLSX with country, year, non_oil_gdp (millions, domestic "
                                         "currency); used instead of WEO total GDP")
    s.add_argument("--out", default="mfs_credit_gap.csv")
    s.add_argument("--plot", help="also save a chart (PNG) per country")
    a = p.parse_args()

    if a.cmd == "mfs":
        df = mfs_credit_to_gdp_with_gap(a.countries, a.lamb, a.min_obs, a.non_oil_gdp)
        print(f"{df['country'].nunique()} countries, lambda = {a.lamb or LAMBDA['A']:,.0f}, "
              f"denominator: {'non-oil GDP (' + a.non_oil_gdp + ')' if a.non_oil_gdp else 'total GDP (WEO)'}")
        print(df[["country", "period", "ratio", "trend", "gap"]].groupby("country").tail(1).round(1)
              .to_string(index=False))
        _save(df, a.out)
        if a.plot:
            gdp_src = "non-oil GDP: user-provided data" if a.non_oil_gdp else "GDP: IMF World Economic Outlook"
            _plot_gap(df, a.plot, names=GULF_NAMES, source="Source: credit: IMF Monetary and Financial Statistics; "
                      f"{gdp_src}; trend: one-sided HP filter (lambda {a.lamb or LAMBDA['A']:,.0f})")
    elif a.cmd == "fsi":
        df = fetch_fsi(a.countries, freq=a.freq, start=a.start)
        print(f"{len(df):,} observations, {df['country'].nunique()} countries, "
              f"{df['indicator'].nunique()} indicators, {df['period'].min()}-{df['period'].max()}")
        _save(df, a.out)
    else:
        df = credit_to_gdp_with_gap(a.countries, a.annual, a.lamb, a.min_obs)
        lam = a.lamb or LAMBDA["A" if a.annual else "Q"]
        print(f"{df['country'].nunique()} countries, lambda = {lam:,.0f}")
        print(df.groupby("country").tail(1).round(1).to_string(index=False))
        _save(df, a.out)
        if a.plot:
            _plot_gap(df, a.plot)


if __name__ == "__main__":
    main()
