"""Build the Copilot agent instructions: rules + CODE + shared core + agent code, checked against 8,000 chars."""
from pathlib import Path
HERE = Path(__file__).parent
AGENTS = {"1_WEO_outlook": ("weo_rules.txt", "weo_code.py"),
          "2_Credit_gap_macroprudential": ("gap_rules.txt", "gap_code.py"),
          "3_Financial_soundness": ("fsi_rules.txt", ["fin_base.py", "fsi_code.py"]),
          "4_FSAP_reports": ("fsap_rules.txt", None),
          "5_Bank_balance_sheets": ("bs_rules.txt", ["fin_base.py", "bs_code.py"]),
          "6_Bank_by_bank": ("bbb_rules.txt", ["fin_base.py", "bbb_code.py"])}
LIMIT = 8000
if __name__ == "__main__":
    core = (HERE / "common.py").read_text(encoding="utf-8")
    for name, (rules, code) in AGENTS.items():
        text = (HERE / rules).read_text(encoding="utf-8").rstrip("\n") + "\n"
        if code:
            files = [code] if isinstance(code, str) else code
            text += "CODE\n" + core + "".join((HERE / f).read_text(encoding="utf-8") for f in files)
        n = len(text.replace("\n", "\r\n"))
        out = HERE / name / "INSTRUCTIONS.txt"
        out.parent.mkdir(exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\r\n")
        print(f"{name:32} {n:5} chars {'OK' if n <= LIMIT else 'TOO LONG by %d' % (n - LIMIT)}")
