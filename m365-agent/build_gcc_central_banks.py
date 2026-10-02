#!/usr/bin/env python3
"""
Fill GCC gaps in the IMF data with central bank statistics.

Adds to the agent's workbooks (public data):
  Kuwait  - CBK Monthly Monetary Statistical Bulletin, Table 13: sectoral distribution of local
            banks' credit facilities to residents  -> loan portfolio (FSI workbook, Loan_portfolio)
  Saudi   - SAMA Monthly Statistical Bulletin (Excel), Table 12d: bank credit by economic
            activity, quarterly since 2021                     -> loan portfolio
  Oman    - CBO Quarterly Statistical Bulletin (PDF): Table 17 bank credit by sectors -> loan
            portfolio (checked against the published % shares); Table 10 selected ratios -> FX loans
            to total loans and customer deposits to loans (FSI workbook)
  Bahrain - CBB Statistical Bulletin (Excel):
            Table 37 financial soundness indicators  -> FSI workbook, FSI_Quarterly
            Table 17 retail banks' assets by sector  -> banking workbook: asset structure and
                                                        sovereign-bank nexus
Shares are computed from the published levels and checked (sectors add up to the total; Oman: equal
to the published shares). Downloaded bulletins are kept in local_data/.

    python m365-agent/build_gcc_central_banks.py [--cbb FILE.xlsx]
Without --cbb the latest CBB bulletin is downloaded from cbb.gov.bh.
"""

import argparse
import io
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from openpyxl import load_workbook

try:  # use the Windows/macOS certificate store (some central bank sites send incomplete chains)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_data_file as b  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130 Safari/537.36"}
CBK_T13 = "https://www.cbk.gov.kw/en/statistics-and-publication/dynamic-statistical-releases/monthly/{y}/{m:02d}/13"
CBK_BULLETIN = "https://www.cbk.gov.kw/en/statistics-and-publication/bulletins-and-periodicals/monthly-monetary-statistical-bulletin"
KAPSARC = ("https://datasource.kapsarc.org/api/explore/v2.1/catalog/datasets/bank-credit-by-economic-activity/"
           "exports/csv")
CBB_PAGE = "https://www.cbb.gov.bh/publications/"
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                                      "Nov", "Dec"], 1)}


def get(url, **kw):
    r = requests.get(url, headers=UA, timeout=120, **kw)
    r.raise_for_status()
    return r


AMOUNTS = []  # loan amounts by sector (same codes as the shares) for sheet Loan_amounts


def lp_rows(iso, name, shares, citation, link, prefix, levels=None, unit=""):
    """Loan-portfolio rows in the agent's Lp format from a DataFrame (periods x sectors, % of total).
    levels (same shape, amounts) are kept in AMOUNTS for growth rates."""
    rows = []
    for sector in shares.columns:
        s = shares[sector].dropna().round(2)
        code = f"LOANS_{prefix}_" + re.sub(r"[^A-Z0-9]+", "_", sector.upper()).strip("_")[:30]
        rows.append({"Economy code": iso, "Economy": name, "Type": "Country", "Indicator code": code,
                     "Indicator": sector, "Unit": "Percent of total credit", "Citation": citation,
                     "Source link": link, **s.to_dict()})
        if levels is not None and sector in levels:
            AMOUNTS.append({**rows[-1], "Unit": unit, **levels[sector].dropna().round(3).to_dict()})
    return rows


