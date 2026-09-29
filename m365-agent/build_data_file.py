#!/usr/bin/env python3
"""
Build the knowledge file for the Microsoft 365 Copilot "Country Data" agent.

Writes three Excel workbooks, each named after its source (Microsoft 365 Copilot shows
the file name in its references), for the agent's Code interpreter to read and plot:

  IMF_World_Economic_Outlook_data.xlsx
      Data        WEO/Fiscal Monitor: economy x indicator rows, one column per year
      Groups      country membership of G7, G20, euro area, advanced economies...
      Indicators  code, name, unit, source, definition
  IMF_Financial_Soundness_Indicators.xlsx
      FSI_Quarterly   IMF core Financial Soundness Indicators, one column per quarter
  BIS_credit_to_GDP.xlsx
      Credit_GDP_Quarterly  BIS credit-to-GDP ratio + one-sided HP trend (lambda 400,000) + gap
      Credit_GDP_Annual     same on calendar-year averages, lambda 100,000
  IMF_MFS_credit_to_GDP.xlsx
      Credit_GDP_Annual     Gulf countries not covered by BIS (Kuwait, UAE, Qatar, Oman):
                            IMF MFS credit / WEO nominal GDP + one-sided HP trend (100,000) + gap

The FSI / BIS downloads and the HP filter live in
.github/skills/country-data/scripts/financial_data.py.

It also writes Agent_tools.xlsx: the agent's Python code (agent_tools.py), one line per row.
After changing only agent_tools.py:  python m365-agent/build_data_file.py --tools-only

Refresh after each WEO release (April and October), or any time for new FSI/BIS quarters:
  python m365-agent/build_data_file.py
then re-upload the .xlsx to the agent's knowledge.
"""

import re
import sys
import time
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / ".github" / "skills" / "country-data" / "scripts"))
import country_data as cd  # noqa: E402
import financial_data as fd  # noqa: E402

# Named after the source: Microsoft 365 Copilot shows the file name in its reference list.
OUT = HERE / "IMF_World_Economic_Outlook_data.xlsx"
FSI_FILE = "IMF_Financial_Soundness_Indicators.xlsx"
BIS_FILE = "BIS_credit_to_GDP.xlsx"
MFS_FILE = "IMF_MFS_credit_to_GDP.xlsx"
GCC = ["BHR", "KWT", "OMN", "QAT", "SAU", "ARE"]
SOURCES = ("World Economic Outlook", "Fiscal Monitor")
# Groups exposed as Yes/blank columns (short name -> WEO group column in country_group.csv)
MAIN_GROUPS = {
    "G7": "G7", "G20": "G20", "Advanced economies": "AE", "Emerging markets": "EM",
    "Emerging and developing economies": "EMDE", "Low-income developing countries": "LIDC",
    "Euro area": "EA", "European Union": "European Union (EU)", "ASEAN-5": "ASEAN-5",
    "Sub-Saharan Africa": "SSA", "Latin America and the Caribbean": "LAC",
    "Middle East and Central Asia": "Middle East and Central Asia",
    "Middle East and North Africa": "MENA",
    "Emerging and developing Asia": "Emerging and Developing Asia",
    "Emerging and developing Europe": "Emerging and Developing Europe",
    "Advanced Asia": "Advanced Asia", "Advanced Europe": "Advanced Europe",
    "North America": "North America", "Fuel exporters": "EMDEs by Source of Export Earnings: Fuel",
}


FSI_SECTORS = {"S12CFSI": "Deposit takers", "REM": "Real estate markets", "S14": "Households",
               "S1M": "Households", "S11": "Nonfinancial corporations"}
FSAP_FILE = "IMF_FSAP_reports_catalog.xlsx"
FSI_CITATION = ("International Monetary Fund, Financial Soundness Indicators (FSI) database "
                "(dataset IMF.STA:FSIC)")
BIS_CITATION = "Bank for International Settlements, credit-to-GDP statistics (dataset WS_CREDIT_GAP)"
MFS_CITATION = ("International Monetary Fund, Monetary and Financial Statistics (dataset IMF.STA:MFS_DC; "
                "depository corporations' claims on other sectors less claims on public non-financial "
                "corporations) and World Economic Outlook (nominal GDP)")
