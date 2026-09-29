#!/usr/bin/env python3
"""
Build Markdown knowledge files for the Microsoft 365 Copilot agent WITHOUT Code interpreter.

Copilot agents without Python find answers by searching their knowledge files. Large
spreadsheets search poorly, so this writes the same data as short, self-contained Markdown
sections: one file per IMF region with one section per country (macro table, FSI heat map,
credit-to-GDP gap), plus world/regional aggregates and the FSAP report list. Every table
carries its source line, and every number is copied from the workbooks built by
build_data_file.py (run that first).

    python m365-agent/build_markdown_knowledge.py

Output: m365-agent/knowledge_md/*.md, knowledge_md.zip and knowledge_txt.zip (same files as .txt)
"""

import re
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "knowledge_md"
sys.path.insert(0, str(HERE))
import build_data_file as b  # noqa: E402  (file names, groups, sparkline, percentiles)

REGIONS = {"AFR": "Africa", "APD": "Asia and Pacific", "EUR": "Europe",
           "MCD": "Middle East and Central Asia", "WHD": "Western Hemisphere"}
MACRO = ["NGDP_RPCH", "NGDPD", "NGDPDPC", "PPPPC", "PCPIPCH", "LUR", "LP", "BCA_NGDPD",
         "GGXCNL_NGDP", "GGXWDG_NGDP", "GGR_G01_GDP_PT", "G_X_G01_GDP_PT"]
LABELS = {"PPPPC": "GDP per capita, PPP", "GGR_G01_GDP_PT": "Government revenue",
          "G_X_G01_GDP_PT": "Government expenditure"}  # clearer names for search
YEARS = [str(y) for y in range(2019, 2032)]
FSI_QUARTERS, CREDIT_PERIODS = 8, 12
LEGEND = ("Colour = percent rank of each quarter in the country's own history (Excel PERCENTRANK.INC), "
          "oriented by vulnerability: \U0001F7E6 least vulnerable (0-0.2), \U0001F7E9 0.2-0.4, "
          "\U0001F7E8 0.4-0.6, \U0001F7E7 0.6-0.8, \U0001F7E5 most vulnerable (0.8-1).")


def md_table(header, rows):
    esc = lambda x: "" if x is None or (isinstance(x, float) and pd.isna(x)) else str(x).replace("|", "/")
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(esc(x) for x in r) + " |" for r in rows]
    return "\n".join(lines)


def fmt(x, nd=1):
    x = pd.to_numeric(x, errors="coerce")
    if pd.isna(x):
        return ""
    return f"{x:,.{nd}f}" if abs(x) >= 1000 else f"{x:.{nd}f}"


def macro_section(name, rows, first_proj):
    rows = rows.set_index("Indicator code")
    body = [[LABELS.get(c, rows.at[c, "Indicator"]), rows.at[c, "Unit"]] + [fmt(rows.at[c, y]) for y in YEARS]
            + [rows.at[c, "Mini chart 2010-2031"]] for c in MACRO if c in rows.index]
    if not body:
        return ""
    code = rows["Economy code"].iloc[0]
    return (f"## {name} — macroeconomic indicators (IMF World Economic Outlook)\n\n"
            f"{name}: annual data 2019-2031. Values from {first_proj} onward are IMF projections. "
            f"Mini chart = trend 2010-2031 (low ▁ to high █).\n\n"
            + md_table(["Indicator", "Unit"] + YEARS + ["Mini chart 2010-2031"], body)
            + f"\n\nSource: {rows['Citation'].iloc[0]}. {name} profile: "
              f"https://www.imf.org/external/datamapper/profile/{code}\n")


