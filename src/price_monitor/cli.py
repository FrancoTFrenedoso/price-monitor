from __future__ import annotations

import time
from pathlib import Path

from price_monitor.scenarios import load_scenarios_csv
from price_monitor.clients.finaer import call_finaer
from price_monitor.normalize.finaer import normalize_finaer
from price_monitor.io.files import write_jsonl, utc_stamp
from price_monitor.io.excel import jsonl_to_excel


def main():
    csv_path = Path("data/scenarios.csv")
    if not csv_path.exists():
        print("No existe data/scenarios.csv")
        return

    df = load_scenarios_csv(csv_path)
    df = df[df["run"] == True]

    if df.empty:
        print("No hay escenarios con run=true en data/scenarios.csv")
        return

    ts = utc_stamp()
    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"finaer_{ts}.jsonl"

    rows: list[dict] = []

    for _, r in df.iterrows():
        try:
            raw = call_finaer(
                int(r["alquiler"]),
                int(r["expensas"]),
                int(r["meses"]),
                bool(r["tipo_garantia"]),
            )
            norm = normalize_finaer(raw)

            rows.append({
                "ts_utc": ts,
                "competitor": "finaer",
                "scenario_id": r["scenario_id"],
                "scenario": {
                    "alquiler": int(r["alquiler"]),
                    "expensas": int(r["expensas"]),
                    "meses": int(r["meses"]),
                    "tipo_garantia": bool(r["tipo_garantia"]),
                },
                "normalized": norm,
                "raw": raw,
            })

            print(f"OK {r['scenario_id']} -> planes: {len(norm.get('planes', []))}")

        except Exception as e:
            print(f"ERROR {r['scenario_id']}: {e}")

        time.sleep(0.25)  # rate limit básico

    if not rows:
        print("No se obtuvieron resultados válidos")
        return

    write_jsonl(out_path, rows)
    print(f"Wrote JSONL -> {out_path}")

    # Exportar a Excel
    xlsx_path = out_path.with_suffix(".xlsx")
    jsonl_to_excel(out_path, xlsx_path)
    print(f"Wrote Excel -> {xlsx_path}")

    print(f"Wrote Excel -> {xlsx_path}")



if __name__ == "__main__":
    main()

