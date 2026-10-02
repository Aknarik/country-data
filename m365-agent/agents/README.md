# Six specialised Copilot agents

The single "Country Data Assistant" had to squeeze every tool into one 8,000-character instruction box.
These four agents each get their own box, so they carry clearer rules and more capable code, and each one
loads only its own data (faster, fewer time-outs). They can be combined later.

| # | Agent | What it does | Knowledge files |
|---|---|---|---|
| 1 | **WEO Economic Outlook** | Line charts for countries, groups (GCC, G20, ...) and aggregates, with solid actual lines, dashed projections on a grey band; ranking bars (projection years hatched); tables with `*` on projections; six-panel macro dashboard | `IMF_World_Economic_Outlook_data.xlsx` |
| 2 | **Credit Gap & Macroprudential** | Credit-to-GDP ratio, one-sided HP trend and gap (BIS; IMF MFS for Kuwait, UAE, Qatar, Oman), Basel 2-10 pp range and guide buffer, iMaPP tightening/loosening years on the chart; gaps from user data (ratio, or credit + GDP, e.g. non-oil GDP); household vs corporate credit; iMaPP measures table with magnitudes and definitions | `BIS_credit_to_GDP.xlsx`, `IMF_MFS_credit_to_GDP.xlsx`, `IMF_iMaPP_macroprudential.xlsx` |
| 3 | **Financial Soundness** | Dashboard in sections (capital, asset quality, profitability, liquidity, loans pie, sovereign-bank nexus); FSI heat map grouped by section; any FSI or banking series | `IMF_Financial_Soundness_Indicators.xlsx`, `IMF_MFS_banking_sector.xlsx` |
| 4 | **FSAP Reports** | Answers from the GCC FSAP reports: short answer, verbatim paragraph with the key sentence in bold, report title, page, link. No Python needed | `IMF_FSAP_reports_catalog.xlsx` + website `https://www.elibrary.imf.org` |
| 5 | **Bank Balance Sheets** | Asset and loan structure (pie with names and percent on slices, or stacked bars over time); growth of every asset/liability item and loan sector; contributions by sector to asset or credit growth | `IMF Financial Soundness Indicators.xlsx`, `IMF MFS banking sector.xlsx` |
| 6 | **Bank-by-Bank** | Individual banks with names: latest ranking, history for the largest banks with the median bank, single-bank profiles (capital, leverage, asset quality, income, liquidity, size); source S&P Capital IQ Pro | `SP Capital IQ Pro bank data.xlsx` |

The instructions for each agent are in `<agent folder>/INSTRUCTIONS.txt` (all under 8,000 characters).

## Ready-to-upload package

Run `python m365-agent/agents/build_package.py`. It creates `copilot_agents_package/` (git-ignored, contains
confidential HEAT data) with one folder per agent: `INSTRUCTIONS.txt` (paste), `SETUP.txt` (name, description,
starter prompts, test question) and `knowledge/` (exactly the files to upload). Rerun after every update.

## Create each agent (repeat 6 times)

1. Microsoft 365 Copilot → **Agents → Create agent** → **Configure** tab.
2. **Name**: e.g. "WEO Economic Outlook". **Description**: one line from the table above.
3. **Instructions**: open the agent's `INSTRUCTIONS.txt` in Notepad, **Ctrl+A, Ctrl+C**, paste. Paste the whole
   file; do not shorten it.
4. **Knowledge**: upload only that agent's files from the table (from `C:\Users\ayvaz\country_data\m365-agent\`;
   the HEAT file is in `C:\Users\ayvaz\country_data\local_data\`). Agent 4: also add the eLibrary website.
5. **Capabilities**: turn on **Code interpreter** (agents 1-3; agent 4 does not need it).
6. **Create**, wait until the knowledge files show as ready, then test in a new chat:
   - Agent 1: "Kuwait real GDP growth", "Compare government debt in the GCC", "Macro dashboard for Saudi Arabia"
   - Agent 2: "Kuwait credit gap", "UK household vs corporate credit", "Kuwait macroprudential measures",
     "What is DSTI?", then paste your own credit and non-oil GDP numbers and ask for the gap
   - Agent 3: "Banking dashboard for Kuwait", "FSI heat map for Bahrain", "Oman loan portfolio",
     "Saudi loan portfolio pie 2025", "Kuwait Tier 1 by bank"
   - Agent 4: "What did the 2019 Kuwait FSSA say about liquidity risk? Quote the paragraph.",
     "Key recommendations of the 2024 Saudi Arabia FSSA"

Agent 6 includes the S&P Capital IQ Pro bank data; the agents are for internal use.

## Updating later

| What changed | Run (in `C:\Users\ayvaz\country_data`) | Re-upload to |
|---|---|---|
| New WEO (April/October) or FSI / BIS / MFS data | `python m365-agent/build_data_file.py` then `python m365-agent/build_gcc_central_banks.py` | agents 1, 2, 3 (their files) |
| New GCC central bank bulletins | `python m365-agent/build_gcc_central_banks.py` | agent 3 |
| New iMaPP or HEAT release | `python m365-agent/build_local_sources.py` | agent 2 (iMaPP), agent 3 (HEAT) |
| New FSAP report | edit `m365-agent/fsap_reports.csv`, run `python m365-agent/build_data_file.py --tools-only` | agent 4 |
| Changed agent rules or code | edit `agents/*_rules.txt` / `*_code.py`, run `python m365-agent/agents/build_agents.py` (checks the 8,000 limit) and `python m365-agent/agents/test_agents.py` | paste the new `INSTRUCTIONS.txt` into that agent |

When replacing a knowledge file: delete the old copy first, upload the new one with the same name, click
**Update**, and test in a **new** chat (old chats keep the old instructions).

## Files

- `common.py`: shared core in every agent (file loading, IMF-blue titles, source line, confidential label)
- `weo_*`, `gap_*`, `fin_*`, `fsap_rules.txt`: rules and code per agent
- `build_agents.py`: writes the four `INSTRUCTIONS.txt` files; `test_agents.py`: runs every function in a clean
  sandbox holding only that agent's knowledge files
