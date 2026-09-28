# Country Data agent for Microsoft 365 Copilot

A no-code Microsoft 365 Copilot agent that answers questions and draws charts from four data files.
It uses the agent's built-in **Code interpreter**, so no API, connector or server is needed.

| File | Contents |
|---|---|
| `IMF_World_Economic_Outlook_data.xlsx` | IMF World Economic Outlook and Fiscal Monitor: 23 annual indicators, about 200 countries and IMF aggregates, 1980–2031 (with projections); country groups including GCC |
| `IMF_Financial_Soundness_Indicators.xlsx` | IMF core Financial Soundness Indicators (capital, NPLs, ROA/ROE, liquidity…), quarterly, 157 countries, 2001 onward |
| `BIS_credit_to_GDP.xlsx` | BIS credit-to-GDP ratio for 44 economies (including Saudi Arabia), with its one-sided Hodrick–Prescott trend and the credit-to-GDP gap: quarterly (λ = 400,000) and annual (λ = 100,000) |
| `IMF_MFS_credit_to_GDP.xlsx` | Gulf countries BIS doesn't cover (Kuwait, UAE, Qatar, Oman): IMF Monetary and Financial Statistics credit ÷ WEO annual GDP, with one-sided HP trend (λ = 100,000) and gap, 2001–2025 |

Each file is named after its source, because Microsoft 365 Copilot shows the file name in its references.

## What you need

