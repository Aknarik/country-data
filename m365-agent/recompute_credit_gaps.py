"""Recompute credit-to-GDP trends and gaps in the existing workbooks, without downloading anything.

Uses the credit-to-GDP ratios already stored in BIS_credit_to_GDP.xlsx and IMF_MFS_credit_to_GDP.xlsx
and the current rules in financial_data.py (one-sided HP filter from the first observation, no gap
for series under 20 years). Useful when the BIS or IMF APIs are down, or after a method change.

    python m365-agent/recompute_credit_gaps.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import build_data_file as bdf  # noqa: E402
fd = bdf.fd


def recompute(df, freq):
    per = [c for c in df.columns if re.fullmatch(r"\d{4}(-Q\d)?", str(c))]
    out = df.copy()
    for code, g in df.groupby("Economy code"):
        idx = g.set_index("Indicator code")
        if "CREDIT_GDP" not in idx.index:
            continue
        ratio = pd.to_numeric(idx.loc["CREDIT_GDP", per], errors="coerce").dropna()
        res = fd.credit_gap(ratio, freq=freq)
        for col, ind in (("trend", "CREDIT_GDP_TREND"), ("gap", "CREDIT_GDP_GAP")):
            row = g.index[g["Indicator code"] == ind]
            out.loc[row, per] = res[col].reindex(per).round(4).values
    return out


def method_text(old):
    return re.sub(r"trend from 10 years after the series start|from 10 years after the series start",
                  "trend from the series start (first 10 years = start-up period); no gap for series under 20 years",
                  str(old))


def readme(lines, freq_note):
    new = []
    for line in lines:
        if "Trend starts 10 years after the series" in line:
            line = ("Trend: one-sided Hodrick-Prescott filter (at each quarter the filter uses only data up to that "
                    "quarter). Sheet 'Credit_GDP_Quarterly': lambda 400,000. Sheet 'Credit_GDP_Annual': calendar-year "
                    "averages (complete years only), lambda 100,000. The filter starts at the first observation and "
                    "the trend is shown from there; the first 10 years are a start-up period (less reliable; BIS does "
                    "not publish them). From year 11 on, the quarterly trend and gap match BIS's published figures "
                    "exactly (checked for Saudi Arabia, UK, US, China, Germany, Turkey). No trend or gap is computed "
                    "for series shorter than 20 years.")
        elif "reported from 10 years" in line:
            line = ("Trend: one-sided Hodrick-Prescott filter, lambda 100,000 (annual data), from the series start; the "
                    "first 10 years are a start-up period (less reliable). Gap = ratio - trend, percentage points of GDP.")
        elif line.startswith("USER-BUILT GAPS"):
            new.extend(bdf.GAP_GUIDANCE[:2])
            continue
        new.append(line)
    return new


def main():
    for name, sheets in ((bdf.BIS_FILE, {"Credit_GDP_Quarterly": "Q", "Credit_GDP_Annual": "A"}),
                         (bdf.MFS_FILE, {"Credit_GDP_Annual": "A"})):
        path = HERE / name
        book = pd.read_excel(path, sheet_name=None)
        out = {}
        for sheet, df in book.items():
            if sheet == "README":
                out[sheet] = readme(df.iloc[:, 0].astype(str).tolist(), sheets)
            elif sheet in sheets:
                df = recompute(df, sheets[sheet])
                if "Method" in df:
                    df["Method"] = df["Method"].map(method_text)
                out[sheet] = df
            else:
                out[sheet] = df
        first = next(iter(sheets))
        if "Latest" in out:
            out["Latest"] = bdf.credit_latest(out[first])
        bdf.write_book(path, out)


if __name__ == "__main__":
    main()
