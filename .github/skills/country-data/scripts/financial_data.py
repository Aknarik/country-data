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
  Claims on other sectors (DCORP_A_ACO_S1_Z), in domestic currency. Claims on public
  non-financial corporations are kept in: BIS credit to the private non-financial sector also
  includes publicly owned corporations, and Kuwait reports them separately only from 2020
  (zero before), so subtracting them would break the series. The narrower "claims on
  private sector" series (DCORP_A_ACO_PS) has a reclassification break for Kuwait
  (about 98% of GDP in 2015 but 4% in 2024, the rest moved to other financial
  corporations), which would create a false gap; the measure used here is continuous.

One-sided HP filter
  For each period t, a standard (two-sided) HP filter is run on the data available
  up to t only, and the trend value at t is kept. This uses no future information,
  as in the Basel III countercyclical capital buffer guide.
  Default smoothing (lambda): quarterly 400,000 (Basel); annual 400,000 / 4^4 = 1,562.5
  (Ravn and Uhlig, 2002, frequency adjustment) (override with --lamb).
  gap = ratio - trend (percentage points of GDP).
  As BIS does, a trend is reported only once 10 years of data are available (--min-obs).
  With these defaults the quarterly trend reproduces BIS's published credit-to-GDP trend.

Usage
  python financial_data.py fsi    --countries "USA,GBR,KWT" --out fsi.csv
  python financial_data.py credit --countries "US,GB,DE"    --out credit_gap.csv
  python financial_data.py credit --countries all --out credit_gap.xlsx
  python financial_data.py credit --countries US --annual           # annual averages, lambda 1,562.5
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
LAMBDA = {"Q": 400_000, "A": 400_000 / 4 ** 4}  # annual = 1,562.5 (Ravn-Uhlig frequency adjustment)
PERIODS_PER_YEAR = {"Q": 4, "A": 1}
MIN_YEARS = 0  # trend shown from the first observation (BIS shows it only after 10 years; values after
#               that are identical, since the one-sided filter always uses all data from the start)
START_UP_YEARS = 10  # first years of the trend: start-up period, flagged as less reliable
MIN_SPAN_YEARS = 20  # no trend or gap for series shorter than this (project rule, conservative)
GULF_MFS = ["KWT", "ARE", "QAT", "OMN"]  # Saudi Arabia: use BIS (longer); Bahrain: no MFS data
GULF_NAMES = {"KWT": "Kuwait", "ARE": "United Arab Emirates", "QAT": "Qatar", "OMN": "Oman",
              "SAU": "Saudi Arabia", "BHR": "Bahrain"}
MFS_OTHER_SECTORS, MFS_PUBLIC_NFC = "DCORP_A_ACO_S1_Z", "DCORP_A_ACO_S11001"

