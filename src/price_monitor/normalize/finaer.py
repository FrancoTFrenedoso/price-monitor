from __future__ import annotations

def normalize_finaer(resp: dict) -> dict:
    obj = (resp or {}).get("object") or {}
    meses = int(obj.get("duracion_del_contrato_en_meses") or 0)

    alquiler = float(obj.get("alquiler") or 0)
    expensas = float(obj.get("expensas") or 0)
    base_mensual_alq = alquiler
    base_mensual_alq_exp = alquiler + expensas

    planes = obj.get("posibles_planes_de_cuotas") or []

    out_planes = []
    for p in planes:
        cuotas = int(p.get("cantidad_de_cuotas") or 0)
        monto_final = float(p.get("monto_final") or 0)
        honorario = float(p.get("honorario_sin_descuentos") or 0)
        descuento = float(p.get("descuento_aplicado") or 0)

        costo_mensual_equiv = (monto_final / meses) if meses else None
        pct_desc_real = (descuento / honorario) if honorario else None

        pct_sobre_total_alquiler = (monto_final / (base_mensual_alq * meses)) if (base_mensual_alq and meses) else None
        pct_sobre_total_alq_exp = (monto_final / (base_mensual_alq_exp * meses)) if (base_mensual_alq_exp and meses) else None

        out_planes.append({
            "cuotas": cuotas,
            "monto_final": monto_final,
            "monto_cuotas": float(p.get("monto_cuotas") or 0),
            "anticipo": float(p.get("anticipo") or 0),

            "honorario_sin_descuentos": honorario,
            "descuento_aplicado": descuento,
            "pct_descuento_aplicado_api": float(p.get("porcentaje_de_descuento_aplicado") or 0),
            "pct_descuento_real": pct_desc_real,

            "fecha_limite_descuento": p.get("fecha_limite_descuento"),
            "costo_mensual_equiv": costo_mensual_equiv,

            "pct_sobre_total_alquiler": pct_sobre_total_alquiler,
            "pct_sobre_total_alq_exp": pct_sobre_total_alq_exp,
        })

    return {
        "alquiler": alquiler,
        "expensas": expensas,
        "meses": meses,
        "porcentaje_descuento_mercadopago": obj.get("porcentaje_descuento_mercadopago"),
        "planes": sorted(out_planes, key=lambda x: x["cuotas"]),
        "errors": resp.get("errors") or [],
    }