# --------------------------------------------------------------------------- Kuwait (CBK Table 13)
def kuwait():
    today = pd.Timestamp.today()
    for back in range(0, 8):  # latest monthly release that exists
        d = today - pd.DateOffset(months=back)
        try:
            html = get(CBK_T13.format(y=d.year, m=d.month)).text
            t = pd.read_html(io.StringIO(html))[0]
            if len(t) > 3:
                break
        except Exception:
            continue
    else:
        raise RuntimeError("CBK Table 13 not reachable")
    cols = [" | ".join(dict.fromkeys(str(v) for v in c)) for c in t.columns]
    t.columns = cols
    # rows: year-ends (a year with values) and months (Jan...Dec after a bare year row)
    periods, year = [], None
    for lab in t[cols[0]].astype(str):
        lab = lab.strip()
        if re.fullmatch(r"\d{4}", lab):
            year = int(lab)
            periods.append(f"{year}-Q4")  # year-end = Q4 (all periods quarterly)
        elif lab[:3] in MONTHS and year:
            periods.append(f"{year}-Q{(MONTHS[lab[:3]] - 1) // 3 + 1}|{MONTHS[lab[:3]]}")
        else:
            periods.append(None)
    t.index = periods
    t = t[t.index.notna()].drop(columns=cols[0]).apply(pd.to_numeric, errors="coerce").dropna(how="all")
    # keep the last month of each quarter for monthly rows
    q = [p for p in t.index if "|" in p]
    keep = [p for p in t.index if "|" not in p] + [max((x for x in q if x.split("|")[0] == k),
                                                         key=lambda x: int(x.split("|")[1]))
                                                     for k in dict.fromkeys(x.split("|")[0] for x in q)]
    t = t.loc[keep]
    t.index = [p.split("|")[0] for p in t.index]
    pick = {  # customer credit (loans to banks and subtotals excluded)
        "Trade": "Trade", "Industry": "Industry", "Constructions": "Construction",
        "Agriculture": "Agriculture and fishing", "Non-Bank Financial": "Non-bank financial institutions",
        "Consumer Loans": "Household consumer loans", "Installment Loans": "Household installment (housing) loans",
        "Private Residential": "Household private residential loans", "Personal Facilities | Other": "Household other personal loans",
        "Purchase of Securities | Total": "Purchase of securities", "Real Estate": "Real estate",
        "Crude Oil": "Crude oil and gas", "Public Services": "Public services", "Other Services": "Other services"}
    lev = pd.DataFrame({new: t[[c for c in t.columns if key in c][0]] for key, new in pick.items()})
    shares = 100 * lev.div(lev.sum(axis=1), axis=0)
    cite = ("Central Bank of Kuwait, Monthly Monetary Statistical Bulletin, Table 13: local banks' sectoral "
            "distribution of utilized credit facilities to residents (excluding loans to banks)")
    print(f"Kuwait: {len(shares)} periods {list(shares.index)[:2]}..{list(shares.index)[-1]}", file=sys.stderr)
    return lp_rows("KWT", "Kuwait", shares.T.T, cite, CBK_BULLETIN, "CBK", lev, "Millions of Kuwaiti dinars")


# --------------------------------------------------------------------------- Saudi Arabia (SAMA via KAPSARC)
def saudi():
    d = pd.read_csv(io.StringIO(get(KAPSARC).text), sep=";")
    d = d[(d["periodicity"] == "Quarterly") & (d["economic_activity"].str.upper() != "TOTAL")]
    d["period"] = d["date"].astype(str) + "-" + d["quarter"].astype(str)
    lev = d.pivot_table(index="period", columns="economic_activity", values="value", aggfunc="first").sort_index()
    lev = lev.rename(columns=lambda c: re.sub(r"\s+,", ",", re.sub(r"\s+", " ", c.replace("Agricultureand", "Agriculture and"))).strip())
    lev = lev.rename(columns={"Miscellaneous": "Miscellaneous (mainly personal loans)",
                              "Government & Quasi Govt.": "Government and quasi-government"})
    shares = 100 * lev.div(lev.sum(axis=1), axis=0)
    cite = ("Saudi Central Bank (SAMA), Monthly Statistical Bulletin, Table 12d: bank credit by economic "
            "activity (via KAPSARC data portal)")
    print(f"Saudi Arabia: {len(shares)} quarters {shares.index[0]}..{shares.index[-1]}", file=sys.stderr)
    return lp_rows("SAU", "Saudi Arabia", shares, cite, "https://www.sama.gov.sa/en-US/Statistics/Pages/MonthlyStatistics.aspx", "SAMA")


