from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def _to_float(x: Any):
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return None
        return float(x)
    except Exception:
        return None


def jsonl_to_excel(jsonl_path: str | Path, xlsx_path: str | Path):
    rows = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)

            ts = rec.get("ts_utc")
            competitor = rec.get("competitor")
            scenario_id = rec.get("scenario_id")
            scenario = rec.get("scenario") or {}
            alquiler = _to_float(scenario.get("alquiler")) or 0.0
            expensas = _to_float(scenario.get("expensas")) or 0.0
            meses = int(scenario.get("meses") or 0)
            base_total = (alquiler + expensas) * meses if meses else None

            norm = rec.get("normalized") or {}
            planes = norm.get("planes") or []

            # Finaer: tus claves actuales
            # Hoggax: claves del normalize_hoggax
            for p in planes:
                row = {
                    "ts": ts,
                    "competitor": competitor,
                    "scenario_id": scenario_id,
                    "alquiler": alquiler,
                    "expensas": expensas,
                    "meses": meses,
                    "alq_exp": alquiler + expensas,
                    "base_total": base_total,
                }

                if competitor == "finaer":
                    cuotas = int(p.get("cuotas") or 0)
                    total_final = _to_float(p.get("monto_final"))
                    monto_cuotas = _to_float(p.get("monto_cuotas"))
                    anticipo = _to_float(p.get("anticipo"))

                    honorario = _to_float(p.get("honorario_sin_descuentos"))
                    desc_abs = _to_float(p.get("descuento_aplicado"))
                    desc_pct = _to_float(p.get("pct_descuento_real"))  # fracción

                    row |= {
                        "plan": f"{cuotas} cuotas",
                        "cuotas": cuotas,
                        "total_final": total_final,
                        "monto_cuota": monto_cuotas,
                        "anticipo": anticipo,
                        "honorario_sin_desc": honorario,
                        "desc_abs": desc_abs,
                        "desc_pct": desc_pct,
                        "fecha_limite_desc": p.get("fecha_limite_descuento"),
                    }

                else:
                    # Hoggax normalize_hoggax
                    total_final = _to_float(p.get("total_final"))
                    cuota = _to_float(p.get("cuota"))
                    anticipo = _to_float(p.get("anticipo"))
                    desc_abs = _to_float(p.get("desc_abs"))
                    desc_pct = _to_float(p.get("desc_pct"))  # fracción

                    row |= {
                        "plan": p.get("metodo"),
                        "cuotas": None,
                        "total_final": total_final,
                        "monto_cuota": cuota,
                        "anticipo": anticipo,
                        "honorario_sin_desc": None,
                        "desc_abs": desc_abs,
                        "desc_pct": desc_pct,
                        "fecha_limite_desc": None,
                        "info": p.get("info"),
                    }

                # métricas comunes
                pct_sobre_base = (total_final / base_total) if (total_final is not None and base_total) else None
                row["pct_sobre_base"] = pct_sobre_base  # fracción

                rows.append(row)

    df = pd.DataFrame(rows)

    Path(xlsx_path).parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Planes", index=False)

        # hoja resumen simple por segmento/plazo/competidor (promedio)
        if not df.empty:
            def seg(x):
                if x <= 500_000:
                    return "hasta 500k"
                if x <= 800_000:
                    return "500k-800k"
                return "mayor_800k"

            df2 = df.copy()
            df2["segmento"] = df2["alq_exp"].apply(seg)

            # promedio por competitor/segmento/meses de pct_sobre_base y descuento
            piv = (
                df2.groupby(["competitor", "segmento", "meses"], as_index=False)
                .agg(
                    pct_sobre_base=("pct_sobre_base", "mean"),
                    desc_pct=("desc_pct", "mean"),
                    desc_abs=("desc_abs", "mean"),
                )
            )
            piv.to_excel(w, sheet_name="Resumen", index=False)
