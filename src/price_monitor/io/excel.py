from __future__ import annotations

import json
from pathlib import Path
import pandas as pd


def jsonl_to_excel(jsonl_path: str | Path, xlsx_path: str | Path):
    rows: list[dict] = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)

            base = {
                "ts": rec.get("ts_utc"),
                "competitor": rec.get("competitor"),
                "scenario_id": rec.get("scenario_id"),
                "alquiler": rec["scenario"].get("alquiler"),
                "expensas": rec["scenario"].get("expensas"),
                "alquiler_mas_expensas": (rec["scenario"].get("alquiler") or 0) + (rec["scenario"].get("expensas") or 0),
                "meses": rec["scenario"].get("meses"),
                "tipo_garantia": rec["scenario"].get("tipo_garantia"),
            }

            for p in rec.get("normalized", {}).get("planes", []):
                rows.append(base | {
                    "cuotas": p.get("cuotas"),
                    "monto_final": p.get("monto_final"),
                    "anticipo": p.get("anticipo"),
                    "monto_cuotas": p.get("monto_cuotas"),

                    "honorario_sin_descuentos": p.get("honorario_sin_descuentos"),
                    "descuento_aplicado": p.get("descuento_aplicado"),
                    "pct_descuento_aplicado_api": p.get("pct_descuento_aplicado_api"),
                    "pct_descuento_real": p.get("pct_descuento_real"),

                    "fecha_limite_descuento": p.get("fecha_limite_descuento"),
                    "costo_mensual_equiv": p.get("costo_mensual_equiv"),

                    "pct_sobre_total_alquiler": p.get("pct_sobre_total_alquiler"),
                    "pct_sobre_total_alq_exp": p.get("pct_sobre_total_alq_exp"),
                })

    df = pd.DataFrame(rows)
    out = Path(xlsx_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(out, index=False)