CREDIT_SERIES = {  # column in financial_data output -> (code, name, unit)
    "ratio": ("CREDIT_GDP", "Credit to the private non-financial sector, % of GDP", "Percent of GDP"),
    "trend": ("CREDIT_GDP_TREND", "Credit-to-GDP trend (one-sided HP filter)", "Percent of GDP"),
    "gap": ("CREDIT_GDP_GAP", "Credit-to-GDP gap (ratio minus trend)", "Percentage points of GDP"),
}


def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def fsi_sheet(names):
    """Core FSIs, all countries, quarterly: one row per economy x indicator."""
    raw = fd.fetch_fsi("all", freq="Q")
    wide = raw.pivot_table(index=["country", "sector", "indicator"], columns="period",
                           values="value", aggfunc="first")
    wide = wide[sorted(wide.columns)].reset_index()
    out = pd.DataFrame({
        "Economy code": wide["country"],
        "Economy": wide["country"].map(names).fillna(wide["country"]),
        "Type": "Country",
        "Sector": wide["sector"].map(FSI_SECTORS).fillna(wide["sector"]),
        "Indicator code": wide["indicator"],
        "Indicator": wide["indicator"].map(fd.FSI_NAMES),
        "Group": wide["indicator"].map(lambda c: fd.FSI_SERIES[c][1]),
        "More vulnerable when": wide["indicator"].map(lambda c: "higher" if fd.FSI_SERIES[c][2] else "lower"),
        "Unit": "Percent",
        "Citation": FSI_CITATION,
        "Source link": "https://data.imf.org",
    })
    out = pd.concat([out, wide[[c for c in wide.columns if "-Q" in str(c)]]], axis=1)
    print(f"  FSI: {len(out):,} rows, {out['Economy code'].nunique()} economies", file=sys.stderr)
    order = {c: i for i, c in enumerate(fd.FSI_SERIES)}
    return out.assign(_o=out["Indicator code"].map(order)).sort_values(["Economy", "_o"]).drop(columns="_o")


def mfs_sheet():
    """Gulf credit-to-GDP from IMF MFS / WEO GDP, annual, one-sided HP (lambda 100,000)."""
    lamb = fd.LAMBDA["A"]
    df = fd.mfs_credit_to_gdp_with_gap(fd.GULF_MFS)
    method = (f"Credit = claims on other sectors minus claims on public non-financial corporations "
              f"(end of year); ratio = credit / nominal GDP x 100; trend: one-sided HP filter, "
              f"lambda = {lamb:,}, from 10 years after the series start")
    rows = []
    for cty, g in df.groupby("country"):
        g = g.set_index("period")
        for col, (code, name, unit) in CREDIT_SERIES.items():
            name = name.replace("Credit to the private non-financial sector",
                                "Credit to the non-government sector (excl. public corporations)")
            rows.append({"Economy code": cty, "Economy": fd.GULF_NAMES.get(cty, cty), "Type": "Country",
                         "Indicator code": code, "Indicator": name, "Unit": unit, "Method": method,
                         "Citation": MFS_CITATION + ("" if col == "ratio" else
                                                     f"; {col}: own calculation, one-sided HP filter "
                                                     f"(lambda {lamb:,})"),
                         "Source link": "https://data.imf.org", **g[col].round(4).to_dict()})
    out = pd.DataFrame(rows)
    periods = sorted(c for c in out.columns if re.fullmatch(r"\d{4}", str(c)))
    print(f"  MFS credit: {out['Economy code'].nunique()} economies", file=sys.stderr)
    return out[[c for c in out.columns if c not in periods] + periods]


GCC_KEY_WEO = ["NGDP_RPCH", "PCPIPCH", "NGDPD", "NGDPDPC", "GGXCNL_NGDP", "GGXWDG_NGDP",
               "BCA_NGDPD", "LUR", "LP"]


def weo_gcc_summary(data):
    """Key WEO indicators for GCC countries, 2019 to the last projection year (readable without Python)."""
    yrs = [c for c in data.columns if c.isdigit() and int(c) >= 2019]
    s = data[data["Economy code"].isin(GCC) & data["Indicator code"].isin(GCC_KEY_WEO)]
    s = s.assign(_o=s["Indicator code"].map({c: i for i, c in enumerate(GCC_KEY_WEO)}))
    s = s.sort_values(["Economy", "_o"])
    return s[["Economy", "Indicator", "Unit", "First projection year"] + yrs].round(1)


