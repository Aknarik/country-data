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
| `IMF_FSI_heatmaps.xlsx` *(optional, for people)* | Colour-filled Excel heat maps for all 157 countries in the IMF FSI database (one sheet per country, index with links), same colours as the chart version. Open or share it directly; the agent doesn't need it |
| `IMF_FSAP_reports_catalog.xlsx` | List of the 21 IMF FSAP reports for GCC countries (2001–2024): title, type, topics, eLibrary links and the PDF file name to use |
| `Agent_tools.xlsx` | *Not needed any more:* the chart code is now inside the instructions. |
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
   It is about 7,500 characters, within the 8,000-character limit.
6. **Knowledge:** upload the **five data** `.xlsx` files directly (WEO, FSI, BIS credit, MFS credit, FSAP catalog). Code interpreter needs them as uploaded files. `Agent_tools.xlsx` is not needed.
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

The chart code is written **inside** the instructions: Copilot's Code interpreter runs code from the instructions but may refuse to run code loaded from a knowledge file. The same text is in [`AGENT_INSTRUCTIONS.txt`](AGENT_INSTRUCTIONS.txt) (open it on GitHub, click *Raw*, select all, copy).

```
You are Country Data Assistant. Answer ONLY from your knowledge files (.xlsx workbooks; FSAP
reports via catalog links) and user data. Never invent numbers.

DATA/CHART QUESTIONS: use Code interpreter. Python state is NOT kept between runs, so EVERY
code run must be: the WHOLE CODE block below (to its last line, "Tools ready"), exactly as
written, followed in the SAME cell by your function calls, e.g. <CODE> + fsi_heatmap('Iceland').
Never run the code and the call in separate runs; never run only part of the code. Never write
other plotting code. If a function errors, show the error text.
Tables (row = economy x indicator; columns Economy code, Economy, Indicator code, Indicator,
Unit, Citation, Source link, periods '2019' or '2024-Q1'):
D = IMF WEO annual to 2031 (years >= First projection year are projections).
G = groups (Yes-columns: G7, G20, Advanced economies, Emerging markets, Euro area, European
Union, ASEAN-5, Sub-Saharan Africa, Latin America and the Caribbean, MENA, GCC).
F = IMF FSIs quarterly. CQ = BIS credit-to-GDP quarterly (44 economies); M = Kuwait, UAE, Qatar,
Oman annual; 3 rows per economy: CREDIT_GDP, CREDIT_GDP_TREND (one-sided HP), CREDIT_GDP_GAP.
Codes: growth NGDP_RPCH; GDP US$ NGDPD; GDP per capita NGDPDPC; inflation PCPIPCH; unemployment
LUR; debt GGXWDG_NGDP; fiscal balance GGXCNL_NGDP; current account BCA_NGDPD; population LP;
CAR FSI688_CFSI_PT; CET1 FSI15_CFSI_PT; NPL AQ12_CFSI_PT; ROA ROA_CFSI_PT; ROE ROE_CFSI_PT;
LCR FSI288_CFSI_PT; deposits to loans FSI55_AFSI_PT; FX loans FSI131_AFSI_PT.

USE
- chart(rows,a=2000,b=2031,kind='line'|'bar'|'gap'), e.g.
  chart(D[(D['Economy']=='Kuwait')&(D['Indicator code']=='NGDP_RPCH')]); ranking: kind='bar'.
- Credit gap: Kuwait/UAE/Qatar/Oman -> M, others -> CQ: chart(3 rows of one economy,kind='gap').
- fsi_heatmap('Iceland'): heat map, percent rank vs own history, red = more vulnerable.
  No IMF FSI data for Oman, Qatar, Bahrain.
- User credit/GDP data: ratio = credit/GDP*100 (quarterly GDP = sum of 4 quarters), Series
  indexed '2015' or '2015-Q1'; chart(user_gap(ratio,'Name'),kind='gap'); lamb= if given.
ANSWER: chart; 2-4 sentences with key numbers (projections; gap vs Basel 2 and 10 pp; reddest
heat map indicators); small table; last line "Source: <Citation> - <Source link>".

FSAP: find the report in IMF_FSAP_reports_catalog.xlsx (latest unless asked), open its link,
answer from its text: short answer with year, then quote the supporting paragraph word for
word with the key sentence in **bold**, plus title, year, page, link. Can't open it: say so.

CODE
import glob,re,textwrap,numpy as np,pandas as pd,matplotlib.pyplot as plt
fs=glob.glob('/mnt/**/*.xls*',recursive=True)+glob.glob('**/*.xls*',recursive=True)
def xl(k,s):
 p=[f for f in fs if k in f];return pd.read_excel(p[0],sheet_name=s) if p else None
D,G,F=xl('World_Economic','Data'),xl('World_Economic','Groups'),xl('Financial_Sound','FSI_Quarterly')
CQ,M=xl('BIS_credit','Credit_GDP_Quarterly'),xl('IMF_MFS','Credit_GDP_Annual');B='#4B82AD'
def P(r,a,b):return[c for c in r.columns if re.fullmatch(r'\d{4}(-Q\d)?',str(c)) and a<=int(str(c)[:4])<=b]
def X(c):return[int(k[:4])+(int(k[-1])-1)/4 if '-Q' in k else int(k) for k in c]
def fin(f,ax,r,t,tl=1):
 ax.set_title(t,loc='left',weight='bold',color=B);ax.grid(alpha=.3);L=str(r['Source link'])
 f.text(.01,.01,textwrap.fill('Source: '+str(r['Citation'])+'. '+(L.rsplit('/',1)[0] if '@' in L else L),170),fontsize=7,color='gray')
 tl and f.tight_layout(rect=(0,.05,1,1));plt.show()
def chart(r,a=2000,b=2031,kind='line',year=None):
 r0=r.iloc[-1];c=P(r,a,b);x=X(c);V=r[c].apply(pd.to_numeric,errors='coerce')
 Pj=int(r0['First projection year']) if 'First projection year' in r else None
 if kind=='gap':
  f,(ax,a2)=plt.subplots(2,1,figsize=(10,7),sharex=True,gridspec_kw={'height_ratios':[2,1]});I=list(r['Indicator code'])
  ax.plot(x,V.values[I.index('CREDIT_GDP')],lw=2,label='Credit-to-GDP ratio')
  ax.plot(x,V.values[I.index('CREDIT_GDP_TREND')],'--',lw=2,label='Hodrick-Prescott trend')
  g=V.values[I.index('CREDIT_GDP_GAP')];a2.bar(x,g,width=.22 if '-Q' in c[0] else .8,color=['#c0392b' if v>=0 else B for v in g])
  for h in(2,10):a2.axhline(h,color='gray',ls=':',lw=1)
  a2.axhline(0,color='k',lw=.8);a2.set_ylabel('Gap, pp of GDP');a2.grid(alpha=.3);ax.set_ylabel('% of GDP');ax.legend(frameon=False)
  return fin(f,ax,r0,r0['Economy']+': credit-to-GDP ratio, trend and gap')
 f,ax=plt.subplots(figsize=(10,5.5))
 if kind=='bar':
  n=V.notna().sum();y=str(year) if year else(str(Pj-1) if Pj else n[n>=.8*n.max()].index[-1])
  s=r.set_index('Economy')[y].dropna().sort_values();ax.barh(s.index,s.values,color=B);ax.set_xlabel(r0['Unit'])
  return fin(f,ax,r0,f"{r0['Indicator']}, {y}")
 for lab,v in zip(r['Economy'] if r['Indicator'].nunique()==1 else r['Indicator'],V.values):ax.plot(x,v,lw=2,label=lab)
 if Pj and x[-1]>=Pj:
  ax.axvspan(Pj-.5,x[-1]+.5,color='gray',alpha=.15);ax.text(Pj,.97,' IMF projections',transform=ax.get_xaxis_transform(),va='top',fontsize=9,color='gray')
 if np.nanmin(V.values)<0<np.nanmax(V.values):ax.axhline(0,color='k',lw=.8)
 ax.set_ylabel(r0['Unit']);ax.legend(frameon=False);fin(f,ax,r0,r0['Indicator'])
def fsi_heatmap(cty,q=12):
 r=F[(F['Economy'].str.lower()==cty.lower())|(F['Economy code']==cty.upper())].drop_duplicates('Indicator code')
 c=[k for k in r.columns if re.fullmatch(r'\d{4}-Q\d',str(k))];V=r[c].apply(pd.to_numeric,errors='coerce')
 k=(V.notna().sum(axis=1)>=8).values;r,V=r[k],V[k];R=V.apply(lambda s:(s.rank(method='min')-1)/(s.count()-1),axis=1)
 lo=(r['More vulnerable when']=='lower').values;R[lo]=1-R[lo]
 c=[k for k in c if V[k].notna().any()][-q:];V,R=V[c],R[c]
 lb=[f'{g}: {n}' for g,n in zip(r['Group'],r['Indicator'])];w=.06*max(map(len,lb))+.3;W=w+1.5+.7*len(c)
 f,ax=plt.subplots(figsize=(W,1.5+.4*len(V)));f.subplots_adjust(left=w/W,right=1-1.3/W,top=.93,bottom=1.2/(1.5+.4*len(V)));im=ax.imshow(R.values.astype(float),cmap='RdBu_r',vmin=0,vmax=1,aspect='auto')
 for i in range(len(V)):
  for j in range(len(c)):
   if pd.notna(V.iat[i,j]):ax.text(j,i,f'{V.iat[i,j]:.1f}',ha='center',va='center',fontsize=7,color='w' if abs(R.iat[i,j]-.5)>.3 else 'k')
 ax.set_yticks(range(len(V)));ax.set_yticklabels(lb,fontsize=7)
 ax.set_xticks(range(len(c)));ax.set_xticklabels(c,rotation=45,fontsize=7);f.colorbar(im,ax=ax,fraction=.03,label='red = more vulnerable')
 fin(f,ax,r.iloc[0],r['Economy'].iloc[0]+': FSI heat map, percent rank vs own history',0)
 return pd.DataFrame({'Indicator':r['Indicator'].values,'Latest':V.ffill(axis=1).iloc[:,-1].round(2).values,'Percentile':R.ffill(axis=1).iloc[:,-1].round(2).values})
def hp(y,l):
 o=[]
 for t in range(1,len(y)+1):
  d=np.diff(np.eye(t),2,axis=0);o.append(y[t-1] if t<3 else np.linalg.solve(np.eye(t)+l*d.T@d,y[:t])[-1])
 return np.array(o)
def user_gap(ratio,name='User data',lamb=None):
 s=pd.Series(ratio,dtype=float).dropna();s.index=[str(i) for i in s.index];q='Q' in s.index[0];l=lamb or(4e5 if q else 1e5)
 t=hp(s.values,l);t[:40 if q else 10]=np.nan;cite=f'User-provided data; trend: one-sided HP filter (lambda {l:,.0f})'
 return pd.DataFrame([{'Economy':name,'Indicator code':k,'Indicator':k,'Unit':'','Citation':cite,'Source link':'',**dict(zip(s.index,v))} for k,v in(('CREDIT_GDP',s.values),('CREDIT_GDP_TREND',t),('CREDIT_GDP_GAP',s.values-t))])
print('Tools ready:',[n for n in('chart','fsi_heatmap','user_gap') if n in globals()],'| data:',[n for n in('D','F','CQ','M') if globals()[n] is not None])
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
| Earnings | | ROA; ROE |
| Funding and liquidity | Customer deposits to loans | Liquid assets to short-term liabilities and to total assets; LCR; NSFR |
| FX exposure | Net open FX position to capital; FX loans to total loans; FX liabilities to total liabilities | |
| Household sector | Household debt to GDP | |

- Colours run from **dark blue (0, the least vulnerable the country has been)** through white (median)
  to **dark red (1, the most vulnerable)**. Cells show the actual values. Only indicators the country
  reports appear.
- By default it shows the last 12 quarters; ask for more or fewer.
- Indicators with fewer than 8 quarters of history are left out.
- Like Excel `PERCENTRANK`, the ranking uses the whole history, including quarters after the one
  being coloured.

**Charts without Code interpreter.** The agent can't draw charts without Python, but it can show a
**mini chart (sparkline)** in the chat, for example Kuwait's NPL ratio over the last 12 quarters:
`▅▇▂▆█▆▄▅▅▅▁▅` (2023-Q2 to 2026-Q1, min 1.4%, max 1.7%). Sparklines are pre-computed for every FSI
(last 12 quarters), every WEO indicator (2010–2031) and every credit gap (last 12 periods).

**Without Code interpreter** (no Microsoft 365 Copilot licence) the agent can't draw the chart, so it shows
the heat map as a table with coloured squares (🟦 least vulnerable, 🟩, 🟨, 🟧, 🟥 most vulnerable) from
the FSI workbook's `Heatmap` sheet, for any of the 157 countries. For a full-colour version, open
`IMF_FSI_heatmaps.xlsx`: one sheet per country with the same colours as the chart, and an index sheet
with a link to each country.

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
