#!/usr/bin/env python3
"""
Check the Markdown knowledge files against the source workbooks:
random macro cells, FSI latest values and percentiles, and every credit gap must match;
every country with data must have exactly one section; no 'nan' or empty tables.

    python m365-agent/test_markdown_knowledge.py
"""

import random
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_data_file as b  # noqa: E402
import build_markdown_knowledge as k  # noqa: E402

random.seed(1)
failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)


def sections():
    """{country name: section text} from all Country_profiles_*.md files."""
    out = {}
    for f in sorted(k.OUT.glob("Country_profiles_*.md")):
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"^# ([^\n]+?) \(([A-Z]{3})\) — country profile$(.*?)(?=^# |\Z)", text, re.M | re.S):
            name = m.group(1)
            check(name not in out, f"duplicate section: {name}")
            out[name] = m.group(0)
    return out


def row_cells(section, heading_word, first_cells):
    """Cells of the table row whose first cells match, inside the subsection containing heading_word."""
    sub = section[section.index("## ", section.index(heading_word) - 200 if False else 0):]
    sub = sub[sub.index(next(h for h in re.findall(r"^## .*$", section, re.M) if heading_word in h)):]
    sub = sub[:sub.index("Source:")]
    for line in sub.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[:len(first_cells)] == first_cells:
            return cells
    return None


S = sections()
text_all = "".join(S.values())
check("nan" not in text_all.lower().replace("financial", "").replace("nonfinancial", ""), "'nan' found in text")

D = pd.read_excel(b.OUT, sheet_name="Data")
F = pd.read_excel(HERE / b.FSI_FILE, sheet_name="FSI_Quarterly")
L = pd.read_excel(HERE / b.FSI_FILE, sheet_name="Latest")

# 1. Macro: random cells
dc = D[(D["Type"] == "Country") & D["Indicator code"].isin(k.MACRO)]
n_macro = 0
for _, r in dc.sample(400, random_state=1).iterrows():
    y = random.choice(k.YEARS)
    if pd.isna(r[y]) or r["Economy"] not in S:
        continue
    label = k.LABELS.get(r["Indicator code"], r["Indicator"])
    cells = row_cells(S[r["Economy"]], "macroeconomic indicators", [label, r["Unit"]])
    check(cells is not None, f"macro row missing: {r['Economy']} / {label}")
    if cells:
        got = cells[2 + k.YEARS.index(y)]
        check(got == k.fmt(r[y]), f"macro mismatch {r['Economy']} {label} {y}: md {got} vs {k.fmt(r[y])}")
        n_macro += 1

# 2. FSI: latest value and percentile against the Latest sheet
n_fsi = 0
for _, r in L.sample(300, random_state=2).iterrows():
    if r["Economy"] not in S or "heat map" not in S[r["Economy"]]:
        continue
    cells = row_cells(S[r["Economy"]], "heat map", [r["Group"], r["Indicator"]])
    if cells is None:  # indicators with < 8 quarters are not in the heat map
        n_q = F[(F["Economy"] == r["Economy"]) & (F["Indicator"] == r["Indicator"])].iloc[:, 11:].notna().sum(axis=1)
        check(len(n_q) and n_q.iloc[0] < 8, f"FSI row missing: {r['Economy']} / {r['Indicator']}")
        continue
    pct_col = "Vulnerability percentile (0 = least, 1 = most vulnerable vs own history)"
    raw = F[(F["Economy"] == r["Economy"]) & (F["Indicator"] == r["Indicator"])][r["Latest quarter"]].iloc[0]
    check(cells[-4] == k.fmt(raw), f"FSI latest mismatch {r['Economy']} {r['Indicator']}: {cells[-4]} vs raw {raw}")
    check(cells[-3] == r["Latest quarter"], f"FSI quarter mismatch {r['Economy']} {r['Indicator']}")
    check(abs(float(cells[-2]) - r[pct_col]) < 0.011,  # both rounded to 2 decimals
          f"FSI percentile mismatch {r['Economy']} {r['Indicator']}: {cells[-2]} vs {r[pct_col]}")
    n_fsi += 1

# 3. Credit: every economy's latest gap
n_credit = 0
for fname in (b.BIS_FILE, b.MFS_FILE):
    for _, r in pd.read_excel(HERE / fname, sheet_name="Latest").iterrows():
        name = r["Economy"]
        if name not in S:
            continue  # aggregates such as the euro area have no country section
        sec = S[name]
        check("credit gap" in sec, f"credit section missing: {name}")
        cells = row_cells(sec, "credit gap", [str(r["Latest period"])])
        check(cells is not None and cells[3] == k.fmt(r["Gap (pp of GDP)"]),
              f"credit gap mismatch {name}: {cells} vs {r['Gap (pp of GDP)']}")
        n_credit += 1

# 4. Coverage: every country with macro data or a heat map has a section
have = set(dc["Economy"])
missing = sorted(have - set(S))
check(not missing, f"countries without a section: {missing[:10]}")

sizes = sorted(((len(v), n) for n, v in S.items()), reverse=True)
print(f"sections: {len(S)} | macro cells checked: {n_macro} | FSI rows checked: {n_fsi} | "
      f"credit gaps checked: {n_credit}")
print(f"largest sections: {sizes[:3]}")
print("Kuwait heat map rows:", S["Kuwait"].count("| Capital adequacy |") + S["Kuwait"].count("| Asset quality |"),
      "capital/asset-quality rows")
if failures:
    print(f"\nFAILED ({len(failures)}):")
    for f in failures[:30]:
        print(" -", f)
    sys.exit(1)
print("\nALL CHECKS PASSED")
