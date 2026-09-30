"""Build the Copilot agent instructions: rules + CODE + shared core + agent code, checked against 8,000 chars."""
from pathlib import Path
HERE = Path(__file__).parent
AGENTS = {"1_WEO_outlook": ("weo_rules.txt", "weo_code.py"),
          "2_Credit_gap_macroprudential": ("gap_rules.txt", "gap_code.py"),
          "3_Banking_sector": ("fin_rules.txt", "fin_code.py"),
          "4_FSAP_reports": ("fsap_rules.txt", None)}
LIMIT = 8000
if __name__ == "__main__":
    core = (HERE / "common.py").read_text(encoding="utf-8")
    for name, (rules, code) in AGENTS.items():
        text = (HERE / rules).read_text(encoding="utf-8").rstrip("\n") + "\n"
        if code:
            text += "CODE\n" + core + (HERE / code).read_text(encoding="utf-8")
        n = len(text.replace("\n", "\r\n"))
        out = HERE / name / "INSTRUCTIONS.txt"
        out.parent.mkdir(exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\r\n")
        print(f"{name:32} {n:5} chars {'OK' if n <= LIMIT else 'TOO LONG by %d' % (n - LIMIT)}")
