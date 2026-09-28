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

The FSI / BIS downloads and the HP filter live in
.github/skills/country-data/scripts/financial_data.py.

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


FSI_SECTORS = {"S12CFSI": "Deposit takers", "REM": "Real estate markets"}
FSI_CITATION = ("International Monetary Fund, Financial Soundness Indicators (FSI) database "
                "(dataset IMF.STA:FSIC)")
BIS_CITATION = "Bank for International Settlements, credit-to-GDP statistics (dataset WS_CREDIT_GAP)"
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
        "Indicator": wide["indicator"].map(fd.CORE_FSI),
        "Unit": "Percent",
        "Citation": FSI_CITATION,
        "Source link": "https://data.imf.org",
    })
    out = pd.concat([out, wide[[c for c in wide.columns if "-Q" in str(c)]]], axis=1)
    print(f"  FSI: {len(out):,} rows, {out['Economy code'].nunique()} economies", file=sys.stderr)
    return out.sort_values(["Economy", "Indicator"])


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
    groups["All groups"] = [", ".join(s for s in MAIN_GROUPS if row[s] == "Yes")
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
            "Units: 'Annual percent change' = growth rate in %; 'Percent of GDP' = ratio to GDP in %; "
            "GDP in billions of US dollars; population in millions.",
            refresh],
        "Data": data, "Groups": groups, "Indicators": indicators})

    # 2. IMF Financial Soundness Indicators (quarterly)
    fsi = fsi_sheet(countries)
    fsi_ind = pd.DataFrame([{"Indicator code": k, "Indicator": v, "Unit": "Percent",
                             "Sector": "Real estate markets" if k == "FSI524_CFSI_PT" else "Deposit takers",
                             "Source": FSI_CITATION} for k, v in fd.CORE_FSI.items()])
    write_book(HERE / FSI_FILE, {
        "README": [
            "IMF Financial Soundness Indicators (FSI) - core indicators, quarterly",
            f"Built on {built} from the public IMF SDMX API (api.imf.org), dataset IMF.STA:FSIC.",
            "Sheet 'FSI_Quarterly': one row per economy and indicator; one column per quarter "
            "(e.g. '2024-Q4'). Blank = not reported. All values in percent.",
            "Covers capital adequacy (regulatory capital, Tier 1, CET1 to risk-weighted assets), asset "
            "quality (NPLs to gross loans, provisions), earnings (ROA, ROE), liquidity (liquid assets, "
            "LCR, NSFR) and FX exposure of deposit takers.",
            "Cite the 'Citation' column (the IMF FSI database), not this workbook.",
            refresh],
        "FSI_Quarterly": fsi, "Indicators": fsi_ind})

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
            "Cite the 'Citation' column (BIS; trend and gap are own calculations), not this workbook.",
            refresh],
        "Credit_GDP_Quarterly": credit_q, "Credit_GDP_Annual": credit_a})


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

if __name__ == "__main__":
    main()