# FSIs used (IMF FSIC dataflow): code -> (name, group, more vulnerable when higher?).
# Grouped and oriented from a financial-sector vulnerability perspective.
FSI_SERIES = {
    "FSI688_CFSI_PT": ("Regulatory capital to risk-weighted assets", "Capital adequacy", False),
    "FSI626_CFSI_PT": ("Tier 1 capital to risk-weighted assets", "Capital adequacy", False),
    "FSI15_CFSI_PT": ("Common equity Tier 1 capital to risk-weighted assets", "Capital adequacy", False),
    "T1KTA_CFSI_PT": ("Tier 1 capital to assets", "Capital adequacy", False),
    "AQ12_CFSI_PT": ("Nonperforming loans to total gross loans", "Asset quality", True),
    "FSI17_CFSI_PT": ("Nonperforming loans net of provisions to capital", "Asset quality", True),
    "AQ14_CFSI_PT": ("Provisions to nonperforming loans", "Asset quality", False),
    "AQ1_CFSI_PT": ("Loan concentration by economic activity", "Concentration", True),
    "FSI214_AFSI_PT": ("Large exposures to capital", "Concentration", True),
    "FSI524_CFSI_PT": ("Residential real estate loans to total gross loans", "Concentration", True),
    "FSI520_AFSI_PT": ("Commercial real estate loans to total gross loans", "Concentration", True),
    "ROA_CFSI_PT": ("Return on assets", "Earnings", False),
    "ROE_CFSI_PT": ("Return on equity", "Earnings", False),
    "FSI765_CFSI_PT": ("Liquid assets to short-term liabilities", "Funding and liquidity", False),
    "FSI283_LIQATTA_PT": ("Liquid assets to total assets", "Funding and liquidity", False),
    "FSI288_CFSI_PT": ("Liquidity coverage ratio", "Funding and liquidity", False),
    "FSI289_CFSI_PT": ("Net stable funding ratio", "Funding and liquidity", False),
    "FSI55_AFSI_PT": ("Customer deposits to total (noninterbank) loans", "Funding and liquidity", True),
    "FSI555_CFSI_PT": ("Net open position in foreign exchange to capital", "FX exposure", True),
    "FSI131_AFSI_PT": ("Foreign currency denominated loans to total loans", "FX exposure", True),
    "FSI680_AFSI_PT": ("Foreign currency denominated liabilities to total liabilities", "FX exposure", True),
    "FSI179_AFSI_PT": ("Household debt to GDP", "Household sector", True),
}
FSI_NAMES = {k: v[0] for k, v in FSI_SERIES.items()}
CORE_FSI = {k: v for k, v in FSI_NAMES.items() if "_CFSI_" in k}  # core FSIs only


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
    lamb defaults to 400,000 for quarterly and 1,562.5 (= 400,000 / 4^4) for annual data.
    Missing values are dropped first. The filter always starts at the first observation.
    min_obs (default: from the first period) is the number of observations before a trend is
    reported. Series shorter than MIN_SPAN_YEARS get no trend (all NaN)."""
    s = pd.Series(series).dropna().astype(float)
    freq = freq or _infer_freq(s.index)
    if lamb is None:
        lamb = LAMBDA[freq]
    if min_obs is None:
        min_obs = MIN_YEARS * PERIODS_PER_YEAR[freq] + 1
    y = s.to_numpy()
    trend = np.full(len(y), np.nan)
    if len(y) < MIN_SPAN_YEARS * PERIODS_PER_YEAR[freq]:
        return pd.Series(trend, index=s.index, name="trend")
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
    """Annual (end-year) depository corporations' claims on other sectors (non-government sectors,
    including public non-financial corporations as in the BIS definition), domestic currency units.
    Public corporations are not subtracted: Kuwait reports them only from 2020 (zero before), which
    would put a break in the series."""
    cty = _codes(countries)
    df = _imf_csv("IMF.STA/MFS_DC", f"{cty}.{MFS_OTHER_SECTORS}.XDC.A")
    if df.empty:
        raise RuntimeError(f"No IMF MFS credit data for {countries}")
    w = df.pivot_table(index=["COUNTRY", "TIME_PERIOD"], columns="INDICATOR", values="OBS_VALUE")
    return w[MFS_OTHER_SECTORS].dropna().rename("credit")


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
    (annual, lambda 1,562.5 by default) and gap. GDP is WEO total GDP, or non-oil GDP from the
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
# Banking sector balance sheet (IMF MFS, other depository corporations)
# --------------------------------------------------------------------------- #
ODC = {  # IMF.STA:MFS_ODC indicator -> short key
    "ODCORP_A_T_ASEC_ODC2SR": "assets", "ODCORP_L_F51KOE_ODCS": "equity",
    "ODCORP_A_ACO_S1311MIXED_ODCS": "claims_gov", "ODCORP_A_ACO_S1_Z_ODCS": "claims_other_sectors",
    "ODCORP_A_ACO_PS_ODCS": "claims_private", "ODCORP_A_ACO_NRES_ODCS": "claims_nonres",
    "ODCORP_A_ACO_S121_ODCS": "claims_cb", "ODCORP_L_F22_IBM_ODCS": "dep_transferable",
    "ODCORP_L_F29_IBM_ODCS": "dep_other", "ODCORP_L_F2M_XBM_ODCS": "dep_excluded",
    "ODCORP_L_LT_NRES_ODCS": "liab_nonres", "ODCORP_A_ACO_S11001_ODCS": "claims_pubnfc",
}
# output indicator -> (name, unit, formula on the keys above; gdp = nominal GDP)
BANK_INDICATORS = {
    "BANK_ASSETS": ("Banking sector total assets", "Billions of domestic currency", lambda d: d.assets / 1e9),
    "BANK_ASSETS_GDP": ("Banking sector total assets", "Percent of GDP", lambda d: 100 * d.assets / d.gdp),
    "BANK_EQUITY_TA": ("Equity (shares and other equity) to total assets", "Percent of total assets",
                       lambda d: 100 * d.equity / d.assets),
    "BANK_GOV_TA": ("Sovereign-bank nexus: claims on central government (% of bank assets)", "Percent of total assets",
                    lambda d: 100 * d.claims_gov / d.assets),
    "BANK_GOV_GDP": ("Bank claims on central government (% of GDP)", "Percent of GDP", lambda d: 100 * d.claims_gov / d.gdp),
    "BANK_CREDIT_GDP": ("Credit to the economy: bank claims on other sectors", "Percent of GDP",
                        lambda d: 100 * d.claims_other_sectors / d.gdp),
    "BANK_CREDIT_TA": ("Claims on other sectors (loans and securities) to total assets", "Percent of total assets",
                       lambda d: 100 * d.claims_other_sectors / d.assets),
    "BANK_PRIVATE_GDP": ("Bank claims on the private sector", "Percent of GDP",
                         lambda d: 100 * d.claims_private / d.gdp),
    "BANK_NRES_TA": ("Claims on nonresidents (foreign assets) to total assets", "Percent of total assets",
                     lambda d: 100 * d.claims_nonres / d.assets),
    "BANK_CB_TA": ("Claims on the central bank (reserves) to total assets", "Percent of total assets",
                   lambda d: 100 * d.claims_cb / d.assets),
    "BANK_DEPOSITS_TA": ("Deposits to total assets", "Percent of total assets",
                         lambda d: 100 * (d.dep_transferable.fillna(0) + d.dep_other.fillna(0)
                                          + d.dep_excluded.fillna(0)).replace(0, np.nan) / d.assets),
    "BANK_FOREIGN_LIAB_TA": ("Liabilities to nonresidents to total assets", "Percent of total assets",
                             lambda d: 100 * d.liab_nonres / d.assets),
    # Asset structure (shares add up to 100): for stacked bar / pie charts
    "BANK_STR_PRIV": ("Asset structure: Private sector and other financial corporations", "Percent of total assets",
                      lambda d: 100 * (d.claims_other_sectors - d.claims_pubnfc.fillna(0)) / d.assets),
    "BANK_STR_PUBNFC": ("Asset structure: Public non-financial corporations", "Percent of total assets",
                        lambda d: 100 * d.claims_pubnfc / d.assets),
    "BANK_STR_GOV": ("Asset structure: Central government", "Percent of total assets",
                     lambda d: 100 * d.claims_gov / d.assets),
    "BANK_STR_NRES": ("Asset structure: Nonresidents (foreign assets)", "Percent of total assets",
                      lambda d: 100 * d.claims_nonres / d.assets),
    "BANK_STR_CB": ("Asset structure: Central bank", "Percent of total assets",
                    lambda d: 100 * d.claims_cb / d.assets),
    "BANK_STR_OTHER": ("Asset structure: Other assets", "Percent of total assets",
                       lambda d: 100 - 100 * (d.claims_other_sectors + d.claims_gov.fillna(0) + d.claims_nonres.fillna(0)
                                              + d.claims_cb.fillna(0)) / d.assets),
}


def bank_balance_sheet(countries="all", start=2000):
    """Banking sector (other depository corporations) balance-sheet ratios, annual:
    DataFrame with country, year and one column per BANK_INDICATORS key."""
    raw = _imf_csv("IMF.STA/MFS_ODC", f"{_codes(countries)}.{'+'.join(ODC)}.XDC.A")
    if raw.empty:
        raise RuntimeError(f"No IMF MFS banking data for {countries}")
    raw = raw[raw["TIME_PERIOD"] >= start]
    w = raw.pivot_table(index=["COUNTRY", "TIME_PERIOD"], columns="INDICATOR", values="OBS_VALUE")
    w = w.rename(columns=ODC).reindex(columns=list(dict.fromkeys(ODC.values())))
    w = w.join(fetch_weo_gdp(countries), how="left")
    # Where total assets are not reported, estimate them as the sum of financial claims
    # (nonresidents, central bank, central government, other sectors): excludes nonfinancial assets.
    est = w[["claims_nonres", "claims_cb", "claims_gov", "claims_other_sectors"]].sum(axis=1, min_count=3)
    w["assets_estimated"] = w["assets"].isna() & est.notna()
    w["assets"] = w["assets"].fillna(est)
    out = pd.DataFrame({k: f(w) for k, (_, _, f) in BANK_INDICATORS.items()}, index=w.index)
    out["assets_estimated"] = w["assets_estimated"]
    return out.replace([np.inf, -np.inf], np.nan).rename_axis(["country", "year"]).reset_index()


# --------------------------------------------------------------------------- #
# Loan portfolio by borrowing sector (IMF FSI balance sheet, deposit takers)
# --------------------------------------------------------------------------- #
LOAN_SECTORS = {"NINTBKF4_T_S11_A_XDC": ("LOANS_NFC_SH", "Non-financial corporations"),
                "NINTBKF4_T_ODS_A_XDC": ("LOANS_HH_SH", "Households and other domestic sectors"),
                "NINTBKF4_T_S12R_A_XDC": ("LOANS_OFC_SH", "Other financial corporations"),
                "NINTBKF4_S13_A_XDC": ("LOANS_GOV_SH", "General government"),
                "NINTBKF4_T_S13_A_XDC": ("LOANS_GOV_SH", "General government"),
                "NINTBKF4_T_NRES_A_XDC": ("LOANS_NRES_SH", "Nonresidents")}
LOAN_RRE = ("RREF4_XDC", "LOANS_RRE_SH", "Residential real estate loans (memo: part of the sectors above)")


def loan_portfolio(countries="all", freq="Q"):
    """Deposit takers' customer (non-interbank) loans by borrowing sector, as % of total customer
    loans, from the IMF FSI balance-sheet data (IMF.STA:FSIBSIS). Long DataFrame:
    country, period, code, name, value."""
    codes = list(LOAN_SECTORS) + [LOAN_RRE[0]]
    raw = _imf_csv("IMF.STA/FSIBSIS", f"{_codes(countries)}.S12CFSI.{'+'.join(codes)}.{freq}")
    if raw.empty:
        raise RuntimeError(f"No IMF FSI loan data for {countries}")
    raw["key"] = raw["INDICATOR"].map(lambda c: LOAN_SECTORS[c][0] if c in LOAN_SECTORS else LOAN_RRE[1])
    w = raw.pivot_table(index=["COUNTRY", "TIME_PERIOD"], columns="key", values="OBS_VALUE", aggfunc="first")
    sectors = [k for k in dict.fromkeys(v[0] for v in LOAN_SECTORS.values()) if k in w]
    total = w[sectors].sum(axis=1, min_count=2)
    names = {**{v[0]: v[1] for v in LOAN_SECTORS.values()}, LOAN_RRE[1]: LOAN_RRE[2]}
    out = []
    for k in sectors + ([LOAN_RRE[1]] if LOAN_RRE[1] in w else []):
        share = (100 * w[k] / total).dropna()
        out.append(pd.DataFrame({"country": share.index.get_level_values(0),
                                 "period": share.index.get_level_values(1),
                                 "code": k, "name": names[k], "value": share.values}))
    return pd.concat(out, ignore_index=True)


# --------------------------------------------------------------------------- #
# BIS total credit by borrowing sector (% of GDP)
# --------------------------------------------------------------------------- #
BIS_SECTORS = {("H", "A"): ("CREDIT_HH_GDP", "Credit to households (all lenders)"),
               ("N", "A"): ("CREDIT_NFC_GDP", "Credit to non-financial corporations (all lenders)"),
               ("P", "A"): ("CREDIT_PNFS_GDP", "Credit to the private non-financial sector (all lenders)"),
               ("P", "B"): ("CREDIT_PNFS_BANK_GDP", "Bank credit to the private non-financial sector"),
               ("G", "A"): ("CREDIT_GOV_GDP", "Credit to general government (all lenders)")}


def bis_credit_by_sector(countries="all", start=None):
    """BIS total credit (WS_TC), % of GDP, quarterly, adjusted for breaks.
    Long DataFrame: country, code, name, period, value."""
    params = {"format": "csv"}
    if start:
        params["startPeriod"] = str(start)
    text = _get(f"{BIS_SDMX}/data/dataflow/BIS/WS_TC/2.0/Q.{_codes(countries)}.H+N+P+G.A+B.M.770.A", params)
    if not text:
        raise RuntimeError(f"No BIS total credit data for {countries}")
    d = pd.read_csv(StringIO(text))
    key = list(zip(d["TC_BORROWERS"], d["TC_LENDERS"]))
    d = d[[k in BIS_SECTORS for k in key]]
    key = list(zip(d["TC_BORROWERS"], d["TC_LENDERS"]))
    return pd.DataFrame({"country": d["BORROWERS_CTY"].values,
                         "code": [BIS_SECTORS[k][0] for k in key], "name": [BIS_SECTORS[k][1] for k in key],
                         "period": d["TIME_PERIOD"].values, "value": d["OBS_VALUE"].values})


# --------------------------------------------------------------------------- #
# IMF Financial Soundness Indicators
# --------------------------------------------------------------------------- #
def fetch_fsi(countries="all", indicators=None, freq="Q", start=None):
    """Long DataFrame: country (ISO3), sector, indicator, indicator_name, period, value."""
    inds = "+".join(indicators or FSI_SERIES)
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
                         "indicator_name": df["INDICATOR"].map(FSI_NAMES).fillna(df["INDICATOR"]),
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
    s = sub.add_parser("fsi", help="IMF Financial Soundness Indicators (core + selected additional)")
    s.add_argument("--countries", default="all", help="ISO3 codes, e.g. USA,GBR,KWT (default all)")
    s.add_argument("--freq", default="Q", choices=["Q", "A", "M"])
    s.add_argument("--start", help="e.g. 2015-Q1")
    s.add_argument("--out", default="fsi.csv")
    s = sub.add_parser("credit", help="BIS credit-to-GDP ratio + one-sided HP trend and gap")
    s.add_argument("--countries", default="all", help="BIS codes, e.g. US,GB,DE,XM (default all)")
    s.add_argument("--annual", action="store_true", help="use annual averages (lambda 1,562.5)")
    s.add_argument("--lamb", type=float, help="override the smoothing parameter")
    s.add_argument("--min-obs", type=int,
                   help="observations needed before a trend is reported (default 10 years)")
    s.add_argument("--out", default="credit_gap.csv")
    s.add_argument("--plot", help="also save a chart (PNG) per country")
    s = sub.add_parser("mfs", help="IMF MFS credit / WEO GDP (annual) + one-sided HP trend and gap")
    s.add_argument("--countries", default=",".join(GULF_MFS), help="ISO3 codes (default Gulf: KWT,ARE,QAT,OMN)")
    s.add_argument("--lamb", type=float, help="override the smoothing parameter (default 400,000 quarterly, 1,562.5 annual)")
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
