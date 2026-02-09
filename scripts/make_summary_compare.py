from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.utils import get_column_letter
from typing import cast
from openpyxl.worksheet.worksheet import Worksheet

PLAZOS = [3, 6, 12, 24, 36]
EMP_COMP = "Finaer"
EMP_OURS = "Hoggax"


def to_float(x) -> Optional[float]:
    try:
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def seg(a: float) -> str:
    if a <= 500_000:
        return "hasta 500k"
    if a <= 800_000:
        return "500k-800k"
    return "mayor_800k"


def load_latest_jsonl() -> tuple[pd.DataFrame, str]:
    out = Path("output")
    files = sorted(out.glob("*.jsonl"))
    if not files:
        raise SystemExit("No hay jsonl en output/")
    f = files[-1]

    rows = []
    with open(f, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            s = r["scenario"]
            for p in r["normalized"]["planes"]:
                rows.append({
                    "scenario_id": r["scenario_id"],
                    "alquiler": float(s.get("alquiler") or 0),
                    "meses": int(s.get("meses") or 0),
                    "cuotas": int(p.get("cuotas") or 0),
                    "pct_contrato": p.get("pct_sobre_total_alq_exp"),
                    "pct_desc": p.get("pct_descuento_real"),
                })

    df = pd.DataFrame(rows)
    df["pct_contrato"] = pd.to_numeric(df["pct_contrato"], errors="coerce")
    df["pct_desc"] = pd.to_numeric(df["pct_desc"], errors="coerce")
    return df, f.stem


def pick_plan(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["scenario_id", "cuotas"])
    return df.groupby("scenario_id", as_index=False).first()


def load_hoggax_rates(path="data/hoggax_rates.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df["segmento"] = df["segmento"].astype(str).str.strip()
    df = df.rename(columns={c: int(c) for c in df.columns if c.isdigit()})
    for m in PLAZOS:
        if m not in df.columns:
            df[m] = pd.NA
    return df[["segmento"] + PLAZOS]


def to_matrix(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    m = df.pivot(index="segmento", columns="meses", values=value_col)
    for plazo in PLAZOS:
        if plazo not in m.columns:
            m[plazo] = pd.NA
    m = m[PLAZOS]
    return m.reset_index()


def main():
    df, stem = load_latest_jsonl()
    df = pick_plan(df)
    df["segmento"] = df["alquiler"].apply(seg)

    summary = (
        df.groupby(["segmento", "meses"], as_index=False)
        .agg(
            finaer_pct=("pct_contrato", "mean"),
            finaer_desc=("pct_desc", "mean"),
        )
    )

    finaer_pct_m = to_matrix(summary, "finaer_pct")
    hoggax_m = load_hoggax_rates("data/hoggax_rates.csv")

    wb = Workbook()

    ws_in = cast(Worksheet, wb.active)

    ws_in.title = "Inputs"
    ws_in.append(["Valor_Alq", "Valor_Exp", "Total_Mensual"])
    ws_in.append([350000, 0, "=A2+B2"])
    for c in ws_in[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="D9E1F2")
    ws_in.freeze_panes = "A2"

    ws = cast(Worksheet, wb.create_sheet("Matriz"))

    headers = ["segmento"]
    for m in PLAZOS:
        headers += [
            f"{EMP_COMP}_%_{m}m",
            f"{EMP_OURS}_%_{m}m",
            f"Dif_%_{m}m",
            f"{EMP_COMP}_$_{m}m",
            f"{EMP_OURS}_$_{m}m",
            f"Dif_$_{m}m",
        ]
    ws.append(headers)

    f_pct = finaer_pct_m.set_index("segmento")
    h_pct = hoggax_m.set_index("segmento")

    for segm in f_pct.index:
        row = [segm]
        for m in PLAZOS:
            fp_f = to_float(f_pct.loc[segm, m])
            hp_f = to_float(h_pct.loc[segm, m] if segm in h_pct.index else None)

            row += [
                fp_f,
                hp_f,
                (fp_f - hp_f) if (fp_f is not None and hp_f is not None) else None,
                None,
                None,
                None,
            ]
        ws.append(row)

    # fórmulas de precios $
    for r in range(2, ws.max_row + 1):
        base_col = 2
        for i, m in enumerate(PLAZOS):
            block = base_col + i * 6
            c_f_pct = get_column_letter(block)
            c_h_pct = get_column_letter(block + 1)
            c_f_price = get_column_letter(block + 3)
            c_h_price = get_column_letter(block + 4)
            c_diff = get_column_letter(block + 5)

            ws[f"{c_f_price}{r}"] = f"=Inputs!$C$2*{m}*{c_f_pct}{r}"
            ws[f"{c_h_price}{r}"] = f"=Inputs!$C$2*{m}*{c_h_pct}{r}"
            ws[f"{c_diff}{r}"] = f"={c_f_price}{r}-{c_h_price}{r}"

    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="D9E1F2")

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    # color scale en Dif_$
    headers_row = [ws.cell(row=1, column=i).value for i in range(1, ws.max_column + 1)]
    dif_cols = [i for i, h in enumerate(headers_row, 1) if isinstance(h, str) and h.startswith("Dif_$_")]

    for col in dif_cols:
        rng = f"{get_column_letter(col)}2:{get_column_letter(col)}{ws.max_row}"
        ws.conditional_formatting.add(
            rng,
            ColorScaleRule(
                start_type="min", start_color="63BE7B",
                mid_type="percentile", mid_value=50, mid_color="FFEB84",
                end_type="max", end_color="F8696B",
            ),
        )

    out = Path("output") / f"compare_{stem}.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print("Wrote", out)


if __name__ == "__main__":
    main()