# --------------------------------------------------------------------------- Bahrain (CBB bulletin)
def cbb_file(path):
    if path:
        return Path(path)
    try:
        links = re.findall(r'href="(https://www\.cbb\.gov\.bh/wp-content/uploads/[^"]+\.xlsx)"', get(CBB_PAGE).text)
    except Exception as e:
        links = []
        print(f"CBB site not reachable ({type(e).__name__})", file=sys.stderr)
    if not links:  # use the latest bulletin already downloaded (files like Jul-2026.xlsx)
        local = sorted((HERE.parent / "local_data").glob("[A-Z][a-z][a-z]-20[0-9][0-9]*.xlsx"), key=lambda p: p.stat().st_mtime)
        if local:
            print(f"using {local[-1].name}", file=sys.stderr)
            return local[-1]
        raise RuntimeError("No CBB Excel bulletin link found")
    out = HERE.parent / "local_data" / Path(links[0]).name
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(get(links[0]).content)
    return out


def sheet_rows(wb, name):
    return [[("" if v is None else v) for v in r] for r in wb[name].iter_rows(values_only=True)]


def bahrain_fsi(wb, edition):
    R = sheet_rows(wb, "37")
    codes = ["FSI688_CFSI_PT", "FSI626_CFSI_PT", "AQ12_CFSI_PT", "AQ14_CFSI_PT", "ROA_CFSI_PT",
             "ROE_CFSI_PT", "FSI283_LIQATTA_PT"]
    vals, year, annual = {}, None, {}
    for r in R:
        y, q = str(r[0]).strip(), str(r[1]).strip()
        if re.fullmatch(r"\d{4}", y):
            year = int(y)
        nums = [pd.to_numeric(v, errors="coerce") for v in r[2:9]]
        if year is None or all(pd.isna(n) for n in nums):
            continue
        if re.fullmatch(r"Q[1-4]", q):
            qn = int(q[1])
            per = f"{year}-Q{qn}"
            # ROA and ROE are year-to-date: annualize
            nums = [n * 4 / qn if c in ("ROA_CFSI_PT", "ROE_CFSI_PT") and pd.notna(n) else n
                    for c, n in zip(codes, nums)]
            vals[per] = nums
        elif q == "" and re.fullmatch(r"\d{4}", y):
            annual[f"{year}-Q4"] = nums  # year-end values fill earlier years as Q4
    for per, nums in annual.items():
        vals.setdefault(per, nums)
    df = pd.DataFrame(vals, index=codes).T.sort_index()
    rows = []
    cite = (f"Central Bank of Bahrain, Statistical Bulletin ({edition}), Table 37: financial soundness "
            "indicators, entire banking sector (ROA and ROE annualized)")
    for c in codes:
        name, group, up = b.fd.FSI_SERIES[c]
        s = df[c].dropna().round(3)
        rows.append({"Economy code": "BHR", "Economy": "Bahrain", "Type": "Country",
                     "Sector": "Deposit takers", "Indicator code": c, "Indicator": name, "Group": group,
                     "More vulnerable when": "higher" if up else "lower", "Unit": "Percent",
                     "Citation": cite, "Source link": CBB_PAGE, **s.to_dict()})
    print(f"Bahrain FSIs: {len(df)} periods {df.index[0]}..{df.index[-1]}", file=sys.stderr)
    return rows


def bahrain_assets(wb, edition):
    """Retail banks' assets by sector (Table 17, BD + FC) -> asset structure and sovereign-bank nexus."""
    R = sheet_rows(wb, "17")
    out, year = {}, None
    for r in R:
        y, m = str(r[0]).strip(), str(r[1]).strip()
        if re.fullmatch(r"\d{4}", y):
            year = int(y)
        nums = [pd.to_numeric(v, errors="coerce") for v in r[2:14]]
        if year is None or sum(pd.notna(n) for n in nums) < 10:
            continue
        per = str(year) if m == "" else None
        if per:
            banks, priv, gov, oth = nums[0] + nums[1], nums[2] + nums[3], nums[4] + nums[5], nums[6] + nums[7]
            foreign, total = nums[8] + nums[9], nums[10] + nums[11]
            out[per] = {"BANK_STR_PRIV": priv, "BANK_STR_GOV": gov, "BANK_STR_NRES": foreign,
                        "BANK_STR_OTHER": banks + oth + (total - banks - priv - gov - oth - foreign)}
            out[per] = {k: 100 * v / total for k, v in out[per].items()}
            out[per]["BANK_GOV_TA"] = out[per]["BANK_STR_GOV"]
    df = pd.DataFrame(out).T.sort_index()
    names = {k: v[0] for k, v in b.fd.BANK_INDICATORS.items()}
    names["BANK_STR_OTHER"] = "Asset structure: Other assets (incl. claims on banks)"
    names["BANK_STR_PRIV"] = "Asset structure: Private sector (non-banks)"
    cite = (f"Central Bank of Bahrain, Statistical Bulletin ({edition}), Table 17: retail banks' aggregated "
            "balance sheet, assets by sector (BD and foreign currency)")
    rows = [{"Economy code": "BHR", "Economy": "Bahrain", "Type": "Country", "Indicator code": c,
             "Indicator": names[c], "Unit": "Percent of total assets", "Method": "Retail banks, year-end",
             "Citation": cite, "Source link": CBB_PAGE, **df[c].dropna().round(2).to_dict()} for c in df.columns]
    print(f"Bahrain assets: {len(df)} years {df.index[0]}..{df.index[-1]}", file=sys.stderr)
    return rows