def fsi_latest(fsi):
    """Per economy and FSI: latest quarter, value, value a year earlier, and vulnerability percentile
    (percent rank in own history, Excel PERCENTRANK.INC, flipped where lower = more vulnerable)."""
    per = [c for c in fsi.columns if re.fullmatch(r"\d{4}-Q\d", str(c))]
    out = []
    for _, r in fsi.iterrows():
        v = pd.to_numeric(r[per], errors="coerce").dropna()
        if len(v) < 2:
            continue
        pr = (v.rank(method="min") - 1) / (len(v) - 1)
        pct = pr.iloc[-1] if r["More vulnerable when"] == "higher" else 1 - pr.iloc[-1]
        last = v.index[-1]
        year_ago = f"{int(last[:4]) - 1}{last[4:]}"
        out.append({"Economy": r["Economy"], "Group": r["Group"], "Indicator": r["Indicator"],
                    "More vulnerable when": r["More vulnerable when"], "Latest quarter": last,
                    "Latest value": round(v.iloc[-1], 2),
                    "Value a year earlier": round(v[year_ago], 2) if year_ago in v else None,
                    "Vulnerability percentile (0 = least, 1 = most vulnerable vs own history)": round(pct, 2),
                    "History from": v.index[0]})
    return pd.DataFrame(out)


HEAT_SQUARES = [(0.2, "\U0001F7E6"), (0.4, "\U0001F7E9"), (0.6, "\U0001F7E8"), (0.8, "\U0001F7E7"), (1.01, "\U0001F7E5")]
HEAT_LEGEND = ("\U0001F7E6 least vulnerable (0-0.2), \U0001F7E9 0.2-0.4, \U0001F7E8 0.4-0.6, "
               "\U0001F7E7 0.6-0.8, \U0001F7E5 most vulnerable (0.8-1) - percent rank vs own history")
HEAT_FILE = "IMF_FSI_heatmaps.xlsx"


def vulnerability_percentiles(row, per):
    """Percent rank of every quarter in the row's own history (Excel PERCENTRANK.INC),
    flipped where a lower value means more vulnerability. Returns (values, percentiles)."""
    v = pd.to_numeric(row[per], errors="coerce").dropna()
    if len(v) < 8:
        return v, None
    pr = (v.rank(method="min") - 1) / (len(v) - 1)
    return v, (pr if row["More vulnerable when"] == "higher" else 1 - pr)


def fsi_heat_tables(fsi, economies=None, quarters=8):
    """Text heat map (coloured squares + value) for the last quarters, readable without Python.
    All economies unless `economies` (ISO3 list) is given."""
    per = [c for c in fsi.columns if re.fullmatch(r"\d{4}-Q\d", str(c))]
    rows = fsi if economies is None else fsi[fsi["Economy code"].isin(economies)]
    out = []
    for econ, g in rows.groupby("Economy", sort=True):
        cols = [c for c in per if g[c].notna().any()][-quarters:]
        for _, r in g.iterrows():
            v, pct = vulnerability_percentiles(r, per)
            if pct is None:
                continue
            cells = {c: (f"{next(sq for lim, sq in HEAT_SQUARES if pct[c] < lim)} {v[c]:.1f}" if c in v else "")
                     for c in cols}
            out.append({"Economy": econ, "Group": r["Group"], "Indicator": r["Indicator"], **cells})
    df = pd.DataFrame(out)
    per_cols = sorted(c for c in df.columns if re.fullmatch(r"\d{4}-Q\d", str(c)))
    return df[["Economy", "Group", "Indicator"] + per_cols]


