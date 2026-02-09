from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, cast

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.cell.cell import Cell, MergedCell


PLAZOS = [3, 6, 12, 24, 36]


def to_float(x) -> Optional[float]:
    try:
        if x is None or pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def segmento(alq_exp: float) -> str:
    if alq_exp <= 500_000:
        return "hasta 500k"
    if alq_exp <= 800_000:
        return "500k-800k"
    return "mayor_800k"


def load_latest_jsonl() -> Path:
    files = sorted(Path("output").glob("finaer_*.jsonl"))
    if not files:
        raise SystemExit("No hay output/finaer_*.jsonl. Corré primero: python -m price_monitor.cli")
    return files[-1]


def pick_plan_contado(planes: list[dict]) -> dict:
    if not planes:
        return {}
    for p in planes:
        c = p.get("cuotas", p.get("cantidad_de_cuotas"))
        if c is not None and int(c) == 1:
            return p
    return sorted(planes, key=lambda p: float(p.get("monto_final") or 1e18))[0]


def load_hoggax_rates(path: str = "data/hoggax_rates.csv") -> pd.DataFrame:
    """
    Espera:
      segmento,3,6,12,24,36
    Puede venir:
      - en porcentaje: 60,80,90,195,231
      - o en fracción: 0.6,0.8,0.9,1.95,2.31
    Normaliza a PORCENTAJE (60,80,90,...)
    """
    df = pd.read_csv(path)
    df["segmento"] = df["segmento"].astype(str).str.strip()

    # renombrar columnas numéricas a int
    df = df.rename(columns={c: int(c) for c in df.columns if isinstance(c, str) and c.isdigit()})

    # asegurar columnas
    for m in PLAZOS:
        if m not in df.columns:
            df[m] = pd.NA

    # convertir a número
    for m in PLAZOS:
        df[m] = pd.to_numeric(df[m], errors="coerce")

    # si parecen fracciones (max <= 3.5), convertir a porcentaje
    vals = pd.concat([df[m].dropna() for m in PLAZOS], ignore_index=True)
    if len(vals) and float(vals.max()) <= 3.5:
        for m in PLAZOS:
            df[m] = df[m] * 100.0

    return df[["segmento"] + PLAZOS]


def style_header_row(ws: Worksheet, row: int, start_col: int, end_col: int):
    for col in range(start_col, end_col + 1):
        cell = cast(Cell, ws.cell(row=row, column=col))
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="D9E1F2")
        cell.alignment = Alignment(horizontal="center", vertical="center")


def heatmap(ws: Worksheet, rng: str):
    ws.conditional_formatting.add(
        rng,
        ColorScaleRule(
            start_type="min",
            start_color="63BE7B",
            mid_type="percentile",
            mid_value=50,
            mid_color="FFEB84",
            end_type="max",
            end_color="F8696B",
        ),
    )


def write_matrix(ws: Worksheet, title: str, df_matrix_pct: pd.DataFrame, start_col: int):
    """
    df_matrix_pct: columnas ["segmento","3","6","12","24","36"] con valores en porcentaje (18.0).
    """
    r0 = 1
    c0 = start_col

    # título
    tcell = cast(Cell, ws.cell(r0, c0, value=title))
    tcell.font = Font(bold=True)
    tcell.fill = PatternFill("solid", fgColor="C6E0B4")
    tcell.alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells(start_row=r0, start_column=c0, end_row=r0, end_column=c0 + len(PLAZOS))

    # header
    ws.cell(r0 + 1, c0, value="segmento")
    for i, m in enumerate(PLAZOS):
        ws.cell(r0 + 1, c0 + 1 + i, value=m)
    style_header_row(ws, r0 + 1, c0, c0 + len(PLAZOS))

    # data (NO itertuples: columnas "3","6"... no son atributos)
    for i, (_, row) in enumerate(df_matrix_pct.iterrows(), start=0):
        rr = r0 + 2 + i
        ws.cell(rr, c0, value=str(row["segmento"]))

        for k, m in enumerate(PLAZOS):
            v = row.get(str(m), None)
            cell = cast(Cell, ws.cell(rr, c0 + 1 + k))

            # defensivo
            if isinstance(cell, MergedCell) or cell.coordinate in ws.merged_cells:
                continue

            fv = to_float(v)
            if fv is None:
                cell.value = None
            else:
                # porcentaje (18.0) -> fracción (0.18) para formato %
                cell.value = fv / 100.0
                cell.number_format = "0.00%"
            cell.alignment = Alignment(horizontal="center")

    # widths
    ws.column_dimensions[get_column_letter(c0)].width = 16
    for i in range(1, len(PLAZOS) + 1):
        ws.column_dimensions[get_column_letter(c0 + i)].width = 10

    # heatmap
    nrows = int(df_matrix_pct.shape[0])
    if nrows:
        top_left = ws.cell(r0 + 2, c0 + 1).coordinate
        bot_right = ws.cell(r0 + 1 + nrows, c0 + len(PLAZOS)).coordinate
        heatmap(ws, f"{top_left}:{bot_right}")