# --------------------------------------------------------------------------- Saudi Arabia (SAMA Excel)
SAMA_XLSX = "https://www.sama.gov.sa/en-US/Statistics/MonthlyStatistics/Monthly_Bulletin_{m}_{y}.xlsx"
SAMA_PAGE = "https://www.sama.gov.sa/en-US/Statistics/Pages/MonthlyStatistics.aspx"
FULL_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December"]


def sama_file(path=None):
    """Latest SAMA Monthly Bulletin Excel (tries the last 8 months)."""
    if path:
        return Path(path)
    today = pd.Timestamp.today()
    for back in range(0, 8):
        d = today - pd.DateOffset(months=back)
        url = SAMA_XLSX.format(m=FULL_MONTHS[d.month - 1], y=d.year)
        try:
            r = get(url)
            if r.content[:2] == b"PK":
                out = HERE.parent / "local_data" / Path(url).name
                out.parent.mkdir(exist_ok=True)
                out.write_bytes(r.content)
                return out
        except Exception:
            continue
    local = sorted((HERE.parent / "local_data").glob("Monthly_Bulletin_*.xlsx"), key=lambda p: p.stat().st_mtime)
    if local:  # SAMA site unreachable: use the latest bulletin already downloaded
        print(f"SAMA download failed; using {local[-1].name}", file=sys.stderr)
        return local[-1]
    raise RuntimeError("No SAMA Monthly Bulletin Excel found")


def saudi_sama(path):
    """SAMA Table 12d: bank credit by economic activity (ISIC, from 2021), quarter-end months."""
    x = pd.read_excel(path, sheet_name="12d", header=None)
    hdr = {j: re.sub(r"\s+", " ", " ".join(str(v) for v in x.iloc[7:9, j] if pd.notna(v))).strip()
           for j in range(x.shape[1])}
    blocks = [j for j, h in hdr.items() if h.startswith("End of")]
    data = {}
    for k, start in enumerate(blocks):
        stop = blocks[k + 1] if k + 1 < len(blocks) else x.shape[1]
        # rows are aligned across blocks; the blocks label months differently (month-end vs 1st),
        # so use the first block's dates everywhere
        dates = pd.to_datetime(x.iloc[9:, blocks[0]], errors="coerce")
        ok = dates.notna().values  # skip note rows at the bottom
        for j in range(start + 1, stop):
            if hdr.get(j):
                v = pd.Series(pd.to_numeric(x.iloc[9:, j], errors="coerce").values[ok], index=dates.values[ok])
                data[hdr[j]] = v[~v.index.duplicated(keep="last")]
    lev = pd.DataFrame(data)
    lev = lev[lev.index.notna()].dropna(how="all")
    total = lev.pop("Total") if "Total" in lev else lev.sum(axis=1)
    # monthly rows only (annual rows are dated 1 January): keep quarter-end months and the latest month
    monthly = lev[[d.day != 1 or d.month != 1 for d in lev.index]]
    monthly = monthly[monthly.index >= "2021-03-01"]
    keep = sorted(set([d for d in monthly.index if d.month in (3, 6, 9, 12)] + [monthly.index.max()]))
    sel = monthly.loc[keep]
    check = (sel.sum(axis=1) / total.reindex(sel.index) - 1).abs().max()  # sectors vs published total
    q = sel.copy()
    q.index = [f"{d.year}-Q{(d.month - 1) // 3 + 1}" for d in q.index]
    q = q[~q.index.duplicated(keep="last")]
    if check > 0.01:
        raise ValueError(f"SAMA sectors do not add up to the total (max gap {check:.1%})")
    shares = 100 * q.div(q.sum(axis=1), axis=0)
    edition = re.sub(r"Monthly_Bulletin_|\.xlsx", "", Path(path).name).replace("_", " ")
    cite = (f"Saudi Central Bank (SAMA), Monthly Statistical Bulletin ({edition}), Table 12d: bank credit "
            "classified by economic activity")
    print(f"Saudi Arabia (SAMA): {len(shares)} quarters {shares.index[0]}..{shares.index[-1]}, "
          f"sector sum check {check:.2%}", file=sys.stderr)
    return lp_rows("SAU", "Saudi Arabia", shares, cite, SAMA_PAGE, "SAMA", q, "Millions of Saudi riyals")