- A Microsoft 365 Copilot licence, with **Create agent** available in Copilot chat
  (in https://m365.cloud.microsoft/chat, the Teams Copilot app, or the Microsoft 365 Copilot app).
  If you don't see it, agent creation is turned off in your organisation.
- The four `.xlsx` files from this folder. On GitHub: open each file, then **Download raw file**.
  Keep the file names: the agent's instructions look for them.

## Step by step

1. Open Microsoft 365 Copilot chat and select **Create agent** (sometimes under **Agents → Create agent**).
2. Switch to the **Configure** tab. Menu names can differ slightly between versions.
3. **Name:** `Country Data Assistant`
4. **Description:** `Answers questions and draws charts on IMF macro data, IMF financial soundness indicators and BIS credit-to-GDP gaps for any country or group.`
5. **Instructions:** paste everything in the box in the [Instructions](#instructions-paste-into-the-agent) section below.
   It is about 6,800 characters, within the 8,000-character limit.
6. **Knowledge:** upload **all four** `.xlsx` files. You can also save them to OneDrive or SharePoint
   and add them from there, which makes updating them easier later.
   - If there is an option **"Only use specified sources"**, turn it **on**.
7. **Capabilities:** turn on **Code interpreter**. It's needed to read the Excel data and draw charts.
8. **Conversation starters:** add the ones listed [below](#conversation-starters).
9. Test in the preview pane on the right, for example *"Plot Kuwait real GDP growth since 2000"* and
   *"Show Saudi Arabia's credit-to-GDP gap"*.
10. Click **Create**. Use **Share** to give access to colleagues if you want to.

**Updating an existing agent:** open it, click **Edit** → **Configure**, replace the Instructions,
upload the new files to Knowledge (remove older copies first), then click **Update**.

## Instructions (paste into the agent)

```
You are Country Data Assistant. Answer questions on country data using ONLY the four uploaded
workbooks. Never use other sources or invent numbers. ALWAYS use Code interpreter (Python); never guess.

FILES (each sheet: one row per economy and indicator, one column per period; blank = no data;
columns include Economy code (ISO3), Economy, Type, Indicator code, Indicator, Unit, Citation, Source link)
- IMF_World_Economic_Outlook_data.xlsx: sheet Data (annual "1980".."2031", column First projection year:
  later years are IMF projections); sheet Groups ("Yes" columns: G7, G20, Advanced economies, Emerging
  markets, Emerging and developing economies, Low-income developing countries, Euro area, European
  Union, ASEAN-5, Sub-Saharan Africa, Latin America and the Caribbean, Middle East and Central Asia,
  Middle East and North Africa, Emerging and developing Asia, Emerging and developing Europe,
  Advanced Asia, Advanced Europe, North America, Fuel exporters, GCC); sheet Indicators.
- IMF_Financial_Soundness_Indicators.xlsx: sheet FSI_Quarterly (quarters "2001-Q1"...).
- BIS_credit_to_GDP.xlsx: sheets Credit_GDP_Quarterly and Credit_GDP_Annual; 3 rows per economy:
  CREDIT_GDP (ratio), CREDIT_GDP_TREND (one-sided HP trend; lambda 400,000 quarterly, 100,000 annual),
  CREDIT_GDP_GAP (ratio minus trend, pp). 44 economies.
- IMF_MFS_credit_to_GDP.xlsx: sheet Credit_GDP_Annual, same 3 rows, for Kuwait, United Arab
  Emirates, Qatar, Oman (IMF MFS credit / WEO annual GDP; lambda 100,000).

MAPPING
- WEO: growth = NGDP_RPCH; inflation = PCPIPCH; unemployment = LUR; debt = GGXWDG_NGDP; fiscal
  balance = GGXCNL_NGDP; current account = BCA_NGDPD; GDP US$ = NGDPD; GDP per capita = NGDPDPC;
  population = LP.
- FSI: capital adequacy / CAR = FSI688_CFSI_PT; Tier 1 = FSI626_CFSI_PT; CET1 = FSI15_CFSI_PT;
  NPL ratio = AQ12_CFSI_PT; provisions to NPL = AQ14_CFSI_PT; ROA = ROA_CFSI_PT; ROE = ROE_CFSI_PT;
  liquid assets to ST liabilities = FSI765_CFSI_PT; LCR = FSI288_CFSI_PT; NSFR = FSI289_CFSI_PT.
- Credit / credit-to-GDP / credit gap: Kuwait, UAE, Qatar, Oman -> MFS file (M); all others incl.
  Saudi Arabia -> BIS quarterly (CQ; CA if annual asked). Bahrain and others not listed: say not covered.
  GCC/Gulf = GCC column.
- Countries: match Economy (case-insensitive) or Economy code; US = United States, UK = United
  Kingdom, Turkey = Türkiye. Group members: codes from Groups. Group totals: Type "Aggregate" rows.
- Unclear request: ask one short question.

CHARTS: ALWAYS run this exact code, then call chart(rows, ...). Do not write your own plotting code.

import glob, re, textwrap, pandas as pd, matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
fs = glob.glob('/mnt/data/*.xlsx') + glob.glob('**/*.xlsx', recursive=True)
xl = lambda k, sh: pd.read_excel(next(p for p in fs if k in p), sheet_name=sh)
D, G = xl('World_Economic_Outlook', 'Data'), xl('World_Economic_Outlook', 'Groups')
F = xl('Financial_Soundness', 'FSI_Quarterly')
CQ, CA = xl('BIS_credit', 'Credit_GDP_Quarterly'), xl('BIS_credit', 'Credit_GDP_Annual')
M = xl('IMF_MFS_credit', 'Credit_GDP_Annual')

def chart(rows, start=2000, end=2031, kind='line', year=None):
    r0 = rows.iloc[-1]; P = int(r0['First projection year']) if 'First projection year' in rows else None
    per = [c for c in rows.columns if re.fullmatch(r'\d{4}(-Q\d)?', str(c)) and start <= int(str(c)[:4]) <= end]
    x = [int(c[:4]) + (int(c[-1]) - 1) / 4 if '-Q' in c else int(c) for c in per]
    V = rows[per].apply(pd.to_numeric, errors='coerce'); codes = list(rows['Indicator code'])
    many = rows['Indicator'].nunique() > 1; title = r0['Economy'] if many else r0['Indicator']
    L = r0['Source link']; src = f"Source: {r0['Citation']}. {L.rsplit('/', 1)[0] if '@' in L else L}"
    if kind == 'gap':
        fig, (ax, a2) = plt.subplots(2, 1, figsize=(10, 7.5), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
        for c, lab, ls in (('CREDIT_GDP', 'Credit-to-GDP ratio', '-'), ('CREDIT_GDP_TREND', 'Hodrick-Prescott trend', '--')):
            ax.plot(x, V.values[codes.index(c)], lw=2, ls=ls, label=lab)
        g = V.values[codes.index('CREDIT_GDP_GAP')]
        a2.bar(x, g, width=0.22 if '-Q' in per[0] else 0.8, color=['#c0392b' if v >= 0 else '#4B82AD' for v in g])
        for h in (2, 10): a2.axhline(h, color='grey', ls=':', lw=1)
        a2.axhline(0, color='black', lw=0.8); a2.set_ylabel('Gap, pp of GDP')
        a2.grid(alpha=0.3); a2.spines[['top', 'right']].set_visible(False); a2.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_ylabel('Percent of GDP'); ax.legend(frameon=False)
        title = f"{r0['Economy']}: credit-to-GDP ratio, trend and gap"
    else:
        fig, ax = plt.subplots(figsize=(10, 5.5))
    if kind == 'bar':
        n = V.notna().sum(); y = str(year) if year else (str(P - 1) if P else n[n >= 0.8 * n.max()].index[-1])
        s = rows.set_index('Economy')[y].dropna().sort_values()
        ax.barh(s.index, s.values, color='#2a6fb0'); ax.set_xlabel(r0['Unit'])
        title = f"{title}, {y}" + (' (IMF projection)' if P and int(y[:4]) >= P else '')
    elif kind == 'line':
        for lab, v in zip(rows['Indicator'] if many else rows['Economy'], V.values):
            ax.plot(x, v, lw=2, label=lab)
        if V.min().min() < 0 < V.max().max(): ax.axhline(0, color='black', lw=0.8)
        if P and x[-1] >= P:
            ax.axvspan(P - 0.5, x[-1] + 0.5, color='grey', alpha=0.15, zorder=0)
            ax.text(P, 0.98, ' IMF projections', transform=ax.get_xaxis_transform(), va='top', fontsize=9, color='dimgray')
        ax.set_ylabel(r0['Unit']); ax.legend(frameon=False); ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_title(title, loc='left', weight='bold', color='#4B82AD')
    ax.grid(alpha=0.3); ax.spines[['top', 'right']].set_visible(False)
    fig.text(0.01, 0.01, textwrap.fill(src, 150), fontsize=8, color='dimgray'); fig.tight_layout(rect=(0, 0.06, 1, 1)); plt.show()
Examples:
chart(D[(D['Economy']=='Kuwait') & (D['Indicator code']=='NGDP_RPCH')])
chart(F[F['Economy code'].isin(['KWT','SAU']) & (F['Indicator code']=='AQ12_CFSI_PT')], start=2010)
chart(M[M['Economy']=='Kuwait'], kind='gap')
chart(CQ[CQ['Economy']=='Saudi Arabia'], kind='gap')
Rankings or more than 10 economies: kind='bar'. ANY credit, credit-to-GDP or credit gap question: pass
all 3 rows of the economy with kind='gap' (top: ratio with Hodrick-Prescott trend; bottom: gap =
ratio minus trend). One chart per economy.

ANSWER: 1) chart(s); 2) 2-4 sentences with key numbers (say which years are IMF projections; for gaps
note Basel III thresholds 2 and 10 pp); 3) small table; 4) last line "Source: <Citation> - <Source link>"
from the rows used. Cite the original source, never the workbook. Missing data: say so, never fill gaps.
```

## Conversation starters

| Title | Message |
|---|---|
| Kuwait growth | Plot Kuwait real GDP growth since 2000 |
| G7 inflation | Compare inflation in the G7 countries since 2015 |
| Gulf banks | Compare nonperforming loan ratios in Kuwait, Saudi Arabia and the UAE |
| Bank capital | Rank G20 countries by bank regulatory capital to risk-weighted assets |
| Credit gap | Show Saudi Arabia's credit-to-GDP ratio, trend and gap |
| Kuwait credit gap | What is Kuwait's credit-to-GDP gap? |
| What's available | Which indicators and countries can you show? |

## About the "source" shown by Copilot

The agent's answers and charts cite the original source, for example
*"Source: International Monetary Fund, World Economic Outlook (April 2026) -
https://www.imf.org/external/datamapper/NGDP_RPCH@WEO/KWT"*. For the credit-to-GDP trend and gap the
citation says they are an own calculation (one-sided HP filter) based on BIS data.

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
  The latest year may be an IMF estimate.
- **Ratio = credit ÷ GDP × 100.** Trend: one-sided HP filter with λ = 100,000 (annual data), from 10
  years after the series start, so from 2011. Gap = ratio − trend.
- **Saudi Arabia** uses the BIS series, which is quarterly and starts in 1993; IMF MFS only has
  2022 onward. **Bahrain** has no IMF MFS data.
- **Oil prices:** Gulf GDP swings with oil prices, so the ratio jumps when oil prices fall
  (for example 2009, 2015 and 2020) even if credit growth is steady. Keep this in mind when
  reading the gap.

The code is in [`.github/skills/country-data/scripts/financial_data.py`](../.github/skills/country-data/scripts/financial_data.py)
(`hp_one_sided`, `credit_gap`, `credit_to_gdp_with_gap`, `fetch_fsi`). It can also be used on its own:

```
python .github/skills/country-data/scripts/financial_data.py credit --countries "SA,US" --out credit_gap.csv --plot gap.png
python .github/skills/country-data/scripts/financial_data.py credit --countries US --annual
python .github/skills/country-data/scripts/financial_data.py fsi --countries "KWT,SAU,ARE" --out fsi.csv
python .github/skills/country-data/scripts/financial_data.py mfs --out gulf_gap.csv --plot gulf.png
```

## Updating the data

The IMF publishes new WEO data in **April** and **October**; FSI and BIS data are updated quarterly.
To refresh all four files:

```
python m365-agent/build_data_file.py
```

It takes about 5 minutes. Then replace the files in the agent's knowledge, or overwrite the
OneDrive/SharePoint copies if you linked them from there.

## Limitations

- WEO data is annual; FSI and credit-to-GDP data are quarterly. No monthly data.
- Credit-to-GDP covers the 44 BIS economies plus Kuwait, the UAE, Qatar and Oman (IMF MFS). Bahrain is not covered.
- For World Bank indicators (life expectancy, CO2, ...) use the GitHub Copilot skill in this repo instead.
- Numbers are a snapshot as of the build date shown in each file's README sheet.
- The agent follows your organisation's Microsoft 365 policies. Sharing it with colleagues
  may be restricted by your admin.
