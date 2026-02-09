from __future__ import annotations
import httpx 

FINAER_URL = "https://admin.finaersa.com.ar/api/web/calcular-costo-del-servicio/"

def call_finaer(alquiler: int, expensas: int, meses: int, tipo_garantia: bool = False, timeout_s: float = 20.0) -> dict:
    payload = {
        "alquiler": str(alquiler),
        "expensas": int(expensas),
        "duracion_contrato": str(meses),
        "tipo_garantia": bool(tipo_garantia),
    }
    with httpx.Client(timeout=timeout_s, headers={"User-Agent": "price-monitor/0.1"}) as client:
        r = client.post(FINAER_URL, json=payload)
        r.raise_for_status()
        return r.json()
