#!/usr/bin/env python3
"""
Fill GCC gaps in the IMF data with central bank statistics.

Adds to the agent's workbooks (public data):
  Kuwait  - CBK Monthly Monetary Statistical Bulletin, Table 13: sectoral distribution of local
            banks' credit facilities to residents  -> loan portfolio (FSI workbook, Loan_portfolio)
  Saudi   - SAMA bank credit by economic activity (Monthly Statistical Bulletin Table 12d, via the
            KAPSARC open-data portal; ends 2022)     -> loan portfolio
  Bahrain - CBB Statistical Bulletin (Excel):
            Table 37 financial soundness indicators  -> FSI workbook, FSI_Quarterly
            Table 17 retail banks' assets by sector  -> banking workbook: asset structure and
                                                        sovereign-bank nexus
Shares are computed from the published levels. Oman and Qatar publish PDF bulletins only; see
AGENT_SETUP.md.

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


def lp_rows(iso, name, shares, citation, link, prefix):
    """Loan-portfolio rows in the agent's Lp format from a DataFrame (periods x sectors, % of total)."""
    rows = []
    for sector in shares.columns:
        s = shares[sector].dropna().round(2)
        code = f"LOANS_{prefix}_" + re.sub(r"[^A-Z0-9]+", "_", sector.upper()).strip("_")[:30]
        rows.append({"Economy code": iso, "Economy": name, "Type": "Country", "Indicator code": code,
                     "Indicator": sector, "Unit": "Percent of total credit", "Citation": citation,
                     "Source link": link, **s.to_dict()})
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
    return lp_rows("KWT", "Kuwait", shares.T.T, cite, CBK_BULLETIN, "CBK")


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
    links = re.findall(r'href="(https://www\.cbb\.gov\.bh/wp-content/uploads/[^"]+\.xlsx)"', get(CBB_PAGE).text)
    if not links:
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


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--cbb", help="CBB statistical bulletin .xlsx (default: download latest)")
    args = a.parse_args()
    t0 = time.time()
    lp = kuwait() + saudi()
    f = cbb_file(args.cbb)
    edition = re.sub(r"-\d$", "", f.stem)  # "Jul-2026-1" -> "Jul-2026"
    wb = load_workbook(f, read_only=True, data_only=True)
    replace_rows(HERE / b.FSI_FILE, "Loan_portfolio", lp, ["KWT", "SAU"])
    replace_rows(HERE / b.FSI_FILE, "FSI_Quarterly", bahrain_fsi(wb, edition), ["BHR"])
    replace_rows(HERE / b.BANK_FILE, "Banking", bahrain_assets(wb, edition), ["BHR"])
    print(f"done in {time.time() - t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
