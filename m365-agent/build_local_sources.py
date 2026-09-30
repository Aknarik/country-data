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

    python m365-agent/build_local_sources.py [--imapp FILE] [--heat FILE]
Defaults: the newest iMaPP_database*.xlsx and HEAT*.xlsm in the repository root.
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
            s_rows.append({"Economy code": iso, "Economy": cname, "Tool code": t, "Tool": TOOLS[t],
                           "Tightenings": nt, "Loosenings": nl,
                           "Tightenings since 2020": int(tg[tg["Year"] >= 2020][t].sum()),
                           "Loosenings since 2020": int(lg[lg["Year"] >= 2020][t].sum()),
                           "First action": f"{int(ev.iloc[0]['Year'])}-{int(ev.iloc[0]['Month']):02d}",
                           "Latest action": f"{int(last['Year'])}-{int(last['Month']):02d}",
                           "Latest direction": "tightening" if lt and not ll else "loosening" if ll and not lt else "both",
                           "Latest description": re.sub(r"\s+", " ", text)[:600],
                           "Citation": IMAPP_CITATION})
    summary = pd.DataFrame(s_rows)
    last_date = f"{int(mapp['Year'].max())}"
    b.write_book(IMAPP_OUT, {
        "README": [
            "IMF Integrated Macroprudential Policy (iMaPP) Database - summary for the Country Data agent.",
            f"Built {time.strftime('%Y-%m-%d')} from {path.name} (data to {last_date}). {len(names)} economies, "
            f"{len(tools)} tool types, monthly since 1990.",
            "Sheet 'Summary': per economy and tool - number of tightenings and loosenings (all years and since "
            "2020), first and latest action, direction and the IMF's text description of the latest action.",
            "Sheet 'Actions': net actions per economy, tool and year (tightenings minus loosenings).",
            "Tools: " + "; ".join(f"{k} = {v}" for k, v in TOOLS.items()) + ".",
            "iMaPP records policy actions (changes), not whether a tool is currently in force; a tool with "
            "tightenings and no later full loosening is likely still in use - check the description.",
            "Cite: " + IMAPP_CITATION + ". " + IMAPP_LINK],
        "Summary": summary, "Actions": actions})
    print(f"iMaPP: {len(names)} economies, {len(summary)} economy-tool records, {time.time() - t0:.0f}s",
          file=sys.stderr)


# --------------------------------------------------------------------------- HEAT
def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def read_o_sheet(ws):
    """Bank rows of an O- sheet: key, country, then one value per quarter."""
    rows = ws.iter_rows(values_only=True)
    header = None
    out = []
    for r in rows:
        if header is None:
            if r and len(r) > 2 and str(r[1]).strip() == "SNL Institution Key":
                header = [str(x).strip() if x is not None else "" for x in r]
                qcols = [i for i, h in enumerate(header) if re.fullmatch(r"\d{4}Q[1-4]", h)]
                ccol = header.index("Country")
            continue
        if r[1] is None or str(r[1]).strip() == "":
            continue
        out.append([str(r[1]).strip(), str(r[ccol]).strip()] + [_num(r[i]) for i in qcols])
    q = [header[i][:4] + "-Q" + header[i][-1] for i in qcols]
    df = pd.DataFrame(out, columns=["key", "country"] + q).drop_duplicates("key")
    return df


def read_total_assets(ws):
    """TotalAssets sheet: bank key -> total assets (USD millions) per quarter."""
    rows = list(ws.iter_rows(min_row=1, max_row=6, values_only=True))
    qrow = rows[4]
    qcols = [i for i, h in enumerate(qrow) if h and re.fullmatch(r"\d{4}Q[1-4]", str(h).strip())]
    out = []
    for r in ws.iter_rows(min_row=7, values_only=True):
        if r[1] is None or str(r[1]).strip() == "":
            continue
        out.append([str(r[1]).strip()] + [_num(r[i]) for i in qcols])
    q = [str(qrow[i]).strip()[:4] + "-Q" + str(qrow[i]).strip()[-1] for i in qcols]
    return pd.DataFrame(out, columns=["key"] + q).drop_duplicates("key").set_index("key")


def build_heat(path):
    t0 = time.time()
    wb = load_workbook(path, read_only=True, data_only=True)
    ta = read_total_assets(wb["TotalAssets"])
    iso = {}
    rows = []
    for sheet, (code, name) in HEAT_SHEETS.items():
        df = read_o_sheet(wb[sheet])
        per = [c for c in df.columns if "-Q" in c]
        for cty, g in df.groupby("country"):
            if cty not in iso:
                try:
                    iso[cty] = {"Palestine": "WBG"}.get(cty) or b.cd.resolve_countries(cty, verbose=False)[0]
                except Exception:
                    iso[cty] = cty
            v = g.set_index("key")[per]
            w = ta.reindex(v.index)[[c for c in per if c in ta.columns]].reindex(columns=per)
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
                             "Type": "Country", "Indicator code": f"HEAT_{code}_{sc}",
                             "Indicator": f"{name} - {sname}",
                             "Unit": "Number of banks" if sc == "N" else "Percent",
                             "Citation": HEAT_CITATION, "Source link": "", **ser.to_dict()})
    # banking system size from the same bank sample
    for cty in {r["Economy code"] for r in rows}:
        pass
    out = pd.DataFrame(rows)
    per = sorted(c for c in out.columns if re.fullmatch(r"\d{4}-Q\d", str(c)))
    out = out[[c for c in out.columns if c not in per] + per].sort_values(["Economy", "Indicator code"])
    LOCAL.mkdir(exist_ok=True)
    b.write_book(HEAT_OUT, {
        "README": [
            "HEAT 2.0 bank-level soundness indicators aggregated to country level - IMF-INTERNAL USE ONLY.",
            f"Built {time.strftime('%Y-%m-%d')} from {path.name}. Source: S&P Capital IQ Pro via the IMF HEAT tool "
            "(licensed). No individual bank names or values are included.",
            "For each country and quarter: median bank, 25th and 75th percentile, asset-weighted mean "
            "(weights = total assets) and number of banks reporting.",
            "Indicators: Tier 1 capital ratio; NPLs net of provisions to total loans; return on average "
            "assets; liquid assets to total liabilities; tangible common equity to tangible assets.",
            "Do not publish outside the IMF; follow the HEAT ReadMe and the S&P licence."],
        "HEAT_country": out})
    print(f"HEAT: {out['Economy code'].nunique()} economies, {len(out)} rows, {time.time() - t0:.0f}s",
          file=sys.stderr)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--imapp", default=None)
    a.add_argument("--heat", default=None)
    a.add_argument("--only", choices=["imapp", "heat"])
    args = a.parse_args()
    if args.only != "heat":
        p = Path(args.imapp) if args.imapp else newest("iMaPP_database*.xlsx")
        build_imapp(p) if p else print("iMaPP file not found", file=sys.stderr)
    if args.only != "imapp":
        p = Path(args.heat) if args.heat else newest("HEAT*.xlsm")
        build_heat(p) if p else print("HEAT file not found", file=sys.stderr)


if __name__ == "__main__":
    main()
