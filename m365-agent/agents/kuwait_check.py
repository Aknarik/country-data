import os, shutil, tempfile, matplotlib, re
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
import test_agents as ta
HERE = Path(__file__).parent; OUT = HERE / "test_output" / "kuwait"; OUT.mkdir(parents=True, exist_ok=True)
CHECKS = {"1_WEO_outlook": [("weo_growth", "line(weo('Kuwait','NGDP_RPCH'))"),
                            ("weo_gcc_debt", "line(weo(members('GCC'),'GGXWDG_NGDP'),2010)"),
                            ("weo_rank", "bar(weo(members('GCC'),'NGDP_RPCH'),2026,hl='Kuwait')"),
                            ("weo_dash", "dashboard('Kuwait')"), ("weo_table", "table(weo('KWT',['NGDP_RPCH','PCPIPCH','GGXCNL_NGDP']),range(2023,2029))")],
          "2_Credit_gap_macroprudential": [("gap", "gap('KWT')"), ("gap_nonoil", "gap(user_gap({'2024':47247},{'2024':27707},'Kuwait (non-oil GDP)'),mpp=False)"),
                            ("sectors", "sectors('KWT')"), ("mpp", "mpp_table('KWT')"),
                            ("defs", "print(T('iMaPP','Definitions').query('`Tool code` in [\"LTV\",\"DSTI\"]').iloc[:,:3].to_string())"),
                            ("lambda", "r=gap_rows if False else M[M['Economy code']=='KWT'];print(r['Method'].iloc[0])")],
          "3_Financial_soundness": [("dash", "dashboard('KWT')"), ("heat", "heatmap('Kuwait')"),
                            ("nexus", "ts('Bk','KWT',['BANK_GOV_TA','BANK_GOV_GDP'],'Sovereign-bank nexus')"),
                            ("liab", "ts('Bk','KWT',['BANK_DEPOSITS_TA','BANK_EQUITY_TA','BANK_FOREIGN_LIAB_TA'],'Bank funding structure')"),
                            ("npl", "ts('F','KWT',['AQ12_CFSI_PT'],'Nonperforming loans')"),
                            ("dirs", "r=get('F','KWT').drop_duplicates('Indicator code');print(r[['Group','Indicator','More vulnerable when']].to_string(index=False))")],
          "5_Banks_balance_sheets": [("loans_bar", "structure('KWT')"), ("loans_pie", "structure('KWT',kind='pie',year=2025)"),
                            ("assets", "structure('KWT','assets')"), ("growth", "growth('KWT')")]
          + [(f"bank_{k}", f"banks('KWT','{k}')") for k in ("T1", "LIQ", "NPLNET", "TCE", "ROAA")]}
for agent, calls in CHECKS.items():
    code = (HERE / agent / "INSTRUCTIONS.txt").read_text(encoding="utf-8").split("CODE\n", 1)[1]
    box = Path(tempfile.mkdtemp()); [shutil.copy(ta.ROOT / f, box) for f in ta.KNOW[agent]]; os.chdir(box)
    for name, call in calls:
        titles = []
        def show(name=name):
            f = plt.gcf()
            for ax in f.axes:
                t = ax.title
                if t.get_text(): titles.append((t.get_text(), matplotlib.colors.to_hex(t.get_color())))
            if f._suptitle: titles.append((f._suptitle.get_text(), matplotlib.colors.to_hex(f._suptitle.get_color())))
            f.savefig(OUT / f"{agent[0]}_{name}.png", dpi=65); plt.close("all")
        plt.show = show
        print(f"\n### {agent[0]} {name}: {call[:80]}")
        try:
            exec(code + "\n" + call, {})
        except Exception as e:
            print(f"   ERROR {type(e).__name__}: {e}")
        for t, c in titles:
            print(f"   title {c} {'lowercase!' if t[0].islower() else ''} {t[:90]}")
