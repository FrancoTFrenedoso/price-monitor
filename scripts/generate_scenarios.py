from __future__ import annotations

from pathlib import Path
import pandas as pd


def main():
    out = Path("data/scenarios.csv")
    out.parent.mkdir(parents=True, exist_ok=True)

    alquileres = list(range(200_000, 1_200_001, 100_000))
    expensas = [0, 50_000, 100_000]
    meses = [12, 24, 36]

    rows = []
    i = 1
    for a in alquileres:
        for e in expensas:
            for m in meses:
                rows.append({
                    "scenario_id": f"AUTO_{i:04d}",
                    "alquiler": a,
                    "expensas": e,
                    "meses": m,
                    "tipo_garantia": False,
                    "run": True,
                })
                i += 1

    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} scenarios -> {out}")


if __name__ == "__main__":
    main()
