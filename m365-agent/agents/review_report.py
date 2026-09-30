"""Build a local HTML page with every test chart, to review the agents' output.

Run kuwait_check.py (and/or test_agents.py) first, then:  python m365-agent/agents/review_report.py
The page stays on this computer (test_output/ is git-ignored) because bank-by-bank charts are confidential.
"""
import base64, html, os, sys, webbrowser
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "test_output"
AGENTS = {"1": "WEO Economic Outlook", "2": "Credit Gap & Macroprudential", "3": "Banking Sector (IMF internal)"}
CAPTIONS = {
    "weo_growth": "Real GDP growth: actual solid, projections dashed on grey band",
    "weo_gcc_debt": "GCC government debt comparison",
    "weo_rank": "Growth ranking in the GCC (projection year hatched, Kuwait highlighted)",
    "weo_dash": "Six-panel macro dashboard",
    "gap": "Credit-to-GDP ratio, HP trend, gap, Basel range, iMaPP action years",
    "gap_nonoil": "Own-data gap (credit / non-oil GDP) - test series",
    "dash": "Banking sector dashboard", "heat": "FSI heat map (red = more vulnerable)",
    "loans_bar": "Loan portfolio by sector (stacked)", "loans_pie": "Loan portfolio, one year (pie)",
    "assets": "Bank asset structure", "nexus": "Sovereign-bank nexus",
    "liab": "Funding structure: deposits, equity, foreign liabilities", "npl": "Nonperforming loans",
    "bank_T1": "Bank by bank: Tier 1 capital", "bank_LIQ": "Bank by bank: liquidity",
    "bank_NPLNET": "Bank by bank: asset quality", "bank_TCE": "Bank by bank: leverage",
    "bank_ROAA": "Bank by bank: income (ROAA)",
}


def build(folder):
    imgs = sorted(folder.glob("*.png"))
    parts = []
    for num, name in AGENTS.items():
        cards = []
        for p in [i for i in imgs if i.name.startswith(num + "_")]:
            key = p.stem.split("_", 1)[1]
            data = base64.b64encode(p.read_bytes()).decode()
            cap = html.escape(CAPTIONS.get(key, key))
            cards.append(f'<figure><a href="data:image/png;base64,{data}" target="_blank">'
                         f'<img src="data:image/png;base64,{data}" alt="{cap}"></a>'
                         f'<figcaption><b>{cap}</b><br><span>{p.name}</span>'
                         f'<label><input type="checkbox"> OK</label>'
                         f'<textarea placeholder="What to improve?"></textarea></figcaption></figure>')
        if cards:
            parts.append(f"<h2>Agent {num}: {html.escape(name)}</h2><div class=grid>{''.join(cards)}</div>")
    page = f"""<!doctype html><html><head><meta charset=utf-8><title>Agent chart review</title>
<style>
:root{{--blue:#4B82AD;--bg:#f6f8fa;--card:#fff;--text:#1f2328;--muted:#656d76}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0d1117;--card:#161b22;--text:#e6edf3;--muted:#8b949e}}}}
body{{margin:0;padding:16px 24px;background:var(--bg);color:var(--text);font:14px system-ui,sans-serif}}
h1,h2{{color:var(--blue)}} .note{{color:#c0392b;font-weight:bold}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:16px}}
figure{{margin:0;background:var(--card);border-radius:8px;padding:10px;box-shadow:0 1px 3px #0003}}
img{{width:100%;background:#fff;border-radius:4px}} figcaption span{{color:var(--muted);font-size:12px}}
label{{float:right}} textarea{{width:100%;box-sizing:border-box;margin-top:6px;min-height:40px}}
</style></head><body><h1>Agent chart review: {html.escape(folder.name.title())}</h1>
<p>Click a chart to open it full size. Tick OK or write what to improve (notes stay in this browser tab only;
copy them into the chat). <span class=note>Bank-by-bank charts are CONFIDENTIAL - IMF internal use only; do not share this file.</span></p>
{''.join(parts)}</body></html>"""
    out = folder / "review.html"
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    folder = OUT / (sys.argv[1] if len(sys.argv) > 1 else "kuwait")
    page = build(folder)
    print(page)
    webbrowser.open(page.as_uri())