# --------------------------------------------------------------------------- Oman (CBO quarterly bulletin PDF)
CBO_QB = "https://cbo.gov.om/sites/assets/Documents/English/Publications/QuarterlyBulletins/{y}/QB{m}{y}{s}.pdf"
CBO_PAGE = "https://cbo.gov.om/Pages/QuarterlyBulletins.aspx"
QB_MONTHS = {"March": 1, "June": 2, "September": 3, "Sept": 3, "Sep": 3, "December": 4, "Dec": 4}
NUM = re.compile(r"-?[\d,]+\.\d+|-?\d[\d,]*")


def cbo_bulletins(years=range(2022, 2031)):
    """Download the CBO Quarterly Statistical Bulletins available (March of each year + latest)."""
    import pdfplumber  # noqa: F401  (fail early if missing)
    out = []
    for y in years:
        for mname, q in QB_MONTHS.items():
            for suffix in ("En", "EN"):
                url = CBO_QB.format(y=y, m=mname, s=suffix)
                path = HERE.parent / "local_data" / f"CBO_QB_{y}_Q{q}.pdf"
                if path.exists():
                    out.append((y, q, path, url))
                    break
                try:
                    r = requests.get(url, headers=UA, timeout=120)
                    if r.status_code == 200 and r.content[:4] == b"%PDF":
                        path.parent.mkdir(exist_ok=True)
                        path.write_bytes(r.content)
                        out.append((y, q, path, url))
                        break
                except Exception:
                    pass
    return sorted({o[2]: o for o in out}.values())  # one entry per bulletin file


def _quarters_back(y, q, n):
    """The n quarters ending at (y, q), oldest first, as 'YYYY-Qn'."""
    out = []
    for _ in range(n):
        out.append(f"{y}-Q{q}")
        y, q = (y, q - 1) if q > 1 else (y - 1, 4)
    return out[::-1]


def _page_with(pdf, title, must):
    """Text of the table page: contains the title and a word only the table itself has
    (so the table of contents is skipped)."""
    for p in pdf.pages:
        t = p.extract_text() or ""
        if title.lower() in t.lower() and must.lower() in t.lower():
            return t
    return ""


def chain_link(editions):
    """Join the 5-quarter amounts of successive bulletin editions into one consistent series: older
    editions are rescaled (per sector) to the newer ones at their first overlapping quarter, so coverage
    changes between editions do not show up as growth. Stops at the first edition with no overlap."""
    linked = editions[-1].copy()
    for old in reversed(editions[:-1]):
        common = [p for p in old.index if p in linked.index]
        if not common:
            break
        f = (linked.loc[common[0]] / old.loc[common[0]].where(old.loc[common[0]] != 0)).fillna(1)
        new = [p for p in old.index if p not in linked.index]
        linked = pd.concat([old.loc[new] * f, linked]).sort_index()
    return linked