def write_heatmap_workbook(fsi, built, economies=None, quarters=12):
    """Excel heat maps, one sheet per economy (all unless `economies` is given), with cell fills in
    the same colours as the agent's chart (RdBu_r), and an index sheet linking to each country."""
    from matplotlib import colormaps
    from matplotlib.colors import to_hex
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
    from openpyxl.worksheet.hyperlink import Hyperlink
    cmap = colormaps["RdBu_r"]
    per = [c for c in fsi.columns if re.fullmatch(r"\d{4}-Q\d", str(c))]
    wb = Workbook(); info = wb.active; info.title = "README"
    for line in [f"IMF Financial Soundness Indicators - vulnerability heat maps by country - built {built}",
                 "Colour = percent rank of each quarter in the country's own history (Excel PERCENTRANK.INC), "
                 "flipped where a lower value means more vulnerability: dark blue = least vulnerable, "
                 "white = median, dark red = most vulnerable. Cells show the actual values (percent).",
                 FSI_CITATION + ". Groups and directions: see IMF_Financial_Soundness_Indicators.xlsx, sheet Indicators."]:
        info.append([line])
    info.column_dimensions["A"].width = 140
    info.append([]); info.append(["Country index (click to open)", "Latest quarter", "Indicators"])
    for c in info[info.max_row]:
        c.font = Font(bold=True)
    thin = Side(style="thin", color="999999")
    used = set()
    rows_all = fsi if economies is None else fsi[fsi["Economy code"].isin(economies)]
    for econ, g in rows_all.groupby("Economy", sort=True):
        if not any(vulnerability_percentiles(r, per)[1] is not None for _, r in g.iterrows()):
            continue
        cols = [c for c in per if g[c].notna().any()][-quarters:]
        name = re.sub(r"[\[\]:*?/\\']", "", str(econ))[:31]
        while name in used:
            name = name[:29] + str(len(used) % 100)
        used.add(name)
        ws = wb.create_sheet(name)
        ws.append([f"{econ}: financial soundness heat map (percent rank vs own history)"])
        ws["A1"].font = Font(bold=True, color="4B82AD", size=12)
        ws.append(["Group", "Indicator"] + cols)
        for c in ws[2]:
            c.font = Font(bold=True)
        prev = None
        for _, r in g.iterrows():
            v, pct = vulnerability_percentiles(r, per)
            if pct is None:
                continue
            ws.append([r["Group"] if r["Group"] != prev else "", r["Indicator"]] + [v.get(c) for c in cols])
            row = ws.max_row
            if r["Group"] != prev and prev is not None:
                for cell in ws[row]:
                    cell.border = Border(top=Side(style="medium", color="000000"))
            prev = r["Group"]
            ws.cell(row, 1).font = Font(bold=True, color="4B82AD")
            for j, c in enumerate(cols, start=3):
                cell = ws.cell(row, j)
                cell.number_format = "0.0"; cell.alignment = Alignment(horizontal="center")
                if c in pct:
                    rgb = cmap(float(pct[c]))
                    cell.fill = PatternFill("solid", fgColor=to_hex(rgb)[1:].upper())
                    lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
                    cell.font = Font(color="FFFFFF" if lum < 0.45 else "000000")
                cell.border = Border(left=thin, right=thin, top=cell.border.top if cell.border.top.style else thin,
                                     bottom=thin)
        ws.column_dimensions["A"].width = 22; ws.column_dimensions["B"].width = 52
        for j in range(3, 3 + len(cols)):
            ws.column_dimensions[ws.cell(2, j).column_letter].width = 9
        ws.freeze_panes = "C3"
        ws.append([]); ws.append(["Source: " + FSI_CITATION + ". Dark red = most vulnerable vs own history, dark blue = least."])
        ws.append(["Back to index"]); ws.cell(ws.max_row, 1).hyperlink = Hyperlink(
            ref=f"A{ws.max_row}", location="'README'!A1")
        ws.cell(ws.max_row, 1).font = Font(color="0563C1", underline="single")
        info.append([econ, cols[-1], ws.max_row]); link = info.cell(info.max_row, 1)
        link.hyperlink = Hyperlink(ref=link.coordinate, location=f"'{name}'!A1"); link.font = Font(color="0563C1", underline="single")
        info.cell(info.max_row, 3).value = sum(1 for _, r in g.iterrows()
                                               if vulnerability_percentiles(r, per)[1] is not None)
    info.column_dimensions["B"].width = 16
    wb.save(HERE / HEAT_FILE)
    print(f"{HEAT_FILE}: {len(wb.sheetnames) - 1} country sheets", file=sys.stderr)


