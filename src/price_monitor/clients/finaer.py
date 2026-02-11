from __future__ import annotations

from typing import Any, Dict

import httpx


FINAER_URL = "https://admin.finaersa.com.ar/api/web/calcular-costo-del-servicio/"


def call_finaer(alquiler: int, expensas: int, meses: int, tipo_garantia: bool) -> Dict[str, Any]:
    """
    Llama a la API de Finaer.

    Header/body esperado (según lo que pasaste):
      {alquiler: "350000", expensas: 0, duracion_contrato: "12", tipo_garantia: false}

    Nota: algunos backends esperan strings en alquiler/duracion_contrato.
    """
    payload = {
        "alquiler": str(int(alquiler)),
        "expensas": int(expensas),
        "duracion_contrato": str(int(meses)),
        "tipo_garantia": bool(tipo_garantia),
    }

    with httpx.Client(timeout=30) as client:
        r = client.post(FINAER_URL, json=payload)
        r.raise_for_status()
        return r.json()
