# scripts/run_pipeline_once.py
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]

# Entradas únicas (misma entrada para ambos proveedores)
ALQ_EXP_VALUES = [499_999, 799_999, 801_000]
EXPENSAS = 0
MESES = [24, 36]          # 24/36 “por web” para Hoggax, Finaer también los trae
TIPO_GARANTIA = False     # mantené igual a tu pipeline actual


def run(cmd: list[str]) -> None:
    print("\n>>", " ".join(cmd))
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def write_scenarios_csv() -> Path:
    out = REPO_ROOT / "data" / "scenarios.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    i = 1
    for alq in ALQ_EXP_VALUES:
        for m in MESES:
            rows.append(
                {
                    "scenario_id": f"S_{alq}_{m}",
                    "alquiler": alq,
                    "expensas": EXPENSAS,
                    "meses": m,
                    "tipo_garantia": TIPO_GARANTIA,
                    "run": True,
                }
            )
            i += 1

    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"Wrote {len(rows)} scenarios -> {out}")
    return out


def main() -> None:
    # 0) escenarios minimalistas (evita “ruido”)
    write_scenarios_csv()

    # 1) FINaer una sola corrida (usa data/scenarios.csv)
    # Asume que tu CLI ya lee data/scenarios.csv y genera output/finaer_*.xlsx y/o output/finaer_*.jsonl
    run([sys.executable, "-m", "price_monitor.cli"])

    # 2) Hoggax por API (usa data/scenarios.csv)
    run([sys.executable, "scripts/fetch_hoggax_quotes.py"])

    # 3) Comparativa final (Excel con formato + heatmap)
    run([sys.executable, "scripts/compare_finaer_vs_hoggax_borders.py"])

    stamp = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    print("\nDONE:", stamp)
    print("Output final ->", REPO_ROOT / "output" / "compare_borders_finaer_vs_hoggax.xlsx")


if __name__ == "__main__":
    main()