def credit_latest(sheet):
    """Per economy: latest period, ratio, trend, gap, gap a year earlier, peak gap."""
    per = [c for c in sheet.columns if re.fullmatch(r"\d{4}(-Q\d)?", str(c))]
    out = []
    for econ, g in sheet.groupby("Economy", sort=True):
        g = g.set_index("Indicator code")
        gap = pd.to_numeric(g.loc["CREDIT_GDP_GAP", per], errors="coerce").dropna()
        if gap.empty:
            continue
        last = gap.index[-1]
        year_ago = f"{int(last[:4]) - 1}{last[4:]}"
        out.append({"Economy": econ, "Latest period": last,
                    "Credit-to-GDP ratio (% of GDP)": round(float(g.at["CREDIT_GDP", last]), 1),
                    "HP trend (% of GDP)": round(float(g.at["CREDIT_GDP_TREND", last]), 1),
                    "Gap (pp of GDP)": round(gap.iloc[-1], 1),
                    "Gap a year earlier (pp)": round(gap[year_ago], 1) if year_ago in gap else None,
                    "Largest gap (pp)": round(gap.max(), 1), "Largest gap period": gap.idxmax(),
                    "Method": g["Method"].iloc[0]})
    return pd.DataFrame(out)


def credit_sheet(annual):
    """BIS credit-to-GDP ratio with our one-sided HP trend and gap."""
    lamb = fd.LAMBDA["A" if annual else "Q"]
    df = fd.credit_to_gdp_with_gap("all", annual=annual)
    bis_names, iso3 = fd.bis_country_names(), fd.iso2_to_iso3()
    method = (f"One-sided HP filter, lambda = {lamb:,}; trend from 10 years after the series start"
              + ("; calendar-year averages of quarterly data" if annual else ""))
    rows = []
    for cty, g in df.groupby("country"):
        g = g.set_index("period")
        for col, (code, name, unit) in CREDIT_SERIES.items():
            rows.append({"Economy code": iso3.get(cty, cty), "Economy": bis_names.get(cty, cty),
                         "Type": "Country" if cty in iso3 else "Aggregate",
                         "Indicator code": code, "Indicator": name, "Unit": unit, "Method": method,
                         "Citation": BIS_CITATION + ("" if col == "ratio" else
                                                     f"; {col}: own calculation, one-sided HP filter "
                                                     f"(lambda {lamb:,})"),
                         "Source link": "https://data.bis.org/topics/CREDIT_GAPS",
                         **g[col].round(4).to_dict()})
    out = pd.DataFrame(rows)
    periods = sorted(c for c in out.columns if re.fullmatch(r"\d{4}(-Q\d)?", str(c)))
    out = out[[c for c in out.columns if c not in periods] + periods]
    print(f"  Credit ({'annual' if annual else 'quarterly'}): {out['Economy code'].nunique()} economies",
          file=sys.stderr)
    return out