def oman():
    import pdfplumber
    sectors, ratios, sources, editions = {}, {}, [], []
    for y, q, path, url in cbo_bulletins():
        with pdfplumber.open(path) as pdf:
            t17 = _page_with(pdf, "Bank Credit by Sectors", "Personal Loans")
            t10 = _page_with(pdf, "Selected Ratios: Conventional Banks", "Credit to Deposits")
        per5 = _quarters_back(y, q, 5)
        found = {}
        for line in t17.splitlines():
            m = re.match(r"([A-Za-z][A-Za-z ,&\-()]+?)\s+(-?[\d,]+\.?\d*\s.*)$", line.strip())
            if not m or m.group(1).strip().lower() in ("total", "sectors", "amount"):
                continue
            nums = [float(v.replace(",", "")) for v in NUM.findall(m.group(2))][:10]
            if len(nums) != 10:
                continue
            name = re.sub(r"\s+,", ",", re.sub(r"\s+", " ", m.group(1))).strip()
            found[name] = nums
        # accept a bulletin only if all 15 sectors were read and shares match the published %
        amt_b = pd.DataFrame({k: v[0::2] for k, v in found.items()}, index=per5)
        pub_b = pd.DataFrame({k: v[1::2] for k, v in found.items()}, index=per5)
        gap_b = (100 * amt_b.div(amt_b.sum(axis=1), axis=0) - pub_b).abs().max().max() if found else 99
        if len(found) < 15 or gap_b > 0.3:
            print(f"  Oman: skipped bulletin {y}-Q{q} ({len(found)} sectors read, gap {gap_b:.2f} pp)", file=sys.stderr)
            continue
        editions.append(amt_b)
        for name, nums in found.items():
            for i, p in enumerate(per5):
                sectors.setdefault(name, {})[p] = (nums[2 * i], nums[2 * i + 1])  # (amount, published %)
        per9 = _quarters_back(y, q, 9)
        for line in t10.splitlines():
            for key, label in (("Credit to Deposits", "cd"), ("Foreign Currency Credit to total Credit", "fx")):
                if re.match(r"\d+\.\s*" + key, line.strip()):
                    nums = [float(v) for v in re.findall(r"\d+\.\d+", line.split(key, 1)[1])][:9]
                    if len(nums) == 9:
                        for p, v in zip(per9, nums):
                            ratios.setdefault(label, {})[p] = v
        sources.append(f"{['March', 'June', 'September', 'December'][q - 1]} {y}")
    amt = pd.DataFrame({k: {p: v[0] for p, v in d.items()} for k, d in sectors.items()}).sort_index()
    pub = pd.DataFrame({k: {p: v[1] for p, v in d.items()} for k, d in sectors.items()}).sort_index()
    shares = 100 * amt.div(amt.sum(axis=1), axis=0)
    gap = (shares - pub).abs().max().max()
    if gap > 0.3:
        raise ValueError(f"Oman: computed shares differ from published % by up to {gap:.2f} pp")
    cite = (f"Central Bank of Oman, Quarterly Statistical Bulletin (editions {', '.join(sources)}), Table 17: "
            "bank credit by sectors (other depository corporations)")
    rows = lp_rows("OMN", "Oman", shares, cite, CBO_PAGE, "CBO", chain_link(editions), "Thousands of Omani rials "
                   "(editions chain-linked for growth rates)")
    fsi = []
    rcite = (f"Central Bank of Oman, Quarterly Statistical Bulletin (editions {', '.join(sources)}), Table 10: "
             "selected ratios, conventional banks")
    conv = {"FSI131_AFSI_PT": pd.Series(ratios.get("fx", {})),
            "FSI55_AFSI_PT": 100 * 100 / pd.Series(ratios.get("cd", {}))}  # deposits/loans = 1/(credit/deposits)
    for c, s in conv.items():
        name, group, up = b.fd.FSI_SERIES[c]
        fsi.append({"Economy code": "OMN", "Economy": "Oman", "Type": "Country", "Sector": "Deposit takers",
                    "Indicator code": c, "Indicator": name, "Group": group,
                    "More vulnerable when": "higher" if up else "lower", "Unit": "Percent",
                    "Citation": rcite + (" (customer deposits to loans derived as 100 / credit-to-deposits ratio)"
                                         if c == "FSI55_AFSI_PT" else ""),
                    "Source link": CBO_PAGE, **s.sort_index().round(2).to_dict()})
    print(f"Oman: loan portfolio {len(shares)} quarters {shares.index[0]}..{shares.index[-1]} "
          f"(max gap vs published % {gap:.2f} pp); ratios {len(conv['FSI131_AFSI_PT'])} quarters", file=sys.stderr)
    return rows, fsi


