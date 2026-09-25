---
name: country-data
description: Fetch, tabulate and chart economic and development data for any country or country group (G7, G20, euro area, advanced economies, emerging markets, ASEAN, Sub-Saharan Africa, world...). Uses the public IMF World Economic Outlook (GDP growth, inflation, unemployment, government debt, fiscal balance, current account, GDP per capita, with projections) and World Bank WDI (~1,500 indicators such as population, life expectancy, CO2, electricity access, poverty). Use whenever the user asks for a country's or group's data, a comparison between countries, a ranking, or a chart/plot of macro or development indicators.
---

# Country data (IMF WEO + World Bank WDI)

One script does everything: `scripts/country_data.py` (next to this file).
It understands plain-language country names, group names and indicator phrases,
prints a table, saves the data as CSV and saves a PNG chart.

## Setup (only if the script fails with `ModuleNotFoundError`)

```
python -m pip install -r <this-skill-dir>/scripts/requirements.txt
```

## Main workflow

Turn the user's request into ONE `show` call:

```
python <this-skill-dir>/scripts/country_data.py show --what "<indicator phrase or code>" --countries "<countries/groups>" [--start YYYY] [--end YYYY]
```

- `--what`: pass the user's own words (`"gdp growth"`, `"inflation"`, `"government debt"`,
  `"unemployment"`, `"current account"`, `"gdp per capita"`, `"population"`,
  `"life expectancy"`, `"co2 emissions"`, `"access to electricity"`...) or an exact code
  (`NGDP_RPCH`, `SP.POP.TOTL`). The source (IMF or World Bank) is picked automatically.
- `--countries`: pass the names exactly as the user wrote them, comma-separated. Accepted:
  - country names or ISO3 codes, including common forms: `US`, `UK`, `South Korea`,
    `Russia`, `Turkey`, `Ivory Coast`, `DRC`; small typos are tolerated
  - groups, expanded to member countries: `G7`, `G20`, `advanced economies`,
    `emerging markets`, `developing countries`, `low income countries`, `euro area`,
    `EU`, `ASEAN`, `Sub-Saharan Africa`, `Latin America`, `MENA`, `HIPC`...
  - `world` gives the world aggregate series; `all` gives every country
  - aggregate series codes, when the user wants the group total rather than its
    members: IMF `EURO`, `ADVEC`, `OEMDC`, `WEOWORLD`; World Bank `EUU`, `SSF`, `WLD`...
- Optional: `--start/--end` years (default start 2000), `--kind line|bar`,
  `--top N` (bar charts), `--year YYYY` (ranking year), `--xlsx`,
  `--outdir <folder>` (default `./country_data_output`).
- Chart choice is automatic: 12 or fewer economies gives a line chart (with the IMF
  projection years shaded); more gives a ranking bar chart for the latest actual year.
  Use `--kind line` for a group's trend over time (it draws each member plus the median).

### Reading the output

The script prints:
1. `Indicator :` the indicator it chose, plus `other matches` if the phrase was ambiguous
2. how each name or group was understood (on stderr), e.g. `G7 -> WEO group 'G7' (7 countries)`
3. a table (last 12 years), or for many countries a top-10 / bottom-5 ranking and the median
4. `Data saved :` and `Chart saved:` absolute paths

## Respond to the user with

- the key numbers from the table, summarised in a sentence or two (mention that
  IMF years from the current year onward are **projections**)
- the table (as markdown if short)
- the chart: link or embed the PNG path from `Chart saved:`, plus the CSV path
- the indicator and source used; if `other matches` looks like a better fit for what
  the user meant, say so and offer to rerun with that code

## When something is unclear or fails

- `ERROR: Could not recognise: 'X' (did you mean ...)`: rerun with the suggested
  name, or look it up: `country_data.py countries --search <text>` / `country_data.py groups`
- The wrong indicator was picked: search, then rerun with the exact code:
  `country_data.py indicators --source imf --search <words>` (about 130 IMF macro series)
  `country_data.py indicators --source wb --search <words>` (about 1,500 World Bank series)
- Check how names are understood without fetching: `country_data.py resolve --countries "..."`
- Full definition of an indicator: `country_data.py info --what <code or phrase>`
- `no data for N of M` means some countries have no values for that indicator; this is normal.
- Metadata is cached for 7 days in `~/.country_data_cache`. Delete that folder if
  lists look stale.

## Examples

| User asks | Command |
|---|---|
| "GDP growth in France and Germany since 2010" | `show --what "gdp growth" --countries "France, Germany" --start 2010` |
| "Plot inflation for the G7" | `show --what inflation --countries G7` |
| "Which emerging markets have the highest debt?" | `show --what "government debt" --countries "emerging markets" --kind bar --top 20` |
| "Euro area unemployment vs the US" (aggregate) | `show --what unemployment --countries "EURO, US"` |
| "Life expectancy in Nigeria, Kenya and Ghana" | `show --what "life expectancy" --countries "Nigeria, Kenya, Ghana"` |
| "World GDP growth forecast" | `show --what "gdp growth" --countries world --start 2015` |
| "Rank all countries by GDP per capita in 2023" | `show --what "gdp per capita" --countries all --year 2023 --top 30` |