def main():
    meta = {k: v for k, v in cd.imf_indicators().items()
            if any(s in v["source"] for s in SOURCES)}
    countries = {k: v for k, v in cd.country_names().items()}
    aggregates = cd.imf_aggregates()
    first_proj = cd.THIS_YEAR
    print(f"{len(meta)} indicators", file=sys.stderr)

    rows = []
    for code, m in meta.items():
        values = cd._get_json(f"{cd.IMF_BASE}/{code}").get("values", {}).get(code, {})
        seen_agg = set()
        tag = "FM" if "Fiscal Monitor" in m["source"] else "WEO"
        for econ, series in values.items():
            if econ in aggregates:
                name, kind = aggregates[econ], "Aggregate"
                if name in seen_agg:  # the API has several "World" codes; keep one per indicator
                    continue
                seen_agg.add(name)
            else:
                name, kind = countries.get(econ, econ), "Country"
            link = f"https://www.imf.org/external/datamapper/{code}@{tag}/{econ}"
            econ = "KOS" if econ == "UVK" else econ  # match the Groups sheet code
            rows.append({"Economy code": econ, "Economy": clean(name), "Type": kind,
                         "Indicator code": code, "Indicator": clean(m["label"]),
                         "Unit": clean(m["unit"]), "Source": clean(m["source"]),
                         "Citation": f"International Monetary Fund, {clean(m['source'])}",
                         "Source link": link, "First projection year": first_proj,
                         **{int(y): v for y, v in series.items()}})
        print(f"  {code:<22} {len(values):>4} economies", file=sys.stderr)
        time.sleep(0.3)

    data = pd.DataFrame(rows)
    years = sorted(c for c in data.columns if isinstance(c, int))
    data = data[[c for c in data.columns if not isinstance(c, int)] + years]
    data = data.dropna(subset=years, how="all")
    data = data.sort_values(["Type", "Economy", "Indicator"], ascending=[False, True, True])
    data.columns = [str(c) for c in data.columns]

    # Groups sheet
    g = cd._groups_table()
    groups = pd.DataFrame({"Economy code": g["countrycode"], "Economy": g["countryname_s"]})
    for short, query in MAIN_GROUPS.items():
        members = set(cd.weo_groups()[cd.find_group(query)])
        groups[short] = ["Yes" if c in members else "" for c in groups["Economy code"]]
    groups["GCC"] = ["Yes" if c in GCC else "" for c in groups["Economy code"]]
    groups["All groups"] = [", ".join(s for s in [*MAIN_GROUPS, "GCC"] if row[s] == "Yes")
                            for _, row in groups.iterrows()]

    indicators = pd.DataFrame([{"Indicator code": k, "Indicator": clean(v["label"]),
                                "Unit": clean(v["unit"]), "Source": clean(v["source"]),
                                "Definition": clean(v["description"])} for k, v in meta.items()])
    built = time.strftime("%Y-%m-%d")
    refresh = "To refresh: run m365-agent/build_data_file.py from github.com/Aknarik/country-data and re-upload."

    # 1. IMF World Economic Outlook / Fiscal Monitor (annual)
    write_book(OUT, {
        "README": [
            "IMF World Economic Outlook and Fiscal Monitor - annual country data",
            f"Built on {built} from the public IMF DataMapper API (www.imf.org/external/datamapper).",
            f"Sources: {', '.join(sorted(indicators['Source'].unique()))}.",
            f"Years {years[0]}-{years[-1]}. Values from {first_proj} onward are IMF PROJECTIONS, not actual "
            "data (for some countries the latest actual year is earlier).",
            "Sheet 'Data': one row per economy and indicator; one column per year. Blank = no data.",
            "Cite the 'Citation' and 'Source link' columns of the rows used (the original IMF source), "
            "not this workbook. 'First projection year' = first year that is an IMF projection.",
            "Type 'Country' = single economy; Type 'Aggregate' = IMF group total (World, Euro area, "
            "Advanced economies, Major advanced economies (G7), ...).",
            "Sheet 'Groups': which countries belong to G7, G20, euro area, advanced economies, emerging "
            "markets, etc. (ISO3 codes, also valid for the FSI and BIS files).",
            "Sheet 'Indicators': definitions and units.",
            "Sheet 'GCC_Summary': key indicators for the GCC countries, 2019 onward (readable without Python).",
            "Units: 'Annual percent change' = growth rate in %; 'Percent of GDP' = ratio to GDP in %; "
            "GDP in billions of US dollars; population in millions.",
            refresh],
        "GCC_Summary": weo_gcc_summary(data), "Data": data, "Groups": groups, "Indicators": indicators})

    # 2. IMF Financial Soundness Indicators (quarterly)
    fsi = fsi_sheet(countries)
    fsi_ind = pd.DataFrame([{"Indicator code": k, "Indicator": name, "Group": group,
                             "More vulnerable when": "higher" if up else "lower",
                             "Core or additional FSI": "Core" if "_CFSI_" in k else "Additional",
                             "Unit": "Percent", "Source": FSI_CITATION}
                            for k, (name, group, up) in fd.FSI_SERIES.items()])
    write_book(HERE / FSI_FILE, {
        "README": [
            "IMF Financial Soundness Indicators (FSI) - core and selected additional indicators, quarterly",
            f"Built on {built} from the public IMF SDMX API (api.imf.org), dataset IMF.STA:FSIC.",
            "Sheet 'FSI_Quarterly': one row per economy and indicator; one column per quarter "
            "(e.g. '2024-Q4'). Blank = not reported. All values in percent.",
            "Groups: capital adequacy, asset quality, concentration (sectoral, large exposures, real "
            "estate), earnings, funding and liquidity (incl. customer deposits to loans), FX exposure "
            "(open position, FX loans and liabilities), household sector.",
            "Column 'More vulnerable when' gives the direction from a financial-sector vulnerability "
            "perspective (e.g. NPL ratio: higher; capital ratios and deposits to loans: lower).",
            "Sheet 'Latest': for every economy and indicator, the latest quarter, value, value a year "
            "earlier and vulnerability percentile vs own history (0 = least, 1 = most vulnerable).",
            "Sheet 'Heatmap': text heat map for every economy, last 8 quarters: " + HEAT_LEGEND + ".",
            "Cite the 'Citation' column (the IMF FSI database), not this workbook.",
            refresh],
        "Heatmap": fsi_heat_tables(fsi), "Latest": fsi_latest(fsi), "FSI_Quarterly": fsi,
        "Indicators": fsi_ind})
    write_heatmap_workbook(fsi, built)

    write_fsap_catalog(built)

    # 3. BIS credit-to-GDP with one-sided HP trend and gap
    credit_q, credit_a = credit_sheet(annual=False), credit_sheet(annual=True)
    write_book(HERE / BIS_FILE, {
        "README": [
            "BIS credit-to-GDP ratio, one-sided HP trend and credit-to-GDP gap",
            f"Built on {built} from the public BIS SDMX API (stats.bis.org), dataset WS_CREDIT_GAP.",
            "Ratio: credit to the private non-financial sector from all sectors, % of GDP, adjusted for breaks.",
            "Trend: one-sided Hodrick-Prescott filter (at each quarter the filter uses only data up to that "
            "quarter). Sheet 'Credit_GDP_Quarterly': lambda 400,000. Sheet 'Credit_GDP_Annual': calendar-"
            "year averages (complete years only), lambda 100,000. Trend starts 10 years after the series "
            "starts, as in the BIS statistics; the quarterly trend and gap match BIS's published figures.",
            "Gap = ratio - trend, in percentage points of GDP. Basel III countercyclical buffer guide: "
            "a gap above 2 pp may signal a buffer build-up; above 10 pp the maximum buffer.",
            "Rows: 3 per economy (CREDIT_GDP, CREDIT_GDP_TREND, CREDIT_GDP_GAP); one column per period.",
            "Sheet 'Latest': latest quarterly ratio, trend and gap for each economy.",
            "Cite the 'Citation' column (BIS; trend and gap are own calculations), not this workbook.",
            refresh],
        "Latest": credit_latest(credit_q), "Credit_GDP_Quarterly": credit_q, "Credit_GDP_Annual": credit_a})

    # 4. Gulf credit-to-GDP from IMF MFS (countries BIS does not cover)
    write_book(HERE / MFS_FILE, {
        "README": [
            "Credit-to-GDP ratio, one-sided HP trend and gap for Gulf countries not covered by BIS "
            "(Kuwait, United Arab Emirates, Qatar, Oman). Saudi Arabia: see BIS_credit_to_GDP.xlsx. "
            "Bahrain: no IMF MFS data.",
            f"Built on {built} from the public IMF SDMX API (api.imf.org): dataset IMF.STA:MFS_DC "
            "(depository corporations survey) and IMF.RES:WEO (nominal GDP, domestic currency).",
            "Credit = depository corporations' claims on other sectors minus claims on public non-financial "
            "corporations, end of year, domestic currency. The narrower 'claims on private sector' series "
            "is not used because it has a reclassification break for Kuwait.",
            "Ratio = credit / annual nominal GDP x 100. The latest year's GDP may be an IMF estimate.",
            "Trend: one-sided Hodrick-Prescott filter, lambda 100,000 (annual data), reported from 10 years "
            "after the series start. Gap = ratio - trend, percentage points of GDP.",
            "Oil-price swings move GDP, so the ratio jumps when oil prices fall (e.g. 2009, 2015, 2020).",
            "Sheet 'Latest': latest ratio, trend and gap for each economy.",
            "Cite the 'Citation' column (IMF; trend and gap are own calculations), not this workbook.",
            refresh],
        "Latest": credit_latest(mfs := mfs_sheet()), "Credit_GDP_Annual": mfs})


