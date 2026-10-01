"""Assemble the ready-to-upload package for the four Microsoft 365 Copilot agents.

    python m365-agent/agents/build_package.py

Creates C:/Users/.../country_data/copilot_agents_package/ with one folder per agent:
    INSTRUCTIONS.txt   paste into the agent's Instructions box
    SETUP.txt          name, description, capabilities, starter prompts, test question
    knowledge/         exactly the files to upload to the agent's Knowledge
The package holds the IMF-internal HEAT file, so it is git-ignored: never commit or share it outside the IMF.
Rerun after any data or instruction update, then re-upload what changed.
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
DATA = HERE.parent
OUT = ROOT / "copilot_agents_package"

AGENTS = [
    {"folder": "1_WEO_Economic_Outlook", "source": "1_WEO_outlook",
     "name": "WEO Economic Outlook",
     "description": "IMF World Economic Outlook data and forecasts for any country or country group, with charts, "
                    "tables and dashboards",
     "knowledge": [DATA / "IMF_World_Economic_Outlook_data.xlsx"],
     "code": True,
     "starters": ["Macroeconomic dashboard for a country", "Compare government debt across a country group",
                  "Inflation outlook for a country"],
     "test": "Brazil: inflation",
     "expected": "Chart 'Brazil: Inflation rate, average consumer prices' in IMF blue; projections on a grey band; "
                 "latest value labelled; legend below; source IMF World Economic Outlook (April 2026)."},
    {"folder": "2_Credit_Gap_and_Macroprudential", "source": "2_Credit_gap_macroprudential",
     "name": "Credit Gap & Macroprudential",
     "description": "Credit-to-GDP gaps with the Basel III buffer guide, gaps built from user data, and IMF iMaPP "
                    "macroprudential measures by country and across countries",
     "knowledge": [DATA / "BIS_credit_to_GDP.xlsx", DATA / "IMF_MFS_credit_to_GDP.xlsx",
                   DATA / "IMF_iMaPP_macroprudential.xlsx"],
     "code": True,
     "starters": ["Credit-to-GDP gap for a country", "Compare macroprudential tools across countries",
                  "Build a credit gap from my own data"],
     "test": "United Kingdom credit gap",
     "expected": "Ratio and trend, gap bars with the Basel 2-10 pp band and the shaded start-up decade, buffer "
                 "guide; then the UK macroprudential tools table citing IMF iMaPP (Alam et al., 2019)."},
    {"folder": "3_Financial_Soundness", "source": "3_Financial_soundness",
     "name": "Financial Soundness",
     "description": "Banking-sector soundness for any country: dashboard (capital, asset quality, profitability, "
                    "liquidity, loans, sovereign-bank nexus), FSI heat map and indicator charts",
     "knowledge": [DATA / "IMF_Financial_Soundness_Indicators.xlsx", DATA / "IMF_MFS_banking_sector.xlsx"],
     "code": True,
     "starters": ["Banking sector dashboard for a country", "FSI heat map for a country",
                  "Nonperforming loans in a country"],
     "test": "Iceland FSI heat map, then: Saudi Arabia banking dashboard",
     "expected": "Heat map in sections (capital adequacy, asset quality...) with red = more vulnerable; six-panel "
                 "dashboard without overlapping labels."},
    {"folder": "4_FSAP_Reports", "source": "4_FSAP_reports",
     "name": "FSAP Reports",
     "description": "Answers from IMF FSAP reports for GCC countries, quoting the supporting paragraph with the key "
                    "sentence in bold, plus page and link",
     "knowledge": [DATA / "IMF_FSAP_reports_catalog.xlsx"],
     "website": "https://www.elibrary.imf.org",
     "code": False,
     "starters": ["What did the latest FSAP say about a topic for a country?", "Key recommendations of an FSAP report"],
     "test": "Key recommendations of the 2024 Saudi Arabia FSSA",
     "expected": "Short answer, quoted paragraph with the key sentence in bold, report title, page and link.",
     "note": "If the agent cannot open the reports, download the PDFs from the catalog links and upload them to "
             "Knowledge, or add a SharePoint/OneDrive folder that contains them."},
    {"folder": "5_Banks_and_Balance_Sheets", "source": "5_Banks_balance_sheets",
     "name": "Banks & Balance Sheets (IMF staff)",
     "description": "Bank-by-bank indicators with bank names (IMF HEAT 2.0), banking balance sheet growth, loan "
                    "portfolio and asset structure for any country",
     "knowledge": [DATA / "IMF_Financial_Soundness_Indicators.xlsx", DATA / "IMF_MFS_banking_sector.xlsx",
                   ROOT / "local_data" / "HEAT_bank_distribution.xlsx"],
     "code": True,
     "starters": ["Tier 1 capital by bank in a country", "Bank balance sheet growth for a country",
                  "Loan portfolio structure for a country"],
     "test": "Kuwait Tier 1 capital by bank, then: Brazil bank balance sheet growth",
     "expected": "Bars with bank names and the median bank; growth chart and table for total assets, credit, "
                 "deposits, equity, claims on government, foreign assets.",
     "note": "Contains licensed S&P Capital IQ Pro data (HEAT): share only with IMF colleagues entitled to it."},
]

STEPS = """HOW TO CREATE THIS AGENT
1. Microsoft 365 Copilot > Agents > New agent (Create agent) > Configure tab.
2. Name and Description: copy from above.
3. Instructions: open INSTRUCTIONS.txt in Notepad, Ctrl+A, Ctrl+C, paste into the Instructions box. Paste the
   whole file; do not edit it.
