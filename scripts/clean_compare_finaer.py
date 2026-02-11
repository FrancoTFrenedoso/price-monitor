from __future__ import annotations

from pathlib import Path
import pandas as pd

IN = Path("output/finaer_2026-02-11T135228Z.xlsx")   # <-- tu archivo real
OUT = Path("output/finaer_clean_cmp.xlsx")

TARGET_ALQ_EXP = {499_999, 799_999, 801_000}
TARGET_MESES = {24, 36}
TARGET_CUOTAS = {1, 3}


def seg(x: float) -> str:
    if x <= 500_000:
        return "hasta_500k"
    if x <= 800_000:
        return "500_800k"
    return "mayor_800k"


def main():
    if not IN.exists():
        raise SystemExit(f"No existe {IN}")

    # intenta leer la primera hoja
    df = pd.read_excel(IN)

    # normalizar nombres por si vienen con mayúsculas/espacios
    df.columns = [str(c).strip() for c in df.columns]

    required = {"alq_exp", "meses", "cuotas", "honorario_sin_desc", "total_final", "monto_cuota", "anticipo"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Faltan columnas en {IN.name}: {sorted(missing)}")

    # asegurar tipos
    for c in ["alq_exp", "meses", "cuotas", "honorario_sin_desc", "total_final", "monto_cuota", "anticipo"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["cuotas"] = df["cuotas"].astype("Int64")
    df["meses"] = df["meses"].astype("Int64")
    df["alq_exp"] = df["alq_exp"].astype("Int64")

    # filtros duros
    df = df[df["alq_exp"].isin(TARGET_ALQ_EXP)]
    df = df[df["meses"].isin(TARGET_MESES)]
    df = df[df["cuotas"].isin(TARGET_CUOTAS)]

    # métricas comparables
    df["segmento"] = df["alq_exp"].astype(float).apply(seg)
    df["finaer_lista"] = df["honorario_sin_desc"]

    # transferencia 15% SOLO contado
    df["finaer_total_transfer"] = df["finaer_lista"]
    df.loc[df["cuotas"] == 1, "finaer_total_transfer"] = df.loc[df["cuotas"] == 1, "finaer_lista"] * 0.85

    df["finaer_cuota_equiv"] = df["finaer_total_transfer"] / df["cuotas"].astype(float)

    # salida
    out_cols = [
        "segmento",
        "alq_exp",
        "meses",
        "cuotas",
        "finaer_lista",
        "finaer_total_transfer",
        "finaer_cuota_equiv",
        "total_final",
        "monto_cuota",
        "anticipo",
    ]
    df_out = df[out_cols].sort_values(["alq_exp", "meses", "cuotas"]).reset_index(drop=True)

    with pd.ExcelWriter(OUT, engine="openpyxl") as w:
        df_out.to_excel(w, index=False, sheet_name="cmp")

    print("Read ->", IN)
    print("Wrote ->", OUT)
    print(df_out)


if __name__ == "__main__":
    main()
