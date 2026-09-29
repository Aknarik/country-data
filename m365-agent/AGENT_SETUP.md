# Country Data agent for Microsoft 365 Copilot

A no-code Microsoft 365 Copilot agent that answers questions and draws charts from five data files and a
code file, and answers questions from IMF FSAP reports on the Gulf countries. It uses the agent's built-in
**Code interpreter**, so no API, connector or server is needed.

| File | Contents |
|---|---|
| `IMF_World_Economic_Outlook_data.xlsx` | IMF World Economic Outlook and Fiscal Monitor: 23 annual indicators, about 200 countries and IMF aggregates, 1980–2031 (with projections); country groups including GCC |
| `IMF_Financial_Soundness_Indicators.xlsx` | IMF Financial Soundness Indicators, core and selected additional (capital, asset quality, concentration, earnings, funding and liquidity incl. deposits to loans, FX exposure incl. FX loans), quarterly, 157 countries, 2001 onward; each indicator's group and vulnerability direction |
| `BIS_credit_to_GDP.xlsx` | BIS credit-to-GDP ratio for 44 economies (including Saudi Arabia), with its one-sided Hodrick–Prescott trend and the credit-to-GDP gap: quarterly (λ = 400,000) and annual (λ = 100,000) |
| `IMF_MFS_credit_to_GDP.xlsx` | Gulf countries BIS doesn't cover (Kuwait, UAE, Qatar, Oman): IMF Monetary and Financial Statistics credit ÷ WEO annual GDP, with one-sided HP trend (λ = 100,000) and gap, 2001–2025 |
| `IMF_FSAP_reports_catalog.xlsx` | List of the 21 IMF FSAP reports for GCC countries (2001–2024): title, type, topics, eLibrary links and the PDF file name to use |
| `Agent_tools.xlsx` | The agent's Python code (charts, credit gap from user data, FSI heat map), stored one line per row. The same code is also in a "Code" sheet in every workbook, so the agent finds it in whichever file Copilot provides. Not a data source. |
| FSAP reports (online) | The agent reads the reports through the eLibrary links in the catalog (see [FSAP reports](#fsap-reports)) |

The data files are named after their sources, because Microsoft 365 Copilot shows the file name in its references.

**What the agent can do**
- Line charts, rankings and tables for any country or group (IMF WEO, FSI, credit-to-GDP)
- Credit-to-GDP gap charts: ratio with HP trend on top, gap below
- **Your own data:** attach or paste credit and GDP (or a ratio) and it computes the one-sided HP trend
  and gap and draws the same chart
- **FSI heat map:** each indicator coloured by its percent rank against the country's own history
  (Excel `PERCENTRANK.INC`), oriented by financial-sector vulnerability; dark red = most vulnerable
  vs history, dark blue = least
- **FSAP reports:** questions on IMF Financial Sector Assessment Program findings, stress tests and
  recommendations for Gulf countries, answered from the report text with citations

## What you need

- A Microsoft 365 Copilot licence, with **Create agent** available in Copilot chat
  (in https://m365.cloud.microsoft/chat, the Teams Copilot app, or the Microsoft 365 Copilot app).
  If you don't see it, agent creation is turned off in your organisation.
- The six `.xlsx` files from this folder. On GitHub: open each file, then **Download raw file**.
  Keep the file names: the agent's instructions look for them.
- For FSAP questions: web access for the agent to open the IMF eLibrary links (see [FSAP reports](#fsap-reports)).

## Step by step

1. Open Microsoft 365 Copilot chat and select **Create agent** (sometimes under **Agents → Create agent**).
2. Switch to the **Configure** tab. Menu names can differ slightly between versions.
3. **Name:** `Country Data Assistant`
4. **Description:** `Answers questions and draws charts on IMF macro data, bank financial soundness (with vulnerability heat maps) and credit-to-GDP gaps, including from your own data, and answers questions from IMF FSAP reports on Gulf countries.`
5. **Instructions:** paste everything in the box in the [Instructions](#instructions-paste-into-the-agent) section below.
   It is about 6,600 characters, within the 8,000-character limit.
6. **Knowledge:** upload **all six** `.xlsx` files directly. Code interpreter needs them as uploaded files.
   For FSAP questions, also add the website `https://www.elibrary.imf.org` as a knowledge source and/or
   keep web search on (see [FSAP reports](#fsap-reports)).
   - If there is an option **"Only use specified sources"**, turn it **on**.
7. **Capabilities:** turn on **Code interpreter**. It's needed to read the Excel files, run the code and draw charts.
8. **Conversation starters:** add the ones listed [below](#conversation-starters).
9. Test in the preview pane on the right, for example *"Plot Kuwait real GDP growth since 2000"*,
   *"What is Kuwait's credit-to-GDP gap?"*, *"Show the FSI heat map for Kuwait"* and
   *"What were the main recommendations of Kuwait's 2018 FSAP?"*.
10. Click **Create**. Use **Share** to give access to colleagues if you want to.

**Updating an existing agent:** open it, click **Edit** → **Configure**, replace the Instructions,
upload the new files to Knowledge (remove older copies first), then click **Update**.

## Instructions (paste into the agent)

```
You are Country Data Assistant. Answer using ONLY your knowledge files, the IMF FSAP reports listed
in the catalog (read via their links), and data the user attaches or pastes. Never use other sources
or invent numbers.

DATA AND CHART questions: use Code interpreter (Python); never guess values.
STEP 1 - before any data work, run exactly:
import glob, pandas as pd
fs = [p for pat in ('/mnt/**/*.xls*', '**/*.xls*') for p in glob.glob(pat, recursive=True)]
f = next(p for p in fs if 'Code' in pd.ExcelFile(p).sheet_names)
exec('\n'.join(pd.read_excel(f, sheet_name='Code')['code'].fillna('')))
This loads the available data tables (it prints which) and the functions chart, user_gap,
fsi_heatmap. Use ONLY these functions for charts; never write your own plotting code. If no
workbook is found or the data needed is "Not available", tell the user which workbook to attach
in the chat (e.g. IMF_Financial_Soundness_Indicators.xlsx) and retry.

IF YOU CANNOT RUN PYTHON: never say you computed or charted anything. Answer from the summary
sheets: IMF_World_Economic_Outlook_data.xlsx sheet GCC_Summary; IMF_Financial_Soundness_Indicators
.xlsx sheet Latest (latest value, a year earlier, vulnerability percentile 0-1 vs own history);
BIS_credit_to_GDP.xlsx and IMF_MFS_credit_to_GDP.xlsx sheet Latest (ratio, HP trend, gap). Give a
table with the source, and say charts need Code interpreter (Microsoft 365 Copilot licence).

DATA (one row per economy and indicator, one column per period "1980" or "2001-Q1"; columns
include Economy code (ISO3), Economy, Type, Indicator code, Indicator, Unit, Citation, Source link)
- D: IMF WEO annual, to 2031; years >= column First projection year are IMF projections.
- G: groups; "Yes" columns: G7, G20, Advanced economies, Emerging markets, Emerging and developing
  economies, Low-income developing countries, Euro area, European Union, ASEAN-5, Sub-Saharan
  Africa, Latin America and the Caribbean, Middle East and Central Asia, Middle East and North
  Africa, Emerging and developing Asia, Emerging and developing Europe, Advanced Asia, Advanced
  Europe, North America, Fuel exporters, GCC.
- F: IMF Financial Soundness Indicators, quarterly.
  Columns Group and "More vulnerable when" (higher/lower) give the vulnerability direction.
- CQ / CA: BIS credit-to-GDP quarterly / annual, 44 economies. M: Kuwait, UAE, Qatar, Oman (IMF MFS
  credit / WEO GDP, annual). Each has 3 rows per economy: CREDIT_GDP, CREDIT_GDP_TREND (one-sided
  Hodrick-Prescott; lambda 400,000 quarterly, 100,000 annual), CREDIT_GDP_GAP (ratio - trend, pp).

MAPPING
- WEO: growth = NGDP_RPCH; inflation = PCPIPCH; unemployment = LUR; debt = GGXWDG_NGDP; fiscal
  balance = GGXCNL_NGDP; current account = BCA_NGDPD; GDP US$ = NGDPD; GDP per capita = NGDPDPC;
  population = LP.
- FSI: capital adequacy/CAR = FSI688_CFSI_PT; Tier 1 = FSI626_CFSI_PT; CET1 = FSI15_CFSI_PT; NPL
  ratio = AQ12_CFSI_PT; provisions to NPL = AQ14_CFSI_PT; ROA = ROA_CFSI_PT; ROE = ROE_CFSI_PT;
  liquid assets to ST liabilities = FSI765_CFSI_PT; LCR = FSI288_CFSI_PT; NSFR = FSI289_CFSI_PT;
  deposits to loans = FSI55_AFSI_PT; FX loans = FSI131_AFSI_PT; large exposures = FSI214_AFSI_PT.
- Credit gap: Kuwait, UAE, Qatar, Oman -> M; others incl. Saudi Arabia -> CQ (CA if annual asked).
  Bahrain and economies not listed: not covered; offer to compute from the user's own data.
- Countries: match Economy (case-insensitive) or Economy code; US = United States, UK = United
  Kingdom, Turkey = Türkiye. Group members: codes from G. Group totals: Type "Aggregate" rows.
- Unclear request: ask one short question.

FUNCTIONS
- chart(rows, start=2000, end=2031, kind='line'|'bar'|'gap', year=None). Rankings or more than 10
  economies: kind='bar'. ANY credit / credit gap question: pass the 3 rows of one economy with
  kind='gap' (top: ratio + Hodrick-Prescott trend; bottom: gap bars). One chart per economy.
  Examples: chart(D[(D['Economy']=='Kuwait') & (D['Indicator code']=='NGDP_RPCH')])
            chart(M[M['Economy']=='Kuwait'], kind='gap')
- fsi_heatmap(country, quarters=12): FSI heat map; colour = percent rank of each quarter in the
  country's own history, oriented so dark red = most vulnerable. Returns group, latest value and
  vulnerability percentile. Use for "heat map", "FSI risks", "banking sector vulnerabilities".
- user_gap(credit=None, gdp=None, ratio=None, economy='...', lamb=None): the user's own data.
  Load the attached file or pasted numbers with pandas into Series indexed by year, quarter
  ('2020-Q1') or date. Give credit and gdp (same currency and scale; quarterly GDP is summed over
  4 quarters) or ratio (% of GDP). Lambda is automatic (quarterly 400,000, annual 100,000) unless the
  user gives one (lamb=). Then chart(user_gap(...), kind='gap'). State the data and lambda used.

FSAP REPORTS (IMF Financial Sector Assessment Program, GCC countries 2001-2024; the list with
titles, years, types, topics and links is in IMF_FSAP_reports_catalog.xlsx, sheet Reports)
- Questions on FSAP findings, risks, stress tests, recommendations, supervision (BCP), securities
  (IOSCO), payment systems (FMI) or AML/CFT: find the report in the catalog (latest relevant one
  unless asked otherwise), read it through its PDF link or eLibrary link, and answer from its text,
  no code. FSSA = main stability assessment; DAR = detailed assessment of one standard.
- FSAP ANSWER FORMAT: (1) a short direct answer, saying the report year; (2) Evidence: for each
  point, quote the relevant paragraph word for word as a quote block, with the sentence that
  justifies the answer in **bold**; under each quote give report title, publication year, page
  or paragraph number, and the link (PDF link, else eLibrary link). Never paraphrase inside quote
  marks; if you cannot find a supporting paragraph, say so.
- "Which FSAP reports exist for X": list them from the catalog with year and eLibrary link.
- If you cannot open a report, say so and give its eLibrary link; never answer from memory.
- You may combine a report's findings with the latest data (e.g. FSIs) - say which is which.

ANSWER (data questions)
1) chart(s); 2) 2-4 sentences with key numbers (which years are IMF projections; for gaps the
Basel III thresholds 2 and 10 pp; for heat maps the most vulnerable (reddest) indicators in the
latest quarter and that colours rank each quarter against the country's own history);
3) small table; 4) last line "Source: <Citation> - <Source link>" of the rows used, or "User-provided
data" for the user's data. Cite the original source, never a workbook. Missing data: say so, never
fill gaps.
```

## Conversation starters

| Title | Message |
|---|---|
| Kuwait growth | Plot Kuwait real GDP growth since 2000 |
| G7 inflation | Compare inflation in the G7 countries since 2015 |
| Gulf banks | Compare nonperforming loan ratios in Kuwait, Saudi Arabia and the UAE |
| FSI heat map | Show the financial soundness heat map for Kuwait |
| Kuwait credit gap | What is Kuwait's credit-to-GDP gap? |
| My own data | I will attach credit and GDP data - calculate the credit-to-GDP gap |
| Kuwait FSAP | What were the main findings and recommendations of Kuwait's latest FSAP? |

## Using your own credit and GDP data

Attach an Excel or CSV file in the chat, or paste a small table, and ask for the credit-to-GDP gap.
For example: *"Here is Kuwait's credit and non-oil GDP, calculate the credit gap"*.

- **Layout:** one column for the period (year such as `2015`, quarter such as `2015-Q1`, or a date),
  plus columns for credit and GDP, or one column for the credit-to-GDP ratio in percent.
- **Units:** credit and GDP must be in the same currency and scale (for example both KWD millions).
- **Frequency** is detected automatically:
  - Quarterly: λ = 400,000. Quarterly GDP is summed over the last 4 quarters, as BIS does.
    If you give quarterly credit with annual GDP, each quarter is divided by its calendar year's GDP.
  - Annual: λ = 100,000.
  - Ask for a different λ if you want one, for example *"use lambda 1,600"*.
- As with the BIS data, the trend is shown from 10 years after the first observation.
- The agent cites your data as "User-provided data".

This is also how to use **non-oil GDP** for oil exporters: provide credit and non-oil GDP.

## FSI heat map

For each FSI the agent takes the country's full quarterly history and computes the percent rank of
every quarter, the same as Excel `PERCENTRANK.INC`:
(number of quarters with a lower value) ÷ (number of quarters − 1).

Indicators are grouped and oriented from a **financial-sector vulnerability** perspective. The rank is
used as is when a higher value means more vulnerability, and as 1 − rank when a lower value does:

| Group | More vulnerable when **higher** | More vulnerable when **lower** |
|---|---|---|
| Capital adequacy | | Regulatory capital, Tier 1, CET1 to risk-weighted assets; Tier 1 capital to assets |
| Asset quality | NPLs to gross loans; NPLs net of provisions to capital | Provisions to NPLs |
| Concentration | Loan concentration by activity; large exposures to capital; residential and commercial real estate loans to total loans | |
| Earnings | Noninterest expenses to gross income | ROA; ROE; interest margin to gross income |
| Funding and liquidity | | Liquid assets to short-term liabilities and to total assets; LCR; NSFR; customer deposits to loans |
| FX exposure | Net open FX position to capital; FX loans to total loans; FX liabilities to total liabilities | |
| Household sector | Household debt to GDP | |

- Colours run from **dark blue (0, the least vulnerable the country has been)** through white (median)
  to **dark red (1, the most vulnerable)**. Cells show the actual values. Only indicators the country
  reports appear.
- By default it shows the last 12 quarters; ask for more or fewer.
- Indicators with fewer than 8 quarters of history are left out.
- Like Excel `PERCENTRANK`, the ranking uses the whole history, including quarters after the one
  being coloured.

The groups and directions are set in `FSI_SERIES` in
[`financial_data.py`](../.github/skills/country-data/scripts/financial_data.py) (the last field: `True` =
more vulnerable when higher). They are written to the FSI workbook's "Group" and "More vulnerable when"
columns. After changing them, run `python m365-agent/build_data_file.py` and re-upload
`IMF_Financial_Soundness_Indicators.xlsx`.

## FSAP reports

`IMF_FSAP_reports_catalog.xlsx` lists 21 IMF FSAP reports for the GCC countries (from
[`fsap_reports.csv`](fsap_reports.csv)):

| Country | Reports (assessment year) |
|---|---|
| Kuwait | FSSA 2004, 2010 (update), **2018**; detailed assessments: IOSCO 2004, AML/CFT 2010 |
| Saudi Arabia | FSSA 2004, 2011 (update), 2017, **2024**; detailed assessments: IOSCO, BCP, payment systems 2011; BCP 2024 |
| United Arab Emirates | FSSA 2001, 2007; detailed assessments: DIFC IOSCO 2007, AML/CFT 2007 |
| Bahrain | FSSA 2005; detailed assessments: AML/CFT 2005, FMI 2016 |
| Qatar | Detailed assessment: AML/CFT 2007 |

**How the agent reads the reports.** The catalog gives each report's eLibrary and PDF links, and the agent
opens the report through them. Make sure the agent can reach the IMF eLibrary:

1. In **Knowledge**, add the public website `https://www.elibrary.imf.org` (if your Agent Builder offers
   website knowledge), and/or
2. keep **web search** turned on for the agent (setting name varies: *Web search* / *Search all websites*).

Test with *"What were the main recommendations of Kuwait's 2018 FSAP?"*. The answer should give a short
summary, then quote the supporting paragraphs from the report with the key sentence in **bold**, each with
the report title, page and link. If the agent says it can't open a report, download that PDF from the
link (save it under the name in the catalog's **PDF file name** column, e.g.
`IMF_FSAP_Kuwait_2018_FSSA_2019.pdf`) and add it to Knowledge, directly or via a SharePoint/OneDrive folder.

To add more reports (other countries or newer FSAPs), add rows to `fsap_reports.csv`, run
`python m365-agent/build_data_file.py --tools-only` and re-upload the catalog.

## About the "source" shown by Copilot

The agent's answers and charts cite the original source, for example
*"Source: International Monetary Fund, World Economic Outlook (April 2026) -
https://www.imf.org/external/datamapper/NGDP_RPCH@WEO/KWT"*. For the credit-to-GDP trend and gap the
citation says they are an own calculation (one-sided HP filter) based on BIS or IMF data.

Microsoft 365 Copilot also adds its own reference to any knowledge file it used, shown as a
citation chip or numbered reference. Agent instructions can't remove that. This is why each file
is named after its source: the automatic reference then reads as the IMF or BIS source.

## How the credit-to-GDP gap is calculated

- **Ratio:** BIS credit to the private non-financial sector from all sectors, % of GDP, adjusted for breaks.
- **Trend:** one-sided Hodrick–Prescott filter. For each period, a standard HP filter is fitted on the
  data up to that period only, and its last value is the trend. No future data is used.
  - Quarterly data: λ = 400,000
  - Annual data (calendar-year averages, complete years only): λ = 100,000
  - As in the BIS statistics, a trend is reported only once 10 years of data are available.
- **Gap:** ratio minus trend, in percentage points of GDP.
- **Check:** the quarterly trend and gap reproduce the BIS-published figures to 4 decimal places
  (tested on the US, UK, Germany, Japan, China, Saudi Arabia and the euro area).

### Gulf countries not covered by BIS (IMF Monetary and Financial Statistics)

For Kuwait, the UAE, Qatar and Oman the ratio is built from IMF data:

- **Credit:** depository corporations' *claims on other sectors* minus *claims on public non-financial
  corporations* (dataset `IMF.STA:MFS_DC`), end of year, domestic currency. The narrower
  *claims on private sector* series isn't used because it has a reclassification break for Kuwait:
  about 98% of GDP in 2015 but 4% in 2024, with the rest moved to "other financial corporations".
  That break would create a false collapse in the ratio.
- **GDP:** annual nominal GDP in domestic currency from the IMF World Economic Outlook (`NGDP`).
  The latest year may be an IMF estimate. Public IMF data has no non-oil GDP; to use non-oil GDP,
  give the agent your own series (see [Using your own credit and GDP data](#using-your-own-credit-and-gdp-data)).
- **Ratio = credit ÷ GDP × 100.** Trend: one-sided HP filter with λ = 100,000 (annual data), from 10
  years after the series start, so from 2011. Gap = ratio − trend.
- **Saudi Arabia** uses the BIS series, which is quarterly and starts in 1993; IMF MFS only has
  2022 onward. **Bahrain** has no IMF MFS data.
- **Oil prices:** Gulf GDP swings with oil prices, so the ratio jumps when oil prices fall
  (for example 2009, 2015 and 2020) even if credit growth is steady. Keep this in mind when
  reading the gap.

The code is in [`.github/skills/country-data/scripts/financial_data.py`](../.github/skills/country-data/scripts/financial_data.py)
(`hp_one_sided`, `credit_gap`, `credit_to_gdp_with_gap`, `mfs_credit_to_gdp_with_gap`, `fetch_fsi`).
It can also be used on its own:

```
python .github/skills/country-data/scripts/financial_data.py credit --countries "SA,US" --out credit_gap.csv --plot gap.png
python .github/skills/country-data/scripts/financial_data.py credit --countries US --annual
python .github/skills/country-data/scripts/financial_data.py fsi --countries "KWT,SAU,ARE" --out fsi.csv
python .github/skills/country-data/scripts/financial_data.py mfs --out gulf_gap.csv --plot gulf.png
python .github/skills/country-data/scripts/financial_data.py mfs --non-oil-gdp m365-agent/non_oil_gdp.csv --out gulf_nonoil.csv
```

## Updating the data

The IMF publishes new WEO data in **April** and **October**; FSI and BIS data are updated quarterly.
To refresh all files:

```
python m365-agent/build_data_file.py
```

It takes about 5 minutes. Then replace the files in the agent's knowledge, or overwrite the
OneDrive/SharePoint copies if you linked them from there. After changing only the agent code
([`agent_tools.py`](agent_tools.py)), run `python m365-agent/build_data_file.py --tools-only` and
re-upload `Agent_tools.xlsx`.

## Limitations

- WEO data is annual; FSI and credit-to-GDP data are quarterly. No monthly data.
- Credit-to-GDP covers the 44 BIS economies plus Kuwait, the UAE, Qatar and Oman (IMF MFS). Bahrain
  is not covered, but you can supply your own data.
- For World Bank indicators (life expectancy, CO2, ...) use the GitHub Copilot skill in this repo instead.
- Numbers are a snapshot as of the build date shown in each file's README sheet.
- FSAP answers are only as current as the latest report (e.g. Kuwait 2018); the agent states the report year.
- The agent follows your organisation's Microsoft 365 policies. Sharing it with colleagues
  may be restricted by your admin. Whether you can attach files in the agent chat also depends on
  your organisation's settings; pasting a small table always works.
