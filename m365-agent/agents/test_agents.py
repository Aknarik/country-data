"""Run each agent's INSTRUCTIONS code in a fresh sandbox holding only that agent's knowledge files."""
import os, shutil, sys, time, tempfile, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
HERE = Path(__file__).parent; ROOT = HERE.parent.parent
KNOW = {"1_WEO_outlook": ["m365-agent/IMF_World_Economic_Outlook_data.xlsx"],
        "2_Credit_gap_macroprudential": ["m365-agent/BIS_credit_to_GDP.xlsx", "m365-agent/IMF_MFS_credit_to_GDP.xlsx",
                                         "m365-agent/IMF_iMaPP_macroprudential.xlsx"],
        "3_Banking_sector": ["m365-agent/IMF_Financial_Soundness_Indicators.xlsx", "m365-agent/IMF_MFS_banking_sector.xlsx",
                             "local_data/HEAT_bank_distribution.xlsx"]}
TESTS = {"1_WEO_outlook": ["line(weo('Kuwait','NGDP_RPCH'))", "line(weo(members('GCC'),'GGXWDG_NGDP'),2010)",
                           "line(weo('SAU',['GGXCNL_NGDP','BCA_NGDPD']))", "bar(weo(members('GCC'),'NGDP_RPCH'),2026,hl='Kuwait')",
                           "bar(weo(members('G20'),'PCPIPCH'))", "table(weo(members('GCC'),'NGDP_RPCH'),range(2022,2028))",
                           "dashboard('Kuwait')", "dashboard('Qatar')", "line(weo(['Euro area','USA'],'NGDP_RPCH'))"],
         "2_Credit_gap_macroprudential": ["gap('KWT')", "gap('GBR')", "gap('Saudi Arabia')", "sectors('GBR')", "mpp_table('KWT')",
                                          "import numpy as np;cr={str(y):v for y,v in zip(range(2001,2026),np.linspace(20000,47247,25))};g={str(y):v for y,v in zip(range(2001,2026),np.linspace(12000,27707,25))};gap(user_gap(cr,g,'Kuwait (non-oil GDP)'),mpp=False)",
                                          "gap(user_gap({f'{2005+i//4}Q{i%4+1}':60+i*.3+np.sin(i/5)*4 for i in range(80)},name='KWT'))"],
         "3_Banking_sector": ["dashboard('KWT')", "dashboard('OMN')", "dashboard('GBR')", "heatmap('Kuwait')", "heatmap('BHR')",
                              "ts('F','KWT',['AQ12_CFSI_PT','AQ14_CFSI_PT'],'asset quality')", "ts('Bk','SAU',['BANK_GOV_TA','BANK_GOV_GDP'],'sovereign-bank nexus')",
                              "ts('H','KWT',['HEAT_T1_MED','HEAT_T1_AW'],'Tier 1 ratio across banks')", "structure('OMN')", "structure('SAU',kind='pie',year=2025)",
                              "structure('KWT','assets')", "structure('ARE','assets','pie',2024)", "structure('GBR')", "banks('KWT')", "banks('SAU','NPLNET',2024)"]}
out = HERE / "test_output"; out.mkdir(exist_ok=True)
for agent, files in KNOW.items():
    code = (HERE / agent / "INSTRUCTIONS.txt").read_text(encoding="utf-8").split("CODE\n", 1)[1]
    box = Path(tempfile.mkdtemp()); [shutil.copy(ROOT / f, box) for f in files]; os.chdir(box)
    for i, call in enumerate(TESTS[agent]):
        n = [0]; plt.show = lambda: (n.__setitem__(0, n[0] + 1), plt.savefig(out / f"{agent[:1]}_{i}.png", dpi=65), plt.close("all"))
        t = time.time()
        try:
            exec(code + "\n" + call, {}); print(f"OK   {agent[:12]} {call[:70]:70} {time.time()-t:4.1f}s charts={n[0]}")
        except Exception as e:
            print(f"FAIL {agent[:12]} {call[:70]:70} {type(e).__name__}: {e}")
