#!/usr/bin/env python3
"""
Process locally downloaded source files for the Country Data agent.

1. iMaPP (IMF Integrated Macroprudential Policy database, public) -> IMF_iMaPP_macroprudential.xlsx
     Actions  : net macroprudential actions per economy, tool and year (tightening +1, loosening -1)
     Summary  : per economy and tool: tightenings, loosenings, first/last action, latest description
2. HEAT 2.0 bank-level data (S&P Capital IQ Pro via IMF HEAT tool; IMF-INTERNAL, LICENSED)
     -> local_data/HEAT_bank_distribution.xlsx: country-level aggregates only (no bank names):
        median, 25th/75th percentile and asset-weighted mean across banks, number of banks,
        total assets. Written to local_data/, which is git-ignored: never publish it.

    python m365-agent/build_local_sources.py [--imapp FILE] [--heat FILE] [--heat-annual FILE]
Defaults: the newest iMaPP_database*.xlsx, HEAT*Quarterly*.xlsm and HEAT*Annual*.xlsm in the
repository root. Quarterly and annual HEAT aggregates go into one sheet (annual codes end in _A).
"""

import argparse
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LOCAL = ROOT / "local_data"
sys.path.insert(0, str(HERE))
import build_data_file as b  # noqa: E402  (write_book, country names)

IMAPP_OUT = HERE / "IMF_iMaPP_macroprudential.xlsx"
HEAT_OUT = LOCAL / "HEAT_bank_distribution.xlsx"
IMAPP_CITATION = ("International Monetary Fund, Integrated Macroprudential Policy (iMaPP) Database; "
                  "Alam, Alter, Eiseman, Gelos, Kang, Narita, Nier and Wang (2019), IMF WP/19/66")
IMAPP_LINK = "https://www.elibrary-areaer.imf.org/Macroprudential/Pages/Home.aspx"
TOOLS = {
    "CCB": "Countercyclical capital buffer", "Conservation": "Capital conservation buffer",
    "Capital": "Capital requirements (all)", "Capital_Gen": "Capital requirements, general",
    "Capital_HH": "Capital requirements, household loans", "Capital_Corp": "Capital requirements, corporate loans",
    "Capital_FX": "Capital requirements, FX loans", "LVR": "Leverage ratio limit", "LLP": "Loan loss provisioning",
    "LCG": "Limits on credit growth (all)", "LCG_Gen": "Limits on credit growth, general",
    "LCG_HH": "Limits on credit growth, households", "LCG_Corp": "Limits on credit growth, corporates",
    "LoanR": "Loan restrictions (all)", "LoanR_HH": "Loan restrictions, households",
    "LoanR_Corp": "Loan restrictions, corporates", "LFC": "Limits on foreign currency lending",
    "LTV": "Loan-to-value limits", "DSTI": "Debt-service-to-income limits", "Tax": "Taxes on financial activities",
    "Liquidity": "Liquidity requirements", "LTD": "Loan-to-deposit ratio limits",
    "LFX": "Limits on FX positions", "RR": "Reserve requirements", "RR_FCD": "Reserve requirements on FX deposits",
    "SIFI": "Measures for systemically important institutions", "OT": "Other measures",
}
HEAT_SHEETS = {  # O-sheet -> (code, name)
    "O-CapitalAdequacy": ("T1", "Tier 1 capital ratio"),
    "O-AssetQuality": ("NPLNET", "NPLs net of provisions to total loans"),
    "O-Earnings": ("ROAA", "Return on average assets"),
    "O-Liquidity": ("LIQ", "Liquid assets to total liabilities"),
    "O-Leverage": ("TCE", "Tangible common equity to tangible assets"),
}
HEAT_CITATION = ("IMF staff calculations (HEAT 2.0) based on S&P Capital IQ Pro bank-level data; "
                 "IMF-internal use only")


def newest(pattern):
    files = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


NUM = r"(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)"