4. Knowledge: Upload files > add every file in the 'knowledge' folder (nothing else). Wait until each is ready.
   If offered, turn on "Only use specified sources".{website}
5. Capabilities: {code}
6. Suggested prompts (optional): add the starter prompts above.
7. Create. Open the agent, start a NEW chat, run the test question and compare with 'Expected'.

UPDATING: new data -> delete the old knowledge file, upload the new one (same name), Update, test in a new chat.
New instructions -> paste the new INSTRUCTIONS.txt over the old text, Update.
"""


def main():
    subprocess.run([sys.executable, str(HERE / "build_agents.py")], check=True)  # fresh INSTRUCTIONS.txt, size check
    if OUT.exists():
        shutil.rmtree(OUT)
    lines = [f"COPILOT AGENTS PACKAGE - built {time.strftime('%Y-%m-%d %H:%M')}", "",
             "One folder per agent. In each: INSTRUCTIONS.txt, SETUP.txt, knowledge/ (files to upload).",
             "All agents work for any country; the user names it in the question.",
             "Folder 5 contains licensed HEAT data: share it only with IMF colleagues entitled to it.", ""]
    for a in AGENTS:
        d = OUT / a["folder"]
        (d / "knowledge").mkdir(parents=True)
        instr = (HERE / a["source"] / "INSTRUCTIONS.txt").read_text(encoding="utf-8")
        (d / "INSTRUCTIONS.txt").write_text(instr, encoding="utf-8", newline="\r\n")
        for f in a["knowledge"]:
            if not f.exists():
                raise FileNotFoundError(f"Missing knowledge file: {f}")
            shutil.copy2(f, d / "knowledge" / f.name)
        n = len(instr.replace("\n", "\r\n"))
        setup = [f"AGENT: {a['name']}", "",
                 f"Name:        {a['name']}",
                 f"Description: {a['description']}",
                 f"Instructions: INSTRUCTIONS.txt ({n:,} characters; limit 8,000)",
                 "Knowledge:   " + ", ".join(f.name for f in a["knowledge"])
                 + (f" + website {a['website']}" if a.get("website") else ""),
                 f"Code interpreter: {'ON' if a['code'] else 'not needed'}",
                 "Starter prompts: " + " | ".join(a["starters"]), "",
                 f"Test question: {a['test']}", f"Expected: {a['expected']}", ""]
        if a.get("note"):
            setup += [f"NOTE: {a['note']}", ""]
        setup.append(STEPS.format(
            website=(f"\n   Also add the website {a['website']} (Add website / Public websites), if offered."
                     if a.get("website") else ""),
            code="turn Code interpreter ON." if a["code"] else "Code interpreter is not needed."))
        (d / "SETUP.txt").write_text("\n".join(setup), encoding="utf-8", newline="\r\n")
        lines.append(f"{a['folder']}: {a['name']} - {len(a['knowledge'])} knowledge file(s), {n:,} characters")
        print(f"{a['folder']:36} {n:5} chars, knowledge: {', '.join(f.name for f in a['knowledge'])}")
    (OUT / "START_HERE.txt").write_text("\n".join(lines + ["", "Create the agents in order 1-5; test each before the next."]),
                                        encoding="utf-8", newline="\r\n")
    print(f"\nPackage: {OUT}")


if __name__ == "__main__":
    main()