def write_book(path, sheets):
    """Write {sheet name: DataFrame or list of README lines} with frozen headers and sized columns."""
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in sheets.items():
            if isinstance(df, list):
                df = pd.DataFrame({"About this file": df})
            df.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            ws.freeze_panes = "A2"
            for i, col in enumerate(df.columns, 1):
                width = 110 if name == "README" else min(45, max(8, len(str(col)) + 2,
                                                              int(df[col].astype(str).str.len().quantile(0.9)) + 2))
                ws.column_dimensions[ws.cell(1, i).column_letter].width = width
    rows = {k: len(v) for k, v in sheets.items() if not isinstance(v, list)}
    print(f"{path.name}: {rows}, {path.stat().st_size / 1e6:.1f} MB", file=sys.stderr)

def write_fsap_catalog(built=None):
    """IMF FSAP reports for Gulf countries (fsap_reports.csv) as a knowledge file, with the file
    name each PDF should be saved under so the agent's citations show the report."""
    cat = pd.read_csv(HERE / "fsap_reports.csv")
    kind = cat["Document type"].str.contains("FSSA").map({True: "FSSA", False: "DAR"})
    topic = cat["Topics"].fillna("").str.replace(", ", "-").str.replace(" ", "")
    cat["PDF file name"] = ("IMF_FSAP_" + cat["Country"].str.replace(" ", "_") + "_" + cat["Assessment year"].astype(str)
                            + "_" + kind + [f"_{t}" if t and k == "DAR" else "" for t, k in zip(topic, kind)]
                            + "_" + cat["Publication year"].astype(str) + ".pdf")
    write_book(HERE / FSAP_FILE, {
        "README": [
            "IMF Financial Sector Assessment Program (FSAP) reports for Gulf countries (GCC).",
            f"Catalog built on {built or time.strftime('%Y-%m-%d')} from m365-agent/fsap_reports.csv.",
            "FSSA = Financial System Stability Assessment (main findings, stress tests, recommendations). "
            "DAR = Detailed Assessment Report on a standard: BCP = Basel Core Principles (banking supervision), "
            "IOSCO = securities regulation, FMI = payment systems / market infrastructures, AML = anti-money "
            "laundering and combating the financing of terrorism, Transparency = monetary and financial policy "
            "transparency.",
            "The report texts are PDF knowledge files named as in column 'PDF file name'.",
            "Cite the report (title, year, page), not this catalog."],
        "Reports": cat})