def main():
    jsonl_path = load_latest_jsonl()

    # ----- Finaer -> matriz -----
    finaer_rows = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            s = rec["scenario"]
            alq = float(s["alquiler"])
            exp = float(s.get("expensas") or 0)
            meses = int(s["meses"])
            alq_exp = alq + exp

            if alq_exp <= 0 or meses not in PLAZOS:
                continue

            p = pick_plan_contado(rec["normalized"]["planes"])
            monto_final = to_float(p.get("monto_final"))
            if monto_final is None:
                continue

            # % sobre (alq+exp)
            pct_ae = (monto_final / alq_exp) * 100.0
            finaer_rows.append({"segmento": segmento(alq_exp), "meses": meses, "pct": pct_ae})

    df_f = pd.DataFrame(finaer_rows)
    if df_f.empty:
        raise SystemExit("Finaer: no hay datos para plazos 3/6/12/24/36 en el jsonl.")

    finaer_mat = (
        df_f.groupby(["segmento", "meses"], as_index=False)["pct"].mean()
        .pivot(index="segmento", columns="meses", values="pct")
        .reindex(columns=PLAZOS)
        .reset_index()
    )
    finaer_mat.columns = ["segmento"] + [str(m) for m in PLAZOS]

    # ----- Hoggax desde CSV -----
    hoggax_mat = load_hoggax_rates("data/hoggax_rates.csv")
    hoggax_mat.columns = ["segmento"] + [str(m) for m in PLAZOS]

    # ----- Excel -----
    wb = Workbook()

    ws_in = cast(Worksheet, wb.active)
    ws_in.title = "Inputs"
    ws_in.append(["Valor_Alq", "Valor_Exp", "Total_(Alq+Exp)"])
    ws_in.append([350000, 0, "=A2+B2"])
    style_header_row(ws_in, 1, 1, 3)
    ws_in.freeze_panes = "A2"
    ws_in.column_dimensions["A"].width = 14
    ws_in.column_dimensions["B"].width = 14
    ws_in.column_dimensions["C"].width = 18

    ws_m = cast(Worksheet, wb.create_sheet("Matrices"))
    write_matrix(ws_m, "Finaer (% sobre Alq+Exp)", finaer_mat, start_col=1)
    write_matrix(ws_m, "Hoggax (% sobre Alq+Exp)", hoggax_mat, start_col=8)
    ws_m.freeze_panes = "A3"

    # ----- Comparativa (FORMATO LONG: uno abajo del otro) -----
    ws_c = cast(Worksheet, wb.create_sheet("Comparativa"))

    headers = [
        "segmento",
        "plazo_meses",
        "Finaer_pct",
        "Hoggax_pct",
        "Dif_pct",
        "Finaer_$",
        "Hoggax_$",
        "Dif_$",
    ]
    ws_c.append(headers)
    style_header_row(ws_c, 1, 1, len(headers))
    ws_c.freeze_panes = "A2"
    ws_c.auto_filter.ref = ws_c.dimensions

    # anchos
    ws_c.column_dimensions["A"].width = 16
    ws_c.column_dimensions["B"].width = 12
    ws_c.column_dimensions["C"].width = 12
    ws_c.column_dimensions["D"].width = 12
    ws_c.column_dimensions["E"].width = 12
    ws_c.column_dimensions["F"].width = 14
    ws_c.column_dimensions["G"].width = 14
    ws_c.column_dimensions["H"].width = 14

    f_idx = finaer_mat.set_index("segmento")
    h_idx = hoggax_mat.set_index("segmento")
    segmentos_all = ["hasta 500k", "500k-800k", "mayor_800k"]

    # filas long: por segmento x plazo
    for segm in segmentos_all:
        for m in PLAZOS:
            f_pct = to_float(f_idx.loc[segm, str(m)]) if segm in f_idx.index else None
            h_pct = to_float(h_idx.loc[segm, str(m)]) if segm in h_idx.index else None
            d_pct = (f_pct - h_pct) if (f_pct is not None and h_pct is not None) else None

            ws_c.append([segm, m, f_pct, h_pct, d_pct, None, None, None])

    # formato % y fórmulas $ (Sheets compatible)
    # Columnas:
    # A segmento, B plazo_meses, C finaer_pct, D hoggax_pct, E dif_pct, F finaer_$, G hoggax_$, H dif_$
    for r in range(2, ws_c.max_row + 1):
        # % -> fracción + formato
        for col in (3, 4, 5):
            cell = cast(Cell, ws_c.cell(r, col))
            if isinstance(cell, MergedCell) or cell.coordinate in ws_c.merged_cells:
                continue
            v = cell.value
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                cell.value = float(v) / 100.0
                cell.number_format = "0.00%"
                cell.alignment = Alignment(horizontal="center")

        # $ = Total * %
        f_ref = f"{get_column_letter(3)}{r}"  # C
        h_ref = f"{get_column_letter(4)}{r}"  # D

        cell_fd = cast(Cell, ws_c.cell(r, 6))  # F
        cell_hd = cast(Cell, ws_c.cell(r, 7))  # G
        cell_dd = cast(Cell, ws_c.cell(r, 8))  # H

        if not isinstance(cell_fd, MergedCell):
            cell_fd.value = f"=Inputs!$C$2*{f_ref}"
        if not isinstance(cell_hd, MergedCell):
            cell_hd.value = f"=Inputs!$C$2*{h_ref}"
        if not isinstance(cell_dd, MergedCell):
            cell_dd.value = f"={get_column_letter(6)}{r}-{get_column_letter(7)}{r}"

    # heatmap en Dif_$ (col H)
    heatmap(ws_c, f"H2:H{ws_c.max_row}")
    
    # heatmap en Dif_$
    dif_cols = [i for i, h in enumerate(headers, 1) if isinstance(h, str) and h.startswith("Dif_$_")]
    for col in dif_cols:
        heatmap(ws_c, f"{get_column_letter(col)}2:{get_column_letter(col)}{ws_c.max_row}")

    out = Path("output") / f"matrices_compare_{jsonl_path.stem}.xlsx"
    wb.save(out)
    print("Wrote", out)


if __name__ == "__main__":
    main()
