from __future__ import annotations

from pathlib import Path
import pandas as pd


def main():
    out = Path("data/scenarios.csv")
    out.parent.mkdir(parents=True, exist_ok=True)

    rows = [
        {"scenario_id": "S_499999_24", "alquiler": 499_999, "expensas": 0, "meses": 24, "tipo_garantia": False, "run": True},
        {"scenario_id": "S_799999_24", "alquiler": 799_999, "expensas": 0, "meses": 24, "tipo_garantia": False, "run": True},
        {"scenario_id": "S_801000_24", "alquiler": 801_000, "expensas": 0, "meses": 24, "tipo_garantia": False, "run": True},
    ]

    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} scenarios -> {out}")


if __name__ == "__main__":
    main()
