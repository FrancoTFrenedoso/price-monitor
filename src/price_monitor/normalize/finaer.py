from __future__ import annotations

from typing import Any, Optional


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        # strings vacíos o "null"
        if isinstance(x, str) and not x.strip():
            return None
        return float(x)
    except Exception:
        return None


def _to_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        if isinstance(x, str) and not x.strip():
            return None
        return int(float(x))
    except Exception:
        return None


def normalize_finaer(resp: dict) -> dict:
    obj = (resp or {}).get("object") or {}

    meses = _to_int(obj.get("duracion_del_contrato_en_meses")) or 0
    alquiler = _to_float(obj.get("alquiler")) or 0.0
    expensas = _to_float(obj.get("expensas")) or 0.0

    base_mensual_alq = alquiler
    base_mensual_alq_exp = alquiler + expensas

    planes = obj.get("posibles_planes_de_cuotas") or []

    out_planes = []
    planes_raw = []

    for p in planes:
        cuotas = _to_int(p.get("cantidad_de_cuotas")) or 0
        monto_final = _to_float(p.get("monto_final"))
        honorario = _to_float(p.get("honorario_sin_descuentos"))
        descuento = _to_float(p.get("descuento_aplicado"))
        monto_cuotas = _to_float(p.get("monto_cuotas"))
        anticipo = _to_float(p.get("anticipo"))
        fecha_limite = p.get("fecha_limite_descuento")
        pct_desc_api = _to_float(p.get("porcentaje_de_descuento_aplicado"))

        # ---- tabla exacta como API
        planes_raw.append(
            {
                "monto_cuotas": monto_cuotas,
                "monto_final": monto_final,
                "honorario_sin_descuentos": honorario,
                "porcentaje_de_descuento_aplicado": pct_desc_api,
                "descuento_aplicado": descuento,
                "cantidad_de_cuotas": cuotas,
                "anticipo": anticipo,
                "fecha_limite_descuento": fecha_limite,
            }
        )

        # ---- derivados
        costo_mensual_equiv = (monto_final / meses) if (monto_final is not None and meses) else None

        pct_desc_real = None
        if honorario and honorario > 0 and descuento is not None:
            pct_desc_real = descuento / honorario  # fracción (0.20 = 20%)

        pct_sobre_total_alquiler = None
        denom_alq = base_mensual_alq * meses
        if monto_final is not None and denom_alq:
            pct_sobre_total_alquiler = monto_final / denom_alq  # fracción

        pct_sobre_total_alq_exp = None
        denom_ae = base_mensual_alq_exp * meses
        if monto_final is not None and denom_ae:
            pct_sobre_total_alq_exp = monto_final / denom_ae  # fracción

        # ---- transferencia (regla negocio): 15% OFF SOLO en 1 pago
        transfer_desc_pct = 0.15 if cuotas == 1 else 0.0  # fracción
        monto_final_transfer = (honorario * (1.0 - transfer_desc_pct)) if (honorario is not None and cuotas == 1) else monto_final

        out_planes.append(
            {
                "cuotas": cuotas,
                "monto_final": monto_final,
                "monto_final_transfer": monto_final_transfer,          # <-- NUEVO
                "transfer_desc_pct": transfer_desc_pct,                # <-- NUEVO (fracción)
                "monto_cuotas": monto_cuotas,
                "anticipo": anticipo,
                "honorario_sin_descuentos": honorario,
                "descuento_aplicado": descuento,
                "pct_descuento_aplicado_api": pct_desc_api,  # como venga (a veces 0)
                "pct_descuento_real": pct_desc_real,         # fracción
                "fecha_limite_descuento": fecha_limite,
                "costo_mensual_equiv": costo_mensual_equiv,
                "pct_sobre_total_alquiler": pct_sobre_total_alquiler,  # fracción
                "pct_sobre_total_alq_exp": pct_sobre_total_alq_exp,    # fracción
            }
        )

    return {
        "alquiler": alquiler,
        "expensas": expensas,
        "alq_exp": base_mensual_alq_exp,  # <-- NUEVO (para comparativas)
        "meses": meses,
        "porcentaje_descuento_mercadopago": _to_float(obj.get("porcentaje_descuento_mercadopago")),
        "planes": sorted(out_planes, key=lambda x: x["cuotas"]),
        "planes_raw": sorted(planes_raw, key=lambda x: x["cantidad_de_cuotas"]),
        "errors": (resp or {}).get("errors") or [],
    }