def magnitude(text):
    """Size of a change from an iMaPP description: (previous, new, change in pp, note).
    Recognises 'from X% to Y%', 'to Y% from X%' and 'by Z pp'; otherwise returns the first
    percentage mentioned as the stated level."""
    t = re.sub(r"\s+", " ", str(text or ""))
    m = re.search(r"from " + NUM + r" to " + NUM, t, re.I)
    if m:
        old, new = float(m.group(1)), float(m.group(2))
        return old, new, round(new - old, 2), ""
    m = re.search(r"to " + NUM + r"[^.;]{0,40}?from " + NUM, t, re.I)
    if m:
        new, old = float(m.group(1)), float(m.group(2))
        return old, new, round(new - old, 2), ""
    m = re.search(r"\bby (\d+(?:\.\d+)?)\s*(?:percentage points?|pp|%)", t, re.I)
    if m:
        sign = -1 if re.search(r"reduc|lower|decreas|cut|releas|relax", t, re.I) else 1
        return None, None, sign * float(m.group(1)), ""
    m = re.search(NUM, t)
    return None, None, None, (f"{m.group(1)}% stated" if m else "")


def latest_ltv(xl):
    """Latest average LTV limit per country (iMaPP LTV_average sheet: months x countries)."""
    try:
        sh = xl.parse("LTV_average", header=None)
    except Exception:
        return {}
    h = sh.index[sh.iloc[:, 0].astype(str).str.strip().eq("Country")]
    if not len(h):
        return {}
    body = sh.iloc[h[0] + 1:]
    body = body[body.iloc[:, 0].astype(str).str.fullmatch(r"\d{4}M\d{1,2}")]
    out = {}
    for j, c in enumerate(sh.iloc[h[0], 1:].tolist(), start=1):
        col = pd.to_numeric(body.iloc[:, j], errors="coerce").dropna()
        if len(col):
            out[str(c).strip()] = (float(col.iloc[-1]), str(body.loc[col.index[-1]].iloc[0]))
    return out


