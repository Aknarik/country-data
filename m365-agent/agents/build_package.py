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
     "description": "Answers from IMF FSAP reports for GCC countries using only the reports' exact wording: key "
                    "sentences and full paragraphs with paragraph number, report title, page and link",
     "knowledge": [DATA / "IMF_FSAP_reports_catalog.xlsx"],
     "website": "https://www.elibrary.imf.org",
     "code": False,
     "starters": ["What did the latest FSAP say about a topic for a country?", "Key recommendations of an FSAP report"],
     "test": "Key recommendations of the 2024 Saudi Arabia FSSA",
     "expected": "Only exact quotes: key sentences (para., page), then full paragraphs with paragraph number, report title, page and link; no own wording.",
     "note": "If the agent cannot open the reports, download the PDFs from the catalog links and upload them to "
             "Knowledge, or add a SharePoint/OneDrive folder that contains them."},
    {"folder": "5_Bank_Balance_Sheets", "source": "5_Bank_balance_sheets",
     "name": "Bank Balance Sheets",
     "description": "Banking-sector assets, liabilities and credit for any country: structure (pie or stacked bars), "
                    "growth by item and contributions by sector",
     "knowledge": [DATA / "IMF_Financial_Soundness_Indicators.xlsx", DATA / "IMF_MFS_banking_sector.xlsx"],
     "code": True,
     "starters": ["Bank asset structure for a country", "Loan portfolio pie for a country",
                  "Contributions to bank credit growth by sector"],
     "test": "Kuwait loan portfolio pie, then: Kuwait contributions to bank asset growth",
     "expected": "Pie with sector names and percent on the slices; stacked bars of sector contributions with "
                 "total growth dots; blue titles, official sources."},
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


try:  # private agents kept outside GitHub (m365-agent/private/agents/private_config.py)
    sys.path.insert(0, str(HERE.parent / "private" / "agents"))
    import private_config as _priv
except ImportError:
    _priv = None
if _priv:
    AGENTS.extend(_priv.PACKAGE)


NAMES = {'IMF_World_Economic_Outlook_data.xlsx': 'IMF World Economic Outlook.xlsx', 'BIS_credit_to_GDP.xlsx': 'BIS credit-to-GDP statistics.xlsx', 'IMF_MFS_credit_to_GDP.xlsx': 'IMF MFS credit to GDP.xlsx', 'IMF_iMaPP_macroprudential.xlsx': 'IMF iMaPP Database.xlsx', 'IMF_Financial_Soundness_Indicators.xlsx': 'IMF Financial Soundness Indicators.xlsx', 'IMF_MFS_banking_sector.xlsx': 'IMF MFS banking sector.xlsx', 'HEAT_bank_distribution.xlsx': 'SP Capital IQ Pro bank data.xlsx', 'IMF_FSAP_reports_catalog.xlsx': 'IMF FSAP reports.xlsx'}  # uploaded under official-source names
DROP = ("Code", "Heatmap", "GCC_Summary")  # old code / ready-made tables: the agents draw charts instead


def strip_sheets(path):
    """Remove the sheets in DROP and the README lines describing them from a knowledge copy."""
    import openpyxl
    wb = openpyxl.load_workbook(path)
    names = [n for n in DROP if n in wb.sheetnames]
    if not names:
        return
    for n in names:
        del wb[n]
    if "README" in wb.sheetnames:
        ws = wb["README"]
        for row in range(ws.max_row, 1, -1):
            v = str(ws.cell(row, 1).value or "")
            if any(f"'{n}'" in v or f"{n} sheet" in v for n in DROP):
                ws.delete_rows(row)
    wb.save(path)


MANIFEST = HERE / ".package_manifest.json"  # what was in the last package, to list what to re-upload


def report_changes():
    """Compare this package with the previous one and print, per agent, what to re-upload."""
    import hashlib
    import json
    src_of = {v: k for k, v in NAMES.items()}
    now = {}
    for f in OUT.rglob("*"):
        if not f.is_file() or f.name == "START_HERE.txt":
            continue
        path = f
        if f.suffix == ".xlsx":  # compare the source workbook (copies differ by save time)
            k = src_of.get(f.name, f.name)
            path = next((p for p in (DATA / k, ROOT / "local_data" / k) if p.exists()), f)
        now[f.relative_to(OUT).as_posix()] = hashlib.md5(path.read_bytes()).hexdigest()
    old = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    MANIFEST.write_text(json.dumps(now, indent=0))
    changed = sorted(k for k, v in now.items() if old.get(k) != v and not k.endswith("SETUP.txt"))
    if not old:
        print("\nFirst package build: upload everything.")
    elif not changed:
        print("\nNothing changed since the last package: no re-upload needed.")
    else:
        print("\nRE-UPLOAD IN COPILOT (changed since the last package):")
        by = {}
        for k in changed:
            agent, rest = k.split("/", 1)
            by.setdefault(agent, []).append("paste new INSTRUCTIONS.txt" if rest == "INSTRUCTIONS.txt"
                                            else "re-upload " + rest.split("/")[-1])
        for agent, items in by.items():
            print(f"  {agent}: " + "; ".join(items))


def main():
    subprocess.run([sys.executable, str(HERE / "build_agents.py")], check=True)  # fresh INSTRUCTIONS.txt, size check
    if OUT.exists():
        shutil.rmtree(OUT)
    lines = [f"COPILOT AGENTS PACKAGE - built {time.strftime('%Y-%m-%d %H:%M')}", "",
             "One folder per agent. In each: INSTRUCTIONS.txt, SETUP.txt, knowledge/ (files to upload).",
             "All agents work for any country; the user names it in the question.",
             "For internal use.", ""]
    for a in AGENTS:
        d = OUT / a["folder"]
        (d / "knowledge").mkdir(parents=True)
        instr = (HERE / a["source"] / "INSTRUCTIONS.txt").read_text(encoding="utf-8")
        (d / "INSTRUCTIONS.txt").write_text(instr, encoding="utf-8", newline="\r\n")
        for f in a["knowledge"]:
            if not f.exists():
                raise FileNotFoundError(f"Missing knowledge file: {f}")
            shutil.copy2(f, d / "knowledge" / NAMES.get(f.name, f.name))
            strip_sheets(d / "knowledge" / NAMES.get(f.name, f.name))
        n = len(instr.replace("\n", "\r\n"))
        setup = [f"AGENT: {a['name']}", "",
                 f"Name:        {a['name']}",
                 f"Description: {a['description']}",
                 f"Instructions: INSTRUCTIONS.txt ({n:,} characters; limit 8,000)",
                 "Knowledge:   " + ", ".join(NAMES.get(f.name, f.name) for f in a["knowledge"])
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
        print(f"{a['folder']:36} {n:5} chars, knowledge: {', '.join(NAMES.get(f.name, f.name) for f in a['knowledge'])}")
    main_agent = HERE.parent / "private" / "agents" / "0_Main_orchestrator"
    if main_agent.exists():  # main agent connecting all agents (private)
        shutil.copytree(main_agent, OUT / "0_Main_agent_Copilot_Studio")
        lines.append("0_Main_agent_Copilot_Studio: main agent that connects all agents (Copilot Studio)")
    (OUT / "START_HERE.txt").write_text("\n".join(lines + ["", "Create the agents in order 1-6; test each before the next."]),
                                        encoding="utf-8", newline="\r\n")
    report_changes()
    print(f"\nPackage: {OUT}")


if __name__ == "__main__":
    main()
