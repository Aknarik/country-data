# Country data and Copilot agents

Python that downloads public IMF/BIS/central bank data, builds Excel knowledge files and the instructions
of Microsoft 365 Copilot agents (charts drawn by Code interpreter).

## Everyday commands
- Routine when asked to "update": run `python update_all.py` (add `--imf` / `--local` if new releases or
  files), then tell the user the "RE-UPLOAD IN COPILOT" list it prints (agent -> instructions / files).
- Update everything quickly: `python update_all.py` (central bank bulletins + agents)
- With new IMF/BIS releases: `python update_all.py --imf`; new iMaPP or bank data files: `--local`
- Only agents after editing rules/code: `python update_all.py --agents`
- Review charts: `python m365-agent/agents/kuwait_check.py` then `python m365-agent/agents/review_report.py`

## Layout
- `m365-agent/build_data_file.py` IMF WEO, FSI, MFS, BIS workbooks; `build_gcc_central_banks.py` CBK/SAMA/CBO/CBB;
  `build_local_sources.py` iMaPP; `recompute_credit_gaps.py` gaps from stored ratios
- `m365-agent/agents/`: `common.py` (shared chart code), `*_code.py` + `*_rules.txt` per agent,
  `build_agents.py` -> `<agent>/INSTRUCTIONS.txt`, `test_agents.py`, `build_package.py` -> `copilot_agents_package/`
- `.github/skills/country-data/scripts/financial_data.py`: data library (HP filter, MFS, BIS, FSI)

## Rules
- Each agent's INSTRUCTIONS.txt must stay under 8,000 characters (build_agents.py checks; keep a margin).
- Charts: title "Country: Indicator (unit)" in IMF blue #4B82AD, latest value at line ends, legend below,
  projections shaded grey, "percent" not "%", source line = official source (never file names).
- Credit gap: one-sided HP from the series start, lambda 400,000 quarterly / 1,562.5 annual, no gap under 20 years.
- After any change: run tests, rebuild the package, commit with a clear message.
- Never commit `local_data/`, `m365-agent/private/`, `copilot_agents_package/`, `*.xlsm`, `iMaPP_database*`
  (all git-ignored); check `git status` before every push.
