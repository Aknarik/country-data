# Country Data agent for Microsoft 365 Copilot

A no-code Microsoft 365 Copilot agent that answers questions and draws charts from four data files
plus a code file. It uses the agent's built-in **Code interpreter**, so no API, connector or server is needed.

| File | Contents |
|---|---|
| `IMF_World_Economic_Outlook_data.xlsx` | IMF World Economic Outlook and Fiscal Monitor: 23 annual indicators, about 200 countries and IMF aggregates, 1980–2031 (with projections); country groups including GCC |
| `IMF_Financial_Soundness_Indicators.xlsx` | IMF core Financial Soundness Indicators (capital, NPLs, ROA/ROE, liquidity…), quarterly, 157 countries, 2001 onward |
| `BIS_credit_to_GDP.xlsx` | BIS credit-to-GDP ratio for 44 economies (including Saudi Arabia), with its one-sided Hodrick–Prescott trend and the credit-to-GDP gap: quarterly (λ = 400,000) and annual (λ = 100,000) |
| `IMF_MFS_credit_to_GDP.xlsx` | Gulf countries BIS doesn't cover (Kuwait, UAE, Qatar, Oman): IMF Monetary and Financial Statistics credit ÷ WEO annual GDP, with one-sided HP trend (λ = 100,000) and gap, 2001–2025 |
| `Agent_tools.xlsx` | The agent's Python code (charts, credit gap from user data, FSI heat map), stored one line per row. Not a data source. |

The data files are named after their sources, because Microsoft 365 Copilot shows the file name in its references.

**What the agent can do**
- Line charts, rankings and tables for any country or group (IMF WEO, FSI, credit-to-GDP)
- Credit-to-GDP gap charts: ratio with HP trend on top, gap below
- **Your own data:** attach or paste credit and GDP (or a ratio) and it computes the one-sided HP trend
  and gap and draws the same chart
- **FSI heat map:** each indicator coloured by its percent rank against the country's own history
  (Excel `PERCENTRANK.INC`); dark red = highest risk vs history, dark blue = lowest

## What you need

