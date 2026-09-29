# Country Data agent without a Microsoft 365 Copilot licence

Use this version if your agent has **no Code interpreter** (no *Capabilities* section in the agent
builder, or the agent says Python is not available). The agent answers from **Markdown documents**
that already contain every table, heat map and mini chart, so it only has to find and copy them.
Without Python, Copilot searches its files instead of computing, and it finds text documents far
more reliably than large spreadsheets.

With a Microsoft 365 Copilot licence, use [AGENT_SETUP.md](AGENT_SETUP.md) instead, which adds real charts.

## What the agent can do

- **Macro data** for about 200 countries: IMF World Economic Outlook, 2019–2031 (projections marked),
  with a text mini chart of 2010–2031 (`▂█▇▄▄▄▅▁▅▄▁▄`)
- **Financial soundness heat map** for 157 countries: last 8 quarters as coloured squares
  (🟦 least vulnerable … 🟥 most vulnerable vs the country's own history), mini chart, latest value and
  vulnerability percentile
- **Credit-to-GDP gap**: ratio, one-sided Hodrick–Prescott trend and gap for the 44 BIS economies,
  plus Kuwait, UAE, Qatar and Oman (IMF data)
- **World and regional totals**
- **IMF FSAP reports** for the GCC countries: answers with quoted paragraphs and links

**Not possible without a licence:** real charts (images), and calculations on your own pasted data.

## Files to upload (7)

Download **[knowledge_md.zip](knowledge_md.zip)** (on GitHub: open it → *Download raw file*) and unzip it:

1. `Country_profiles_Africa.md`
2. `Country_profiles_Asia_and_Pacific.md`
3. `Country_profiles_Europe.md`
4. `Country_profiles_Middle_East_and_Central_Asia.md`
5. `Country_profiles_Western_Hemisphere.md`
6. `World_and_regional_aggregates.md`
7. `IMF_FSAP_reports_catalog.md`

If the agent builder won't accept `.md` files, use **[knowledge_txt.zip](knowledge_txt.zip)**. It has
the same seven files as `.txt`.

## Step by step

1. Open the agent → **Edit** → **Configure** (or **Create agent** for a new one).
2. **Knowledge:**
   - **Remove all `.xlsx` files.** Without Python they only get in the way of the search.
   - **Upload the 7 files** above.
   - Add the website `https://www.elibrary.imf.org` if website knowledge is offered (for FSAP reports).
   - Turn on **Only use specified sources** if the option exists.
3. **Instructions:** delete everything and paste the box below (about 3,100 characters).
4. **Conversation starters** (optional):
   - *Kuwait economy*: `Show Kuwait's key macroeconomic indicators`
   - *Kuwait heat map*: `Show the financial soundness heat map for Kuwait`
   - *NPL trend*: `Plot the NPL ratio for Kuwait`
   - *Credit gap*: `What is Saudi Arabia's credit-to-GDP gap?`
   - *Compare*: `Compare inflation in Kuwait, Qatar and the UAE`
   - *FSAP*: `What were the main recommendations of Kuwait's latest FSAP?`
5. Click **Update** (or **Create**). Wait until every file shows as processed.
6. Open a **new chat** and test with the questions below.

## Instructions (paste into the agent)

```
You are Country Data Assistant for macroeconomic and financial-stability data. Answer ONLY from
your knowledge files; never use other sources, memory or estimates.

FILES
- Country_profiles_<region>.md (Africa, Asia_and_Pacific, Europe, Middle_East_and_Central_Asia,
  Western_Hemisphere): one section per country, titled "<Country> (<ISO3>) - country profile", with:
  (1) "<Country> - macroeconomic indicators": IMF WEO table 2019-2031 (years from the stated year
      are IMF projections) and a mini chart 2010-2031;
  (2) "<Country> - financial soundness indicators heat map": IMF FSIs for the last 8 quarters with
      coloured squares, mini chart, latest value and vulnerability percentile;
  (3) "<Country> - credit-to-GDP ratio, Hodrick-Prescott trend and credit gap".
- World_and_regional_aggregates.md: world and group totals.
- IMF_FSAP_reports_catalog.md: IMF FSAP reports for GCC countries with links.

DATA QUESTIONS
1. Find the country's section (name or ISO3 code; US = United States, UK = United Kingdom,
   Turkey = Türkiye, South Korea = Korea).
2. Copy the needed rows EXACTLY: numbers, coloured squares and mini-chart characters. Never
   recompute, re-round, interpolate or estimate. If a value is missing, say so.
3. "Plot", "chart", "trend": show the rows with their mini chart (▁ low to █ high) and key values;
   say it is a text mini chart.
4. "Heat map", "FSI", "banking vulnerabilities": show the heat map table grouped by Group with the
   legend (🟦 least vulnerable, 🟩, 🟨, 🟧, 🟥 most vulnerable vs own history), then name the reddest
   indicators in the latest quarter.
5. "Credit gap": show the credit table and gap mini chart; mention the Basel III guide (gap above
   2 pp: buffer build-up; above 10 pp: maximum buffer).
6. Comparisons: take each country's section and put the rows side by side.
7. End with the Source line printed under the table you used.

FSAP QUESTIONS
- Find the report in IMF_FSAP_reports_catalog.md (latest relevant one unless asked otherwise),
  open it through its PDF link or eLibrary link, and answer from its text.
- Format: (1) short direct answer with the report year; (2) Evidence: quote the relevant paragraph
  word for word as a quote block, with the sentence that justifies the answer in **bold**; under it
  give report title, publication year, page or paragraph number and the link.
- If you cannot open the report, say so and give its link; never answer from memory.

If a country or indicator is not in the files, say it is not covered. Keep answers concise.
```

## Test questions and expected answers

| Ask | Expected |
|---|---|
| *Show Kuwait's key macroeconomic indicators* | Table 2019–2031; real GDP growth 2025 = 3.5, 2026 = −0.6 (projection) |
| *Plot the NPL ratio for Kuwait* | Mini chart `▅▇▂▆█▆▄▅▅▅▁▅`, latest 1.6% (2026-Q1) |
| *Show the financial soundness heat map for Kuwait* | Squares table; reddest: Tier 1 capital to assets and FX loans to total loans (percentile 1.00) |
| *What is Kuwait's credit-to-GDP gap?* | 2025: ratio 104.4, trend 104.0, gap 0.4 pp |
| *What were the main recommendations of Kuwait's latest FSAP?* | 2018 FSSA; quoted paragraphs with bold key sentences and the link |

If an answer differs, send me the agent's reply.

## Refreshing the data

```
python m365-agent/build_data_file.py          # download the latest data (about 5 minutes)
python m365-agent/build_markdown_knowledge.py # rebuild the Markdown files and zips
python m365-agent/test_markdown_knowledge.py  # check every file against the data
```

Then replace the 7 files in the agent's Knowledge.
