#!/usr/bin/env python3
"""
Build the knowledge file for the Microsoft 365 Copilot "Country Data" agent.

Downloads the IMF World Economic Outlook + Fiscal Monitor indicators for every
country and IMF aggregate, and writes one Excel workbook that the agent's
Code interpreter can read and plot:

  Data        one row per economy x indicator, one column per year (wide)
  Groups      country membership of G7, G20, euro area, advanced economies...
  Indicators  code, name, unit, source, definition
  README      what is inside, projections, how to refresh

Refresh after each WEO release (April and October):
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

# Named after the source: Microsoft 365 Copilot shows the file name in its reference list.
OUT = HERE / "IMF_World_Economic_Outlook_data.xlsx"
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


def clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


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

    readme = pd.DataFrame({"About this file": [
        "Country Data - IMF World Economic Outlook and Fiscal Monitor",
        f"Built on {time.strftime('%Y-%m-%d')} from the public IMF DataMapper API (www.imf.org/external/datamapper).",
        f"Sources: {', '.join(sorted(indicators['Source'].unique()))}.",
        f"Years {years[0]}-{years[-1]}. Values from {first_proj} onward are IMF PROJECTIONS, not actual data "
        "(for some countries the latest actual year is earlier).",
        "Sheet 'Data': one row per economy and indicator; one column per year. Blank = no data.",
        "Cite the 'Citation' and 'Source link' columns of the rows used (the original IMF source), "
        "not this workbook. 'First projection year' = first year that is an IMF projection.",
        "Type 'Country' = single economy; Type 'Aggregate' = IMF group total (World, Euro area, "
        "Advanced economies, Major advanced economies (G7), ...).",
        "Sheet 'Groups': which countries belong to G7, G20, euro area, advanced economies, emerging markets, etc. "
        "Use it to pick members of a group; use Type 'Aggregate' rows for the group total.",
        "Sheet 'Indicators': definitions and units.",
        "Units: 'Annual percent change' = growth rate in %; 'Percent of GDP' = ratio to GDP in %; "
        "GDP in billions of US dollars; population in millions.",
        "To refresh: run m365-agent/build_data_file.py from github.com/Aknarik/country-data and re-upload.",
    ]})

    with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
        readme.to_excel(xw, sheet_name="README", index=False)
        data.to_excel(xw, sheet_name="Data", index=False)
        groups.to_excel(xw, sheet_name="Groups", index=False)
        indicators.to_excel(xw, sheet_name="Indicators", index=False)
        for name, df in (("README", readme), ("Data", data), ("Groups", groups), ("Indicators", indicators)):
            ws = xw.sheets[name]
            ws.freeze_panes = "A2"
            for i, col in enumerate(df.columns, 1):
                width = 110 if name == "README" else min(45, max(8, len(str(col)) + 2,
                                                              int(df[col].astype(str).str.len().quantile(0.9)) + 2))
                ws.column_dimensions[ws.cell(1, i).column_letter].width = width

    print(f"\n{OUT}\n  Data: {len(data):,} rows ({data['Economy code'].nunique()} economies, "
          f"{data['Indicator code'].nunique()} indicators, {years[0]}-{years[-1]})"
          f"\n  Size: {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