def fsi_section(name, g, per):
    cols = [c for c in per if g[c].notna().any()][-FSI_QUARTERS:]
    body = []
    for _, r in g.iterrows():
        v, pct = b.vulnerability_percentiles(r, per)
        if pct is None:
            continue
        sq = lambda c: next(s for lim, s in b.HEAT_SQUARES if pct[c] < lim) if c in pct else ""
        last12 = v.iloc[-12:]
        body.append([r["Group"], r["Indicator"]] + [f"{sq(c)} {fmt(v[c])}" if c in v else "" for c in cols]
                    + [b.sparkline(last12), fmt(v.iloc[-1]), v.index[-1], f"{pct.iloc[-1]:.2f}",
                       r["More vulnerable when"]])
    if not body:
        return ""
    return (f"## {name} — financial soundness indicators heat map (IMF FSI)\n\n"
            f"{name}: banking-sector Financial Soundness Indicators, percent, last {len(cols)} quarters. "
            f"{LEGEND} Mini chart = last 12 quarters (low ▁ to high █).\n\n"
            + md_table(["Group", "Indicator"] + cols + ["Mini chart (12 quarters)", "Latest value",
                                                       "Latest quarter", "Vulnerability percentile",
                                                       "More vulnerable when"], body)
            + f"\n\nSource: {b.FSI_CITATION}. https://data.imf.org\n")


def credit_section(name, g, source_file):
    g = g.set_index("Indicator code")
    per = [c for c in g.columns if re.fullmatch(r"\d{4}(-Q\d)?", str(c))]
    gap = pd.to_numeric(g.loc["CREDIT_GDP_GAP", per], errors="coerce").dropna()
    if gap.empty:
        return ""
    show = list(gap.index[-CREDIT_PERIODS:])
    body = [[p, fmt(g.at["CREDIT_GDP", p]), fmt(g.at["CREDIT_GDP_TREND", p]), fmt(gap[p])] for p in show]
    return (f"## {name} — credit-to-GDP ratio, Hodrick-Prescott trend and credit gap\n\n"
            f"{name}: {g['Method'].iloc[0]}. Gap = ratio minus trend, percentage points of GDP. "
            f"Basel III countercyclical buffer guide: gap above 2 pp may signal a buffer build-up; "
            f"above 10 pp the maximum buffer. Gap mini chart ({show[0]} to {show[-1]}): "
            f"{b.sparkline(gap[show])} (min {gap[show].min():.1f}, max {gap[show].max():.1f}).\n\n"
            + md_table(["Period", "Credit-to-GDP ratio (% of GDP)", "HP trend (% of GDP)", "Gap (pp)"], body)
            + f"\n\nSource: {g['Citation'].iloc[0]}. {g['Source link'].iloc[0]}\n")


