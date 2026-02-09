from __future__ import annotations

from pathlib import Path
import csv
import pandas as pd


def _sniff_delimiter(path: str | Path) -> str:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
    try:
        # string de delimitadores posibles, no lista
        return csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except Exception:
        return ","


def load_scenarios_csv(path: str | Path) -> pd.DataFrame:
    delim = _sniff_delimiter(path)

    df = pd.read_csv(
        path,
        sep=delim,
        encoding="utf-8-sig",
        on_bad_lines="skip",
        engine="python",
    )

    df.columns = [c.strip().lstrip("\ufeff").lower() for c in df.columns]

    required = {"scenario_id", "alquiler", "expensas", "meses", "tipo_garantia", "run"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(
            f"CSV inválido. Faltan columnas: {missing}. Columnas presentes: {list(df.columns)}. "
            f"Separador detectado: {repr(delim)}"
        )

    df["alquiler"] = df["alquiler"].astype(int)
    df["expensas"] = df["expensas"].astype(int)
    df["meses"] = df["meses"].astype(int)
    df["tipo_garantia"] = df["tipo_garantia"].astype(str).str.strip().str.lower().isin(["true", "1", "yes", "si", "sí"])
    df["run"] = df["run"].astype(str).str.strip().str.lower().isin(["true", "1", "yes", "si", "sí"])
    return df