# --------------------------------------------------------------------------- iMaPP
def build_imapp(path):
    t0 = time.time()
    xl = pd.ExcelFile(path)
    mapp = xl.parse("MaPP")
    tight = xl.parse("MaPP_T").rename(columns=lambda c: re.sub(r"_T$", "", str(c)))
    loose = xl.parse("MaPP_L").rename(columns=lambda c: re.sub(r"_L$", "", str(c)))
    tools = [t for t in TOOLS if t in mapp.columns]
    key = ["Country", "iso3", "Year", "Month"]
    std = b.cd.country_names()
    names = {i: std.get(i) or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", c) for i, c in zip(mapp["iso3"], mapp["Country"])}

    # Actions: net per economy, tool, year
    annual = mapp.groupby(["iso3", "Year"])[tools].sum()
    years = sorted(annual.index.get_level_values(1).unique())
    rows = []
    for iso, g in annual.groupby(level=0):
        g = g.droplevel(0)
        for t in tools:
            rows.append({"Economy code": iso, "Economy": names[iso], "Type": "Country", "Indicator code": t,
                         "Indicator": TOOLS[t], "Unit": "Net actions (tightening +1, loosening -1)",
                         "Citation": IMAPP_CITATION, "Source link": IMAPP_LINK,
                         **{str(int(y)): int(g.at[y, t]) for y in years}})
    actions = pd.DataFrame(rows)

    # Latest text description per economy and tool (instrument sheets: months x countries)
    texts = {}
    for t in tools:
        if t not in xl.sheet_names:
            continue
        sh = xl.parse(t, header=None)
        hdr = sh.index[sh.iloc[:, 0].astype(str).str.strip().eq("Country")]
        if not len(hdr):
            continue
        h = hdr[0]
        countries = sh.iloc[h, 1:].tolist()
        body = sh.iloc[h + 1:]
        body = body[body.iloc[:, 0].astype(str).str.fullmatch(r"\d{4}M\d{1,2}")]  # monthly rows only
        for j, c in enumerate(countries, start=1):
            col = body.iloc[:, j].dropna().astype(str).str.strip()
            col = col[col.ne("") & ~col.str.fullmatch(r"-?\d+(\.0)?")]
            if len(col):  # all texts by month, e.g. {'2023M1': '...'}
                texts[(str(c).strip(), t)] = {str(body.loc[i].iloc[0]).strip(): v for i, v in col.items()}

    ltv = latest_ltv(xl)
    s_rows = []
    orig = dict(zip(mapp["iso3"], mapp["Country"]))
    for iso, g in mapp.groupby("iso3"):
        tg, lg = tight[tight["iso3"] == iso], loose[loose["iso3"] == iso]
        cname = names[iso]
        for t in tools:
            nt, nl = int(tg[t].sum()), int(lg[t].sum())
            if nt + nl == 0:
                continue
            ev = g[(tg[t].values != 0) | (lg[t].values != 0)]
            last = ev.iloc[-1]
            lt, ll = int(tg.loc[last.name, t]), int(lg.loc[last.name, t])
            bymonth = texts.get((orig[iso], t), {})
            text = bymonth.get(f"{int(last['Year'])}M{int(last['Month'])}") or (list(bymonth.values())[-1] if bymonth else "")
            text = re.sub(r"[　-鿿]", "", text.replace("_x000D_", " "))
            mag = magnitude(text)
            if t == "LTV" and orig[iso] in ltv and mag[1] is None:
                v, mth = ltv[orig[iso]]
                mag = (mag[0], mag[1], mag[2], f"average LTV limit {v:.0f}% ({mth})")
            s_rows.append({"Economy code": iso, "Economy": cname, "Tool code": t, "Tool": TOOLS[t],
                           "Tightenings": nt, "Loosenings": nl,
                           "Tightenings since 2020": int(tg[tg["Year"] >= 2020][t].sum()),
                           "Loosenings since 2020": int(lg[lg["Year"] >= 2020][t].sum()),
                           "First action": f"{int(ev.iloc[0]['Year'])}-{int(ev.iloc[0]['Month']):02d}",
                           "Latest action": f"{int(last['Year'])}-{int(last['Month']):02d}",
                           "Latest direction": "tightening" if lt and not ll else "loosening" if ll and not lt else "both",
                           "Previous level (%)": mag[0], "New level (%)": mag[1], "Change (pp)": mag[2],
                           "Magnitude note": mag[3],
                           "Latest description": re.sub(r"\s+", " ", text)[:600],
                           "Citation": IMAPP_CITATION})
    summary = pd.DataFrame(s_rows)
    # Official tool definitions from the iMaPP table of contents (C1.CCB ... C17.Other, A1.LTV_average)
    toc = xl.parse("TOC", header=None)
    defs = []
    for _, r in toc.iterrows():
        cells = [str(v).strip() for v in r if pd.notna(v) and str(v).strip()]
        m = re.fullmatch(r"([AC]\d+)\.(\w+)", cells[0]) if cells else None
        if m and len(cells) > 1:
            code = {"Other": "OT"}.get(m.group(2), m.group(2))
            defs.append({"Tool code": code, "Tool": TOOLS.get(code, "Average LTV limit" if code == "LTV_average" else code),
                         "Definition (IMF iMaPP)": re.sub(r"\s+", " ", " ".join(cells[1:])),
                         "Citation": IMAPP_CITATION})
    definitions = pd.DataFrame(defs)
    last_date = f"{int(mapp['Year'].max())}"
    b.write_book(IMAPP_OUT, {
        "README": [
            "IMF Integrated Macroprudential Policy (iMaPP) Database - summary for the Country Data agent.",
            f"Built {time.strftime('%Y-%m-%d')} from {path.name} (data to {last_date}). {len(names)} economies, "
            f"{len(tools)} tool types, monthly since 1990.",
            "Sheet 'Summary': per economy and tool - number of tightenings and loosenings (all years and since "
            "2020), first and latest action, direction and the IMF's text description of the latest action.",
            "Sheet 'Actions': net actions per economy, tool and year (tightenings minus loosenings).",
            "Sheet 'Definitions': the IMF's official definition of each tool (e.g. LTV, DSTI, CCB).",
            "Tools: " + "; ".join(f"{k} = {v}" for k, v in TOOLS.items()) + ".",
            "iMaPP records policy actions (changes), not whether a tool is currently in force; a tool with "
            "tightenings and no later full loosening is likely still in use - check the description.",
            "Cite: " + IMAPP_CITATION + ". " + IMAPP_LINK],
        "Definitions": definitions, "Summary": summary, "Actions": actions})
    print(f"iMaPP: {len(names)} economies, {len(summary)} economy-tool records, {time.time() - t0:.0f}s",
          file=sys.stderr)


# --------------------------------------------------------------------------- HEAT
PERIOD_Q, PERIOD_A = re.compile(r"(\d{4})Q([1-4])"), re.compile(r"(\d{4})Y?")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def _period(h, annual):
    """'2010Q1' -> '2010-Q1' (quarterly); '2010' or '2010Y' -> '2010' (annual); else None."""
    h = str(h).strip() if h is not None else ""
    m = (PERIOD_A if annual else PERIOD_Q).fullmatch(h)
    return (m.group(1) if annual else f"{m.group(1)}-Q{m.group(2)}") if m else None


def read_o_sheet(ws, annual):
    """Bank rows of an O- sheet: key, country, then one value per period."""
    header, out = None, []
    for r in ws.iter_rows(values_only=True):
        if header is None:
            if r and len(r) > 2 and str(r[1]).strip() == "SNL Institution Key":
                header = [str(x).strip() if x is not None else "" for x in r]
                cols = [(i, _period(h, annual)) for i, h in enumerate(header) if _period(h, annual)]
                ccol = header.index("Country")
            continue
        if r[1] is None or str(r[1]).strip() == "":
            continue
        out.append([str(r[1]).strip(), str(r[ccol]).strip()] + [_num(r[i]) for i, _ in cols])
    return pd.DataFrame(out, columns=["key", "country"] + [p for _, p in cols]).drop_duplicates("key")


def read_total_assets(ws, annual):
    """TotalAssets sheet: bank key -> total assets per period (row 5 holds '2010Q1' or '2010Y')."""
    prow = list(ws.iter_rows(min_row=5, max_row=5, values_only=True))[0]
    cols = [(i, _period(h, annual)) for i, h in enumerate(prow) if _period(h, annual)]
    out = []
    for r in ws.iter_rows(min_row=7, values_only=True):
        if r[1] is None or str(r[1]).strip() == "":
            continue
        out.append([str(r[1]).strip()] + [_num(r[i]) for i, _ in cols])
    return pd.DataFrame(out, columns=["key"] + [p for _, p in cols]).drop_duplicates("key").set_index("key")


def heat_rows(path, annual, iso):
    """Country-level distribution rows (no bank names) from one HEAT workbook."""
    wb = load_workbook(path, read_only=True, data_only=True)
    ta = read_total_assets(wb["TotalAssets"], annual)
    sfx, label = ("_A", " (annual)") if annual else ("", "")
    rows = []
    for sheet, (code, name) in HEAT_SHEETS.items():
        df = read_o_sheet(wb[sheet], annual)
        per = [c for c in df.columns if c not in ("key", "country")]
        for cty, g in df.groupby("country"):
            if cty not in iso:
                try:
                    iso[cty] = {"Palestine": "WBG", "Dem. Rep. Congo": "COD", "Guernsey": "GGY", "Isle of Man": "IMN",
                              "Jersey": "JEY", "Vatican City": "VAT"}.get(cty) or b.cd.resolve_countries(cty, verbose=False)[0]
                except Exception:
                    iso[cty] = cty
            v = g.set_index("key")[per]
            w = ta.reindex(v.index).reindex(columns=per)
            stats = {
                "MED": ("median bank", v.median()),
                "P25": ("25th percentile bank", v.quantile(0.25)),
                "P75": ("75th percentile bank", v.quantile(0.75)),
                "AW": ("asset-weighted mean", (v * w).sum(min_count=1) / w.where(v.notna()).sum(min_count=1)),
                "N": ("number of banks reporting", v.notna().sum().replace(0, np.nan)),
            }
            for sc, (sname, ser) in stats.items():
                ser = ser.round(2).dropna()
                if ser.empty:
                    continue
                rows.append({"Economy code": iso[cty], "Economy": b.cd.country_names().get(iso[cty], cty),
                             "Type": "Country", "Indicator code": f"HEAT_{code}_{sc}{sfx}",
                             "Indicator": f"{name} - {sname}{label}",
                             "Unit": "Number of banks" if sc == "N" else "Percent",
                             "Citation": HEAT_CITATION, "Source link": "", **ser.to_dict()})
    return rows


def build_heat(quarterly, annual_file):
    t0 = time.time()
    iso, rows, used = {}, [], []
    for path, annual in ((quarterly, False), (annual_file, True)):
        if path:
            n = len(rows)
            rows += heat_rows(path, annual, iso)
            used.append(f"{path.name} ({'annual' if annual else 'quarterly'}, {len(rows) - n} rows)")
    out = pd.DataFrame(rows)
    per = sorted((c for c in out.columns if re.fullmatch(r"\d{4}(-Q\d)?", str(c))),
                 key=lambda c: (len(c), c))  # annual years first, then quarters
    out = out[[c for c in out.columns if c not in per] + per].sort_values(["Economy", "Indicator code"])
    LOCAL.mkdir(exist_ok=True)
    b.write_book(HEAT_OUT, {
        "README": [
            "HEAT 2.0 bank-level soundness indicators aggregated to country level - IMF-INTERNAL USE ONLY.",
            f"Built {time.strftime('%Y-%m-%d')} from: {'; '.join(used)}. Source: S&P Capital IQ Pro via the IMF "
            "HEAT tool (licensed). No individual bank names or values are included.",
            "For each country and period: median bank, 25th and 75th percentile, asset-weighted mean "
            "(weights = total assets) and number of banks reporting.",
            "Quarterly rows: codes like HEAT_T1_MED, periods '2010-Q1'. Annual rows (more banks, from 2000): "
            "codes ending _A (e.g. HEAT_T1_MED_A), periods '2010'.",
            "Indicators: Tier 1 capital ratio (T1); NPLs net of provisions to total loans (NPLNET); return on "
            "average assets (ROAA); liquid assets to total liabilities (LIQ); tangible common equity to "
            "tangible assets (TCE).",
            "Do not publish outside the IMF; follow the HEAT ReadMe and the S&P licence."],
        "HEAT_country": out})
    print(f"HEAT: {out['Economy code'].nunique()} economies, {len(out)} rows, {time.time() - t0:.0f}s",
          file=sys.stderr)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--imapp", default=None)
    a.add_argument("--heat", default=None, help="quarterly HEAT workbook")
    a.add_argument("--heat-annual", dest="heat_annual", default=None, help="annual HEAT workbook")
    a.add_argument("--only", choices=["imapp", "heat"])
    args = a.parse_args()
    if args.only != "heat":
        p = Path(args.imapp) if args.imapp else newest("iMaPP_database*.xlsx")
        build_imapp(p) if p else print("iMaPP file not found", file=sys.stderr)
    if args.only != "imapp":
        q = Path(args.heat) if args.heat else newest("HEAT*Quarterly*.xlsm")
        an = Path(args.heat_annual) if args.heat_annual else newest("HEAT*Annual*.xlsm")
        build_heat(q, an) if (q or an) else print("HEAT files not found", file=sys.stderr)


if __name__ == "__main__":
    main()
