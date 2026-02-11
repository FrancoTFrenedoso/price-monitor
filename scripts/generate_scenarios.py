from __future__ import annotations

from pathlib import Path
import pandas as pd


def main():
    out = Path("data/scenarios.csv")
    out.parent.mkdir(parents=True, exist_ok=True)

    alquileres = [499_999, 799_999, 801_000]
    expensas = [0]
    meses = [24, 36]          # <-- ACÁ agregás 36
    tipo_garantia = [False]

    rows = []
    i = 1
    for a in alquileres:
        for e in expensas:
            for m in meses:
                for tg in tipo_garantia:
                    rows.append(
                        {
                            "scenario_id": f"S_{a}_{m}",
                            "alquiler": a,
                            "expensas": e,
                            "meses": m,
                            "tipo_garantia": tg,
                            "run": True,
                        }
                    )
                    i += 1

    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"Wrote {len(rows)} scenarios -> {out}")


if __name__ == "__main__":
    main()