def write_tools():
    """Store agent_tools.py in Agent_tools.xlsx (sheet Code, one line per row) so the agent's
    Code interpreter can load it: exec('\\n'.join(pd.read_excel(f, 'Code')['code'].fillna('')))."""
    lines = (HERE / "agent_tools.py").read_text(encoding="utf-8").splitlines()
    bad = [ln for ln in lines if ln.startswith("=")]
    if bad:
        raise ValueError(f"Lines starting with '=' would become Excel formulas: {bad[:3]}")
    path = HERE / "Agent_tools.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        pd.DataFrame({"code": lines}).to_excel(xw, sheet_name="Code", index=False)
        pd.DataFrame({"About this file": [
            "Python code used by the Country Data Assistant agent (charts, credit-to-GDP gap from "
            "user data, FSI heat map). Not a data source - do not cite it.",
            "Source: m365-agent/agent_tools.py in github.com/Aknarik/country-data."]}).to_excel(
            xw, sheet_name="README", index=False)
    # Also put the code in every workbook: Copilot may pass only some knowledge files to Code
    # interpreter, so the agent finds the code in whichever workbook it has.
    from openpyxl import load_workbook
    books = [path] + [HERE / n for n in (OUT.name, FSI_FILE, BIS_FILE, MFS_FILE, FSAP_FILE)
                      if (HERE / n).exists()]
    for book in books[1:]:
        wb = load_workbook(book)
        if "Code" in wb.sheetnames:
            del wb["Code"]
        ws = wb.create_sheet("Code")
        ws.append(["code"])
        for ln in lines:
            ws.append([ln if ln else None])
        wb.save(book)
    for book in books:
        back = "\n".join(pd.read_excel(book, sheet_name="Code")["code"].fillna(""))
        if back != "\n".join(lines):
            raise ValueError(f"{book.name} does not round-trip the code exactly")
    print(f"Code sheet ({len(lines)} lines) in: {', '.join(b.name for b in books)}", file=sys.stderr)


if __name__ == "__main__":
    if "--tools-only" in sys.argv:
        write_tools()
        write_fsap_catalog()
    else:
        main()
        write_tools()