# --------------------------------------------------------------------------- write into the workbooks
def replace_rows(path, sheet, new_rows, economies):
    """Replace rows of `economies` coming from central banks (Citation not IMF) in a workbook sheet."""
    old = pd.read_excel(path, sheet_name=sheet)
    cb = old["Economy code"].isin(economies) & ~old["Citation"].astype(str).str.startswith(
        ("International Monetary Fund", "Bank for International"))
    new = pd.DataFrame(new_rows)
    df = pd.concat([old[~cb], new], ignore_index=True).dropna(axis=1, how="all")  # no empty period columns
    per = sorted((c for c in df.columns if re.fullmatch(r"\d{4}(-Q\d)?", str(c))), key=lambda c: (len(c), c))
    df = df[[c for c in df.columns if c not in per] + per]
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as xw:
        df.to_excel(xw, sheet_name=sheet, index=False)
    print(f"{path.name}/{sheet}: {len(new)} rows for {economies}", file=sys.stderr)


def write_loan_amounts(path):
    """Sheet Loan_amounts: loans by sector in amounts (for growth rates) - IMF FSI balance sheets
    (FSIBSIS) for all countries plus the central bank tables (Kuwait, Saudi Arabia, Oman)."""
    rows = list(AMOUNTS)
    try:
        d = b.fd.loan_portfolio("all", amounts=True)
        names = b.cd.country_names()
        w = d.pivot_table(index=["country", "code", "name"], columns="period", values="value").reset_index()
        per = sorted(c for c in w.columns if "-Q" in str(c))
        for _, r in w.iterrows():
            rows.append({"Economy code": r["country"], "Economy": names.get(r["country"], r["country"]),
                         "Type": "Country", "Indicator code": r["code"], "Indicator": r["name"],
                         "Unit": "Domestic currency (as reported)",
                         "Citation": "International Monetary Fund, Financial Soundness Indicators, balance sheet "
                                     "data of deposit takers (dataset IMF.STA:FSIBSIS)",
                         "Source link": "https://data.imf.org", **r[per].dropna().to_dict()})
    except Exception as e:  # IMF API down: keep the central bank amounts
        print(f"IMF FSIBSIS amounts not available ({e}); central bank amounts only", file=sys.stderr)
    df = pd.DataFrame(rows)
    per = sorted((c for c in df.columns if re.fullmatch(r"\d{4}-Q\d", str(c))))
    df = df[[c for c in df.columns if c not in per] + per]
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as xw:
        df.to_excel(xw, sheet_name="Loan_amounts", index=False)
    print(f"{path.name}/Loan_amounts: {df['Economy code'].nunique()} economies, {len(df)} rows", file=sys.stderr)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--cbb", help="CBB statistical bulletin .xlsx (default: download latest)")
    a.add_argument("--sama", help="SAMA Monthly Bulletin .xlsx (default: download latest)")
    args = a.parse_args()
    t0 = time.time()
    om_lp, om_fsi = oman()
    lp = kuwait() + saudi_sama(sama_file(args.sama)) + om_lp
    f = cbb_file(args.cbb)
    edition = re.sub(r"-\d$", "", f.stem)  # "Jul-2026-1" -> "Jul-2026"
    wb = load_workbook(f, read_only=True, data_only=True)
    replace_rows(HERE / b.FSI_FILE, "Loan_portfolio", lp, ["KWT", "SAU", "OMN"])
    write_loan_amounts(HERE / b.FSI_FILE)
    replace_rows(HERE / b.FSI_FILE, "FSI_Quarterly", bahrain_fsi(wb, edition) + om_fsi, ["BHR", "OMN"])
    replace_rows(HERE / b.BANK_FILE, "Banking", bahrain_assets(wb, edition), ["BHR"])
    print(f"done in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
