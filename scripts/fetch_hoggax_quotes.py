from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests


API_URL = "https://api.hoggax.com/cotizador/individuo/cotizar"

MESES_TO_PLAZO = {24: 2, 36: 3}

HEADERS = {
    "content-type": "application/json",
    "accept": "application/json, text/plain, */*",
}

SCENARIOS_CSV = Path("data/scenarios.csv")

OUT_RAW_DIR = Path("output/hoggax_raw")
OUT_CSV = Path("output/hoggax_rates_long.csv")

TARGET_CUOTAS = {1, 3}  # lo que querés comparar


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    alquiler: int
    expensas: int
    meses: int


def _parse_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(float(x))
    except Exception:
        return None


def _extract_total_from_info(info_texto: str) -> Optional[int]:
    """
    Ej: "Importe total: $ 1.413.747. CFT: 144.10%"
    Devuelve 1413747
    """
    if not info_texto:
        return None
    m = re.search(r"Importe total:\s*\$\s*([0-9\.\,]+)", info_texto)
    if not m:
        return None
    s = m.group(1).replace(".", "").replace(",", "")
    try:
        return int(s)
    except Exception:
        return None


def _extract_cuota_from_info(info_texto: str) -> Optional[int]:
    """
    Ej: "Importe cuota: $ 324.999. CFT: 0.00%"
    Devuelve 324999
    """
    if not info_texto:
        return None
    m = re.search(r"Importe cuota:\s*\$\s*([0-9\.\,]+)", info_texto)
    if not m:
        return None
    s = m.group(1).replace(".", "").replace(",", "")
    try:
        return int(s)
    except Exception:
        return None


def _cuotas_from_texto(texto: str) -> Optional[int]:
    """
    "15% OFF" -> 1 (contado)
    "3 CUOTAS sin interés" -> 3
    "12 Cuotas" -> 12
    "7,5% Adel. + 23 CUOTAS" -> 24? (no la queremos)
    """
    if not texto:
        return None
    t = texto.lower()

    # contado
    if "transferencia" in t or "off" in t:
        # este plan en tu JSON es 15% OFF transferencia, lo tratamos como 1 pago
        return 1

    # buscar patrón N cuotas
    m = re.search(r"(\d+)\s*cuot", t)
    if m:
        return int(m.group(1))

    return None


def _request_hoggax(s: Scenario) -> dict:
    plazo = MESES_TO_PLAZO.get(s.meses)
    if plazo is None:
        raise SystemExit(f"Meses={s.meses} no está mapeado en MESES_TO_PLAZO.")

    payload = {
        "cotizacion": {
            "alquiler": s.alquiler,
            "expensas": s.expensas,
            "plazo": plazo,
            "discountRef": "",
        },
        "meta": {
            "fuente": "Hoggax",
            "medio": "Cotizador (nueva web)",
            "esMobile": False,
            "esRenovacion": False,
        },
    }

    r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def _load_scenarios() -> list[Scenario]:
    if not SCENARIOS_CSV.exists():
        raise SystemExit(f"No existe {SCENARIOS_CSV}.")
    df = pd.read_csv(SCENARIOS_CSV)

    out: list[Scenario] = []
    for _, r in df.iterrows():
        run = r.get("run", True)
        if isinstance(run, str):
            run = run.strip().lower() not in {"false", "0", "no"}
        if not bool(run):
            continue

        out.append(
            Scenario(
                scenario_id=str(r["scenario_id"]),
                alquiler=int(float(r["alquiler"])),
                expensas=int(float(r["expensas"])),
                meses=int(float(r["meses"])),
            )
        )
    return out


def main():
    OUT_RAW_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = _load_scenarios()

    rows: list[dict] = []

    for s in scenarios:
        # ---- 12 meses: regla fija (NO API) ----
        if s.meses == 12:
            base = s.alquiler + s.expensas  # monto final = alq + exp

            # 1 pago transferencia (15% OFF)
            rows.append(
                {
                    "scenario_id": s.scenario_id,
                    "alquiler": s.alquiler,
                    "expensas": s.expensas,
                    "alq_exp": base,
                    "meses": s.meses,
                    "cuotas": 1,
                    "plan_texto": "15% OFF",
                    "plan_subtexto": "Transferencia",
                    "hoggax_sin_desc": base,
                    "hoggax_total_web": int(round(base * 0.85)),
                    "hoggax_monto_cuota": 0,
                }
            )

            # 3 cuotas sin interés (sin descuento)
            rows.append(
                {
                    "scenario_id": s.scenario_id,
                    "alquiler": s.alquiler,
                    "expensas": s.expensas,
                    "alq_exp": base,
                    "meses": s.meses,
                    "cuotas": 3,
                    "plan_texto": "3 CUOTAS sin interés",
                    "plan_subtexto": "Crédito o Débito",
                    "hoggax_sin_desc": base,
                    "hoggax_total_web": base,
                    "hoggax_monto_cuota": int(round(base / 3)),
                }
            )

            continue

        # ---- 24/36 meses: por API ----
        data = _request_hoggax(s)
        (OUT_RAW_DIR / f"{s.scenario_id}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        cot = (data.get("payload") or {}).get("cotizacion") or {}
        lista = _parse_int(cot.get("importeRaw")) or _parse_int(cot.get("importe"))
        facs = cot.get("facilidades_pago") or []
        if lista is None or not isinstance(facs, list):
            continue

        for f in facs:
            texto = str(f.get("texto") or "")
            sub = str(f.get("sub_texto") or "")
            precio_texto = str(f.get("precio_texto") or "")
            info = str(f.get("info_texto") or "")
            importe = _parse_int(f.get("importe"))

            cuotas = _cuotas_from_texto(texto)

            if cuotas not in TARGET_CUOTAS:
                continue

            total = None
            monto_cuota = None

            if precio_texto.lower().startswith("precio"):
                total = importe
                monto_cuota = 0 if cuotas == 1 else _extract_cuota_from_info(info)
            else:
                monto_cuota = importe
                total = _extract_total_from_info(info)
                if total is None and monto_cuota is not None and cuotas is not None:
                    total = monto_cuota * cuotas

            rows.append(
                {
                    "scenario_id": s.scenario_id,
                    "alquiler": s.alquiler,
                    "expensas": s.expensas,
                    "alq_exp": s.alquiler + s.expensas,
                    "meses": s.meses,
                    "cuotas": cuotas,
                    "plan_texto": texto,
                    "plan_subtexto": sub,
                    "hoggax_sin_desc": lista,
                    "hoggax_total_web": total,
                    "hoggax_monto_cuota": monto_cuota,
                }
            )

        time.sleep(0.25)

    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)

    print("Wrote raw ->", OUT_RAW_DIR)
    print("Wrote csv ->", OUT_CSV)
    print(df)

if __name__ == "__main__":
    main()
