#!/usr/bin/env python3
"""
Process locally downloaded source files for the Country Data agent.

iMaPP (IMF Integrated Macroprudential Policy database, public) -> IMF_iMaPP_macroprudential.xlsx:
Definitions, Tools_in_place, Measures_history, Summary, Actions.

    python m365-agent/build_local_sources.py [--imapp FILE]
Default: the newest iMaPP_database*.xlsx in the repository root.
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


LABEL = re.compile(r"\b([A-Z][A-Z0-9-]{1,6}(?=s?\b)|(?i:advances to stable resources|debt-to-income|"
                   r"loan-to-value|loan-to-deposit|reserve requirements?|cash reserve|capital conservation "
                   r"buffer|countercyclical (?:capital )?buffer|liquidity coverage|net stable funding|"
                   r"leverage ratio|risk weights?|provisions?|capital adequacy))")
PAIR = re.compile(r"from " + NUM + r" to " + NUM + r"|to " + NUM + r"[^.;]{0,40}?from " + NUM, re.I)
SKIP = {"THE", "AND", "FOR", "ALL", "NEW", "IFRS", "IFRS9", "SAR", "USD", "US", "KD", "QR", "AED", "DATE", "COVID",
        "COVID-19", "GDP", "IMF", "BIS", "SME", "CBK", "CBUAE", "SAMA", "CBB", "CBO", "QCB", "BCBS", "EU", "ECB"}


def level_changes(text):
    """All 'from X% to Y%' changes in an iMaPP description, each labelled with the nearest ratio name
    before it in the same sentence, e.g. 'LAR 7 to 10; advances to stable resources 110 to 100'."""
    t = re.sub(r"\s+", " ", str(text or ""))
    out = []
    for m in PAIR.finditer(t):
        old, new = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        start = max(t.rfind(".", 0, m.start()), t.rfind(";", 0, m.start())) + 1
        names = [x for x in LABEL.findall(t[start:m.start()]) if x.upper() not in SKIP]
        lab = names[-1] if names else ""
        item = f"{lab} {float(old):g} to {float(new):g}".strip()
        if item not in out:
            out.append(item)
    return "; ".join(out)


def latest_ltv(xl):
    """Latest average LTV limit per country from the iMaPP LTV_average sheet (Country, Year, Month, LTV_average)."""
    try:
        d = xl.parse("LTV_average").dropna(subset=["LTV_average"])
    except Exception:
        return {}
    d = d.sort_values(["Country", "Year", "Month"]).groupby("Country").tail(1)
    return {str(c).strip(): (float(v), f"{int(y)}-{int(m):02d}")
            for c, v, y, m in zip(d["Country"], d["LTV_average"], d["Year"], d["Month"])}


REVERT = re.compile(r"revert|back to|returned to|return to|restor|expir|withdr|lapse|ended", re.I)


def current_level(hist):
    """Latest levels stated for a tool, with the month set. If a later action reverts, ends or lets a
    measure expire, the levels from before that temporary change are reported as restored."""
    lv = [(i, stated_levels(x)) for i, (_, _, x) in enumerate(hist)]
    lv = [(i, v) for i, v in lv if v and v != "0"]
    if not lv:
        return ""
    i, v = lv[-1]
    later = [(d, x) for d, _, x in hist[i + 1:] if REVERT.search(x)]
    if later and len(lv) > 1:
        j, w = lv[-2]
        return f"{w} (set {hist[j][0]}; restored {later[-1][0]})"
    return f"{v} (set {hist[i][0]})"


def stated_levels(text):
    """Labelled 'from X to Y' changes, else the percentages mentioned (e.g. '50, 60, 70')."""
    lv = level_changes(text)
    if lv:
        return lv
    pct = r"(\d+(?:\.\d+)?)\s*(?:%|percent(?!age)|per cent)(?!age)(?!\s*points?)"  # levels, not pp changes
    nums = list(dict.fromkeys(f"{float(x):g}" for x in re.findall(pct, str(text or ""), re.I)))
    return ", ".join(nums[:6])


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
    s_rows, h_rows = [], []
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
            hist = []  # every action of this tool, oldest first
            for idx, e in ev.iterrows():
                d = f"{int(e['Year'])}-{int(e['Month']):02d}"
                tt, ll = int(tg.loc[idx, t]), int(lg.loc[idx, t])
                tx = re.sub(r"\s+", " ", re.sub(r"[　-鿿]", "", bymonth.get(f"{int(e['Year'])}M{int(e['Month'])}", "")
                                                   .replace("_x000D_", " "))).strip()
                hist.append((d, "tightening" if tt and not ll else "loosening" if ll and not tt else "both", tx))
                h_rows.append({"Economy code": iso, "Economy": cname, "Tool": TOOLS[t], "Date": d,
                               "Direction": hist[-1][1], "Levels, percent": stated_levels(tx),
                               "Measure": tx.replace("%", " percent")[:700], "Citation": IMAPP_CITATION})
            level_now = current_level(hist)
            if t == "LTV" and orig[iso] in ltv:
                v, mth = ltv[orig[iso]]
                level_now = f"average LTV limit {v:g} ({mth})" + (f"; last stated: {level_now}" if level_now else "")
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
                           "Magnitude note": mag[3], "Level change (percent)": level_changes(text),
                           "Current or last stated level": level_now,
                           "Latest description": re.sub(r"\s+", " ", text)[:600],
                           "Citation": IMAPP_CITATION})
    summary = pd.DataFrame(s_rows)
    history = pd.DataFrame(h_rows).sort_values(["Economy", "Tool", "Date"])
    agg = {"Capital", "LCG", "LoanR"}  # '(all)' rows, dropped when the sub-tools are listed
    keep = [not (t in agg and ((summary["Economy code"] == e) & summary["Tool code"].str.startswith(t + "_")).any())
            for e, t in zip(summary["Economy code"], summary["Tool code"])]
    in_place = summary[keep].sort_values(["Economy", "Latest action"], ascending=[True, False])
    in_place = pd.DataFrame({
        "Economy code": in_place["Economy code"], "Economy": in_place["Economy"], "Tool": in_place["Tool"],
        "In place since": in_place["First action"],
        "Latest change": in_place["Latest action"] + ", " + in_place["Latest direction"],
        "Level, percent (date set)": in_place["Current or last stated level"],
        "Latest measure": in_place["Latest description"].str.replace("%", " percent").str.slice(0, 400),
        "Citation": IMAPP_CITATION})
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
            "Sheet 'Tools_in_place': one table per economy - every tool introduced (in place unless the latest "
            "measure removed it), since when, latest change, level changes (each 'from X to Y' in the text, "
            "labelled with its ratio, e.g. LAR 7 to 10) and the latest measure. Aggregate '(all)' tools are left "
            "out when their sub-tools are listed. Economies not in iMaPP (e.g. Qatar) have no rows.",
            "In Tools_in_place, 'Level, percent (date set)' = the latest levels stated in any action for that tool, with "
            "the month they were set (for LTV also iMaPP's average LTV limit). If the latest action reverts or ends a "
            "measure, read Measures_history for the levels it restored.",
            "Sheet 'Measures_history': every recorded action since 1990 for every economy and tool - date, direction, "
            "levels mentioned and the IMF description (from all instrument sheets of the iMaPP database).",
            "Tools: " + "; ".join(f"{k} = {v}" for k, v in TOOLS.items()) + ".",
            "iMaPP records policy actions (changes), not whether a tool is currently in force; a tool with "
            "tightenings and no later full loosening is likely still in use - check the description.",
            "Cite: " + IMAPP_CITATION + ". " + IMAPP_LINK],
        "Definitions": definitions, "Tools_in_place": in_place, "Measures_history": history, "Summary": summary,
        "Actions": actions})
    print(f"iMaPP: {len(names)} economies, {len(summary)} economy-tool records, {time.time() - t0:.0f}s",
          file=sys.stderr)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--imapp", default=None)
    a.add_argument("--only", choices=["imapp", "heat"])
    args, rest = a.parse_known_args()
    if args.only != "heat":
        p = Path(args.imapp) if args.imapp else newest("iMaPP_database*.xlsx")
        build_imapp(p) if p else print("iMaPP file not found", file=sys.stderr)
    private = HERE / "private" / "build_heat.py"
    if args.only != "imapp" and private.exists():  # bank data builder kept outside GitHub
        import runpy
        sys.argv = [str(private)] + rest
        runpy.run_path(str(private), run_name="__main__")


if __name__ == "__main__":
    main()