def main():
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.md"):
        old.unlink()
    built = time.strftime("%Y-%m-%d")
    D = pd.read_excel(b.OUT, sheet_name="Data")
    G = pd.read_excel(b.OUT, sheet_name="Groups")
    F = pd.read_excel(HERE / b.FSI_FILE, sheet_name="FSI_Quarterly")
    CQ = pd.read_excel(HERE / b.BIS_FILE, sheet_name="Credit_GDP_Quarterly")
    M = pd.read_excel(HERE / b.MFS_FILE, sheet_name="Credit_GDP_Annual")
    cat = pd.read_excel(HERE / b.FSAP_FILE, sheet_name="Reports")
    first_proj = int(D["First projection year"].iloc[0])
    per = [c for c in F.columns if re.fullmatch(r"\d{4}-Q\d", str(c))]
    gt = b.cd._groups_table(); region = dict(zip(gt["countrycode"], gt["department"]))
    groups = dict(zip(G["Economy code"], G["All groups"].fillna("")))

    countries = D[D["Type"] == "Country"][["Economy code", "Economy"]].drop_duplicates("Economy code")
    extra = F[~F["Economy code"].isin(countries["Economy code"])][["Economy code", "Economy"]]
    countries = pd.concat([countries, extra.drop_duplicates("Economy code")]).sort_values("Economy")
    countries = countries[countries["Economy code"].str.fullmatch(r"[A-Z]{3}")
                          & (countries["Economy"] != countries["Economy code"])]  # drop internal codes
    files, sections = {}, 0
    for code, name in countries.itertuples(index=False):
        parts = [macro_section(name, D[(D["Economy code"] == code)], first_proj),
                 fsi_section(name, F[F["Economy code"] == code], per)]
        cq = CQ[CQ["Economy code"] == code]
        mm = M[M["Economy code"] == code]
        if len(mm):
            parts.append(credit_section(name, mm, b.MFS_FILE))
        elif len(cq):
            parts.append(credit_section(name, cq, b.BIS_FILE))
        parts = [p for p in parts if p]
        if not parts:
            continue
        reg = REGIONS.get(region.get(code), "Other economies")
        covered = ["macroeconomic indicators" if "macroeconomic" in "".join(parts) else None,
                   "financial soundness heat map" if "heat map" in "".join(parts) else None,
                   "credit-to-GDP gap" if "credit gap" in "".join(parts) else None]
        head = (f"# {name} ({code}) — country profile\n\n{name}. ISO3 code {code}. IMF region: {reg}. "
                f"Groups: {groups.get(code) or 'none listed'}. Contents: "
                f"{', '.join(c for c in covered if c)}. Data built {built}.\n")
        files.setdefault(reg, []).append("\n".join([head] + parts))
        sections += 1

    written = []
    for reg, secs in files.items():
        fname = f"Country_profiles_{reg.replace(' ', '_')}.md"
        intro = (f"# Country profiles — {reg}\n\nIMF World Economic Outlook, IMF Financial Soundness "
                 f"Indicators and credit-to-GDP gaps (BIS, or IMF Monetary and Financial Statistics for "
                 f"Kuwait, UAE, Qatar and Oman) for {len(secs)} economies in {reg}. Each country has its own "
                 f"section below. Built {built} from github.com/Aknarik/country-data.\n")
        (OUT / fname).write_text("\n\n".join([intro] + secs) + "\n", encoding="utf-8")
        written.append(fname)

    # World and regional aggregates (WEO)
    agg = D[D["Type"] == "Aggregate"]
    secs = [macro_section(n, agg[agg["Economy"] == n], first_proj) for n in sorted(agg["Economy"].unique())]
    (OUT / "World_and_regional_aggregates.md").write_text(
        "# World and regional aggregates — IMF World Economic Outlook\n\nGroup totals (World, "
        "Advanced economies, Euro area, Emerging market and developing economies, regions...). "
        f"Built {built}.\n\n" + "\n\n".join(s.replace("## ", "## Aggregate: ") for s in secs if s) + "\n",
        encoding="utf-8")
    written.append("World_and_regional_aggregates.md")

    # FSAP reports catalog
    rows = [[r["Country"], r["Assessment year"], r["Publication year"], r["Document type"],
             r["Topics"] if isinstance(r["Topics"], str) else "", r["Document title"], r["PDF link"],
             r["eLibrary link"]] for _, r in cat.iterrows()]
    (OUT / "IMF_FSAP_reports_catalog.md").write_text(
        "# IMF Financial Sector Assessment Program (FSAP) reports — GCC countries\n\n"
        "FSSA = Financial System Stability Assessment (main findings, stress tests, recommendations). "
        "DAR = Detailed Assessment Report on one standard: BCP = Basel Core Principles (banking "
        "supervision), IOSCO = securities regulation, FMI = payment systems / market infrastructures, "
        "AML = anti-money laundering and combating the financing of terrorism.\n\n"
        + md_table(["Country", "Assessment year", "Publication year", "Type", "Topics", "Title",
                    "PDF link", "eLibrary link"], rows) + "\n", encoding="utf-8")
    written.append("IMF_FSAP_reports_catalog.md")

    with zipfile.ZipFile(HERE / "knowledge_md.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in written:
            z.write(OUT / f, f)
    # Same files as .txt, for Copilot versions that do not accept .md uploads
    with zipfile.ZipFile(HERE / "knowledge_txt.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in written:
            z.write(OUT / f, f.replace(".md", ".txt"))
    for f in written:
        print(f"{f}: {(OUT / f).stat().st_size / 1e3:,.0f} KB", file=sys.stderr)
    print(f"{sections} country sections -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
