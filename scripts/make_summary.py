from __future__ import annotations

import json
from pathlib import Path
import pandas as pd


def segment_alquiler(alquiler: float) -> str:
    if alquiler <= 500_000:
        return "hasta 500000"
    if alquiler <= 800_000:
        return "500000-800000"
    return "mayor a 800000"


def pick_main_plan(df: pd.DataFrame) -> pd.DataFrame:
    """
    Para comparar de forma consistente: elegir 2 cuotas si existe, sino 1 cuota.
    """
    df = df.copy()
    df["pref"] = df["cuotas"].apply(lambda x: 0 if x == 2 else (1 if x == 1 else 9))
    df = df.sort_values(["scenario_id", "pref", "cuotas"])
    return df.groupby(["ts", "competitor", "scenario_id"], as_index=False).first()


def load_latest_jsonl(output_dir: Path) -> pd.DataFrame:
    files = sorted(output_dir.glob("finaer_*.jsonl"))
    if not files:
        raise SystemExit("No hay output/finaer_*.jsonl")

    latest = files[-1]
    rows = []
    with open(latest, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            scen = rec["scenario"]
            for p in rec.get("normalized", {}).get("planes", []):
                rows.append({
                    "ts": rec.get("ts_utc"),
                    "competitor": rec.get("competitor"),
                    "scenario_id": rec.get("scenario_id"),
                    "alquiler": float(scen.get("alquiler") or 0),
                    "expensas": float(scen.get("expensas") or 0),
                    "alquiler_mas_expensas": float(scen.get("alquiler") or 0) + float(scen.get("expensas") or 0),
                    "meses": int(scen.get("meses") or 0),

                    "cuotas": int(p.get("cuotas") or 0),
                    "monto_final": float(p.get("monto_final") or 0),
                    "honorario_sin_descuentos": float(p.get("honorario_sin_descuentos") or 0),
                    "descuento_aplicado": float(p.get("descuento_aplicado") or 0),
                    "pct_descuento_real": p.get("pct_descuento_real"),
                    "costo_mensual_equiv": p.get("costo_mensual_equiv"),
                    "pct_sobre_total_alq_exp": p.get("pct_sobre_total_alq_exp"),
                })

    df = pd.DataFrame(rows)
    df["pct_descuento_real"] = pd.to_numeric(df["pct_descuento_real"], errors="coerce")
    df["costo_mensual_equiv"] = pd.to_numeric(df["costo_mensual_equiv"], errors="coerce")
    df["pct_sobre_total_alq_exp"] = pd.to_numeric(df["pct_sobre_total_alq_exp"], errors="coerce")
    return df, latest


def main():
    out_dir = Path("output")
    df, latest_file = load_latest_jsonl(out_dir)

    # Elegir un plan "principal" por escenario (2 cuotas si existe, sino 1)
    main_df = pick_main_plan(df)

    # Segmentos de alquiler (según alquiler, no alquiler+expensas)
    main_df["segmento_alquiler"] = main_df["alquiler"].apply(segment_alquiler)

    # Resumen por segmento y plazo
    summary = (
        main_df
        .groupby(["competitor", "segmento_alquiler", "meses"], as_index=False)
        .agg(
            escenarios=("scenario_id", "nunique"),
            avg_monto_final=("monto_final", "mean"),
            avg_honorario_sin_desc=("honorario_sin_descuentos", "mean"),
            avg_descuento=("descuento_aplicado", "mean"),
            avg_pct_desc=("pct_descuento_real", "mean"),
            avg_pct_sobre_contrato=("pct_sobre_total_alq_exp", "mean"),
            avg_costo_mensual=("costo_mensual_equiv", "mean"),
        )
    )

    # Formato porcentajes (dejar numérico también sirve; acá lo redondeo)
    summary["avg_pct_desc"] = summary["avg_pct_desc"].round(4)
    summary["avg_pct_sobre_contrato"] = summary["avg_pct_sobre_contrato"].round(4)
    summary["avg_monto_final"] = summary["avg_monto_final"].round(2)
    summary["avg_descuento"] = summary["avg_descuento"].round(2)
    summary["avg_costo_mensual"] = summary["avg_costo_mensual"].round(2)

    # Pivot “matriz”: filas = segmento, columnas = meses
    pivot_pct = summary.pivot_table(
        index=["competitor", "segmento_alquiler"],
        columns="meses",
        values="avg_pct_sobre_contrato",
        aggfunc="first"
    ).reset_index()

    pivot_desc = summary.pivot_table(
        index=["competitor", "segmento_alquiler"],
        columns="meses",
        values="avg_pct_desc",
        aggfunc="first"
    ).reset_index()

    pivot_price = summary.pivot_table(
        index=["competitor", "segmento_alquiler"],
        columns="meses",
        values="avg_monto_final",
        aggfunc="first"
    ).reset_index()

    # Export a Excel con 4 hojas
    out_xlsx = out_dir / f"summary_{Path(latest_file).stem}.xlsx"
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as w:
        summary.to_excel(w, index=False, sheet_name="Resumen")
        pivot_price.to_excel(w, index=False, sheet_name="Avg_MontoFinal")
        pivot_desc.to_excel(w, index=False, sheet_name="Avg_%Descuento")
        pivot_pct.to_excel(w, index=False, sheet_name="Avg_%SobreContrato")

    print(f"Wrote summary -> {out_xlsx}")


if __name__ == "__main__":
    main()