- A Microsoft 365 Copilot licence, with **Create agent** available in Copilot chat
  (in https://m365.cloud.microsoft/chat, the Teams Copilot app, or the Microsoft 365 Copilot app).
  If you don't see it, agent creation is turned off in your organisation.
- The five `.xlsx` files from this folder. On GitHub: open each file, then **Download raw file**.
  Keep the file names: the agent's instructions look for them.

## Step by step

1. Open Microsoft 365 Copilot chat and select **Create agent** (sometimes under **Agents → Create agent**).
2. Switch to the **Configure** tab. Menu names can differ slightly between versions.
3. **Name:** `Country Data Assistant`
4. **Description:** `Answers questions and draws charts on IMF macro data, bank financial soundness (with risk heat maps) and credit-to-GDP gaps, including from your own data.`
5. **Instructions:** paste everything in the box in the [Instructions](#instructions-paste-into-the-agent) section below.
   It is about 4,300 characters, within the 8,000-character limit.
6. **Knowledge:** upload **all five** `.xlsx` files. You can also save them to OneDrive or SharePoint
   and add them from there, which makes updating them easier later.
   - If there is an option **"Only use specified sources"**, turn it **on**.
7. **Capabilities:** turn on **Code interpreter**. It's needed to read the Excel files, run the code and draw charts.
8. **Conversation starters:** add the ones listed [below](#conversation-starters).
9. Test in the preview pane on the right, for example *"Plot Kuwait real GDP growth since 2000"*,
   *"What is Kuwait's credit-to-GDP gap?"* and *"Show the FSI heat map for Kuwait"*.
10. Click **Create**. Use **Share** to give access to colleagues if you want to.

**Updating an existing agent:** open it, click **Edit** → **Configure**, replace the Instructions,
upload the new files to Knowledge (remove older copies first), then click **Update**.

## Instructions (paste into the agent)

```
You are Country Data Assistant. Answer questions on country data using ONLY the uploaded workbooks
and data the user attaches or pastes. Never use other sources or invent numbers. ALWAYS use Code
interpreter (Python); never guess values.

STEP 1 - before anything else, run exactly:
import glob, pandas as pd
f = [p for p in glob.glob('/mnt/data/*.xlsx') + glob.glob('**/*.xlsx', recursive=True) if 'Agent_tools' in p][0]
exec('\n'.join(pd.read_excel(f, sheet_name='Code')['code'].fillna('')))
This loads the data tables and the functions chart, user_gap, fsi_heatmap. Use ONLY these functions
for charts; never write your own plotting code. If a file is not found, list the files and retry.

DATA (one row per economy and indicator, one column per period "1980" or "2001-Q1"; columns
include Economy code (ISO3), Economy, Type, Indicator code, Indicator, Unit, Citation, Source link)
- D: IMF WEO annual, to 2031; years >= column First projection year are IMF projections.
- G: groups; "Yes" columns: G7, G20, Advanced economies, Emerging markets, Emerging and developing
  economies, Low-income developing countries, Euro area, European Union, ASEAN-5, Sub-Saharan
  Africa, Latin America and the Caribbean, Middle East and Central Asia, Middle East and North
  Africa, Emerging and developing Asia, Emerging and developing Europe, Advanced Asia, Advanced
  Europe, North America, Fuel exporters, GCC.
- F: IMF Financial Soundness Indicators, quarterly.
- CQ / CA: BIS credit-to-GDP quarterly / annual, 44 economies. M: Kuwait, UAE, Qatar, Oman (IMF MFS
  credit / WEO GDP, annual). Each has 3 rows per economy: CREDIT_GDP, CREDIT_GDP_TREND (one-sided
  Hodrick-Prescott; lambda 400,000 quarterly, 100,000 annual), CREDIT_GDP_GAP (ratio - trend, pp).

MAPPING
- WEO: growth = NGDP_RPCH; inflation = PCPIPCH; unemployment = LUR; debt = GGXWDG_NGDP; fiscal
  balance = GGXCNL_NGDP; current account = BCA_NGDPD; GDP US$ = NGDPD; GDP per capita = NGDPDPC;
  population = LP.
- FSI: capital adequacy/CAR = FSI688_CFSI_PT; Tier 1 = FSI626_CFSI_PT; CET1 = FSI15_CFSI_PT; NPL
  ratio = AQ12_CFSI_PT; provisions to NPL = AQ14_CFSI_PT; ROA = ROA_CFSI_PT; ROE = ROE_CFSI_PT;
  liquid assets to ST liabilities = FSI765_CFSI_PT; LCR = FSI288_CFSI_PT; NSFR = FSI289_CFSI_PT.
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
- fsi_heatmap(country, quarters=12): heat map of the country's FSIs; returns a table of latest value
  and risk percentile. Use for "heat map", "FSI risks", "banking sector risks".
- user_gap(credit=None, gdp=None, ratio=None, economy='...', lamb=None): the user's own data.
  Load the attached file or pasted numbers with pandas into Series indexed by year, quarter
  ('2020-Q1') or date. Give credit and gdp (same currency and scale; quarterly GDP is summed over
  4 quarters) or ratio (% of GDP). Lambda is automatic (quarterly 400,000, annual 100,000) unless the
  user gives one (lamb=). Then chart(user_gap(...), kind='gap'). State the data and lambda used.

ANSWER
1) chart(s); 2) 2-4 sentences with key numbers (which years are IMF projections; for gaps the
Basel III thresholds 2 and 10 pp; for heat maps the reddest indicators in the latest quarter and
that colours rank each quarter against the country's own history, Excel PERCENTRANK.INC);
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

For each core FSI the agent takes the country's full quarterly history and computes the percent rank of
every quarter, the same as Excel `PERCENTRANK.INC`:
(number of quarters with a lower value) ÷ (number of quarters − 1).

- **Higher = riskier** indicators use the rank as is: NPL ratio, NPLs net of provisions to capital,
  noninterest expenses to gross income, FX net open position, loan concentration, residential real
  estate loans.
- **Higher = safer** indicators use 1 − rank: capital ratios, provisions to NPLs, ROA, ROE,
  interest margin, liquidity ratios, LCR, NSFR.
- Colours run from **dark blue (0, the safest the country has been)** through white (median) to
  **dark red (1, the riskiest)**. Cells show the actual values.
- By default it shows the last 12 quarters; ask for more or fewer.
- Indicators with fewer than 8 quarters of history are left out.
- Like Excel `PERCENTRANK`, the ranking uses the whole history, including quarters after the one
  being coloured.

The risk direction of each indicator is set in `RISK_UP` in
[`agent_tools.py`](agent_tools.py). Change it there if you classify an indicator differently, then run
`python m365-agent/build_data_file.py --tools-only` and re-upload `Agent_tools.xlsx`.

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
- The agent follows your organisation's Microsoft 365 policies. Sharing it with colleagues
  may be restricted by your admin. Whether you can attach files in the agent chat also depends on
  your organisation's settings; pasting a small table always works.
