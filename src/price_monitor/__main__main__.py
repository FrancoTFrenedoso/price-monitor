from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def run(cmd: list[str]) -> int:
    print("+", " ".join(cmd))
    return subprocess.call(cmd)


def main() -> None:
    p = argparse.ArgumentParser(prog="price-monitor")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("summary", help="Genera escenarios, corre scraping (API) y exporta Excel promedio")
    s.add_argument("--no-generate", action="store_true", help="No regenera data/scenarios.csv")
    s.add_argument("--no-run", action="store_true", help="No corre la recolección (cli)")
    s.add_argument("--no-report", action="store_true", help="No genera el excel resumen")
    s.add_argument("--scenarios", default="scripts/generate_scenarios.py")
    s.add_argument("--report", default="scripts/make_summary_simple.py")

    args = p.parse_args()

    if args.cmd == "summary":
        root = Path.cwd()
        if not (root / "pyproject.toml").exists():
            print("Ejecutá esto desde la raíz del repo (donde está pyproject.toml).")
            sys.exit(2)

        code = 0
        if not args.no_generate:
            code = run([sys.executable, args.scenarios])
            if code != 0:
                sys.exit(code)

        if not args.no_run:
            code = run([sys.executable, "-m", "price_monitor.cli"])
            if code != 0:
                sys.exit(code)

        if not args.no_report:
            code = run([sys.executable, args.report])
            if code != 0:
                sys.exit(code)

        print("OK. Revisá output/")
