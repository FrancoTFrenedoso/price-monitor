from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def load_all_jsonl(output_dir: Path) -> pd.DataFrame:
    rows = []
    for p in sorted(output_dir.glob("finaer_*.jsonl")):
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)

                scen = rec["scenario"]
                for plan in rec.get("normalized", {}).get("planes", []):
                    rows.append({
                        "ts": rec.get("ts_utc"),
                        "scenario_id": rec.get("scenario_id"),
                        "alquiler": scen.get("alquiler"),
                        "expensas": scen.get("expensas"),
                        "alquiler_mas_expensas": (scen.get("alquiler") or 0) + (scen.get("expensas") or 0),
                        "meses": scen.get("meses"),
                        "cuotas": plan.get("cuotas"),
                        "monto_final": plan.get("monto_final"),
                        "anticipo": plan.get("anticipo"),
                        "monto_cuotas": plan.get("monto_cuotas"),
                        "honorario_sin_descuentos": plan.get("honorario_sin_descuentos"),
                        "descuento_aplicado": plan.get("descuento_aplicado"),
                        "pct_descuento_real": plan.get("pct_descuento_real"),
                        "costo_mensual_equiv": plan.get("costo_mensual_equiv"),
                        "pct_sobre_total_alq_exp": plan.get("pct_sobre_total_alq_exp"),
                    })
    return pd.DataFrame(rows)


def save_charts(df: pd.DataFrame, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    df = df.copy()
    df["meses"] = df["meses"].astype(int)
    df["cuotas"] = df["cuotas"].astype(int)

    # 1) % sobre contrato (alq+exp) vs alquiler, por plazo, usando cuotas=1 (contado)
    df1 = df[df["cuotas"] == 1].dropna(subset=["pct_sobre_total_alq_exp"])
    for m in sorted(df1["meses"].unique()):
        sub = df1[df1["meses"] == m].sort_values("alquiler_mas_expensas")
        plt.figure()
        plt.plot(sub["alquiler_mas_expensas"], sub["pct_sobre_total_alq_exp"])
        plt.title(f"% sobre contrato (alq+exp) - contado - {m} meses")
        plt.xlabel("Alquiler + Expensas (mensual)")
        plt.ylabel("Pct sobre total del contrato")
        plt.tight_layout()
        plt.savefig(out_dir / f"pct_sobre_contrato_contado_{m}m.png", dpi=150)
        plt.close()

    # 2) Descuento real (%) vs alquiler, por plazo, cuotas=1
    df2 = df[df["cuotas"] == 1].dropna(subset=["pct_descuento_real"])
    for m in sorted(df2["meses"].unique()):
        sub = df2[df2["meses"] == m].sort_values("alquiler_mas_expensas")
        plt.figure()
        plt.plot(sub["alquiler_mas_expensas"], sub["pct_descuento_real"])
        plt.title(f"Descuento real - contado - {m} meses")
        plt.xlabel("Alquiler + Expensas (mensual)")
        plt.ylabel("Pct descuento real")
        plt.tight_layout()
        plt.savefig(out_dir / f"pct_descuento_real_contado_{m}m.png", dpi=150)
        plt.close()

    # 3) Costo mensual equivalente por cantidad de cuotas, usando un escenario “mediano” por plazo
    #    (elige el alquiler_mas_expensas mediano para cada plazo)
    for m in sorted(df["meses"].unique()):
        subm = df[df["meses"] == m].dropna(subset=["costo_mensual_equiv"])
        if subm.empty:
            continue
        med = subm["alquiler_mas_expensas"].median()
        pick = subm.iloc[(subm["alquiler_mas_expensas"] - med).abs().argsort()[:1]]
        sid = pick["scenario_id"].iloc[0]
        sub = subm[subm["scenario_id"] == sid].sort_values("cuotas")

        plt.figure()
        plt.plot(sub["cuotas"], sub["costo_mensual_equiv"], marker="o")
        plt.title(f"Costo mensual equivalente vs cuotas (escenario {sid}) - {m} meses")
        plt.xlabel("Cuotas")
        plt.ylabel("Costo mensual equivalente")
        plt.tight_layout()
        plt.savefig(out_dir / f"costo_mensual_vs_cuotas_{m}m.png", dpi=150)
        plt.close()


def main():
    out_dir = Path("output")
    df = load_all_jsonl(out_dir)

    if df.empty:
        print("No hay datos en output/finaer_*.jsonl")
        return

    # Excel consolidado histórico
    consolidated = out_dir / "finaer_consolidated.xlsx"
    df.to_excel(consolidated, index=False)

    # Gráficos
    charts_dir = out_dir / "charts"
    save_charts(df, charts_dir)

    print(f"Wrote consolidated -> {consolidated}")
    print(f"Wrote charts -> {charts_dir}")


if __name__ == "__main__":
    main()
