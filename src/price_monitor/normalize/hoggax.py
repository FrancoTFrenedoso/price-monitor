from __future__ import annotations

import re
from typing import Optional


_money_re = re.compile(r"\$?\s*([\d\.\,]+)")
_pct_re = re.compile(r"(\d+(?:[\,\.]\d+)?)\s*%")

def _parse_money(s: str) -> Optional[float]:
    if not s:
        return None
    m = _money_re.search(s)
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except Exception:
        return None

def _parse_pct_from_text(s: str) -> Optional[float]:
    if not s:
        return None
    m = _pct_re.search(s)
    if not m:
        return None
    raw = m.group(1).replace(",", ".")
    try:
        return float(raw) / 100.0
    except Exception:
        return None

def _extract_total_from_info(info: str) -> Optional[float]:
    # Busca "Importe total: $ X"
    if not info:
        return None
    # separa por frases comunes
    # preferir el que sigue a "Importe total:"
    parts = info.split("Importe total:")
    if len(parts) >= 2:
        return _parse_money(parts[1])
    # fallback: primer monto que aparezca
    return _parse_money(info)

def _extract_anticipo_from_info(info: str) -> Optional[float]:
    if not info:
        return None
    parts = info.split("Adelanto:")
    if len(parts) >= 2:
        return _parse_money(parts[1])
    return None

def _extract_desc_abs_from_info(info: str) -> Optional[float]:
    # "Te ahorrás $ X"
    if not info:
        return None
    parts = info.split("Te ahorr")
    if len(parts) >= 2:
        return _parse_money(parts[1])
    return None


def normalize_hoggax(resp: dict) -> dict:
    q = (((resp or {}).get("body") or {}).get("quotation") or {})
    rent = float(q.get("rent") or 0)
    expenses = float(q.get("expenses") or 0)
    term = int(q.get("term") or 0)

    base_total = (rent + expenses) * term if term else 0

    methods = q.get("payment_methods") or []
    out = []

    for pm in methods:
        texto = str(pm.get("texto") or "")
        precio_texto = str(pm.get("precioTexto") or "")
        info = str(pm.get("infoTexto") or "")
        importe = float(pm.get("importe") or 0)

        # detectar descuento %
        desc_pct = _parse_pct_from_text(texto)
        desc_abs = _extract_desc_abs_from_info(info)

        # total_final:
        # - si precioTexto == "Precio FINAL": importe es total
        # - si precioTexto == "Cuotas": total está en infoTexto ("Importe total")
        total_final = None
        cuota = None

        if precio_texto.lower().strip() == "precio final":
            total_final = importe
        else:
            total_final = _extract_total_from_info(info)
            cuota = importe if importe else None

        anticipo = _extract_anticipo_from_info(info)

        # Si tengo desc_pct pero no desc_abs, lo calculo desde total
        if desc_pct is not None and total_final:
            # precio sin desc = total_final / (1-desc_pct)
            if desc_pct < 1.0:
                sin_desc = total_final / (1.0 - desc_pct)
                desc_abs = desc_abs if desc_abs is not None else (sin_desc - total_final)

        # Si tengo desc_abs pero no desc_pct, lo infiero (cuando posible)
        if desc_abs is not None and total_final and desc_pct is None and (total_final + desc_abs) > 0:
            desc_pct = desc_abs / (total_final + desc_abs)

        pct_sobre_base = (total_final / base_total) if (total_final and base_total) else None

        out.append(
            {
                "metodo": texto,
                "submetodo": str(pm.get("subTexto") or ""),
                "precio_texto": precio_texto,
                "total_final": total_final,
                "cuota": cuota,
                "anticipo": anticipo,
                "desc_abs": desc_abs,
                "desc_pct": desc_pct,  # fracción: 0.15
                "pct_sobre_total_base": pct_sobre_base,  # fracción
                "info": info,
            }
        )

    return {
        "rent": rent,
        "expenses": expenses,
        "term": term,
        "base_total": base_total,
        "planes": out,
        "raw_discount_value": q.get("discount_value"),
        "errors": [],
    }
