"""Cálculo de percentiles de crecimiento con el método LMS de la OMS.

Referencia: Patrones de crecimiento infantil de la OMS, 0 a 60 meses.
- Peso para la edad.
- Longitud/talla para la edad: hasta los 24 meses se usa la longitud (acostado) y
  desde los 24 meses la talla (de pie), que es 0.7 cm menor. Por eso la curva de
  talla tiene un pequeño escalón a los 24 meses, tal como en las tablas oficiales.

Fórmula conceptual:
    Z = ((X / M)^L - 1) / (L * S)        (si L = 0:  Z = ln(X / M) / S)
    percentil = Φ(Z) * 100               (Φ = distribución normal estándar)
"""
import json
import math
from datetime import date
from pathlib import Path

DAYS_PER_MONTH = 30.4375
MAX_MONTHS = 60
SWITCH_MONTH = 24  # longitud -> talla

_DATA = json.loads((Path(__file__).parent / "data" / "who_lms.json").read_text(encoding="utf-8"))

# z-scores de los percentiles que se grafican (P5 y P95 son los umbrales de alerta)
CURVE_PERCENTILES = {"p5": -1.6449, "p25": -0.6745, "p50": 0.0, "p75": 0.6745, "p95": 1.6449}


def age_in_months(birth: date, on: date) -> float:
    return (on - birth).days / DAYS_PER_MONTH


def _table(indicator: str, age: float) -> tuple[str, int]:
    """Devuelve (nombre de la tabla, mes inicial de esa tabla)."""
    if indicator == "weight":
        return "weight", 0
    return ("height_lying", 0) if age < SWITCH_MONTH else ("height_standing", SWITCH_MONTH)


def lms_at(indicator: str, sex: str, age: float):
    """L, M, S interpolados linealmente entre meses completos. None si fuera de rango."""
    if age < 0 or age > MAX_MONTHS:
        return None
    table, start = _table(indicator, age)
    rows = _DATA[table][sex]
    pos = age - start
    lo = int(pos)
    hi = min(lo + 1, len(rows) - 1)
    t = pos - lo
    a, b = rows[lo], rows[hi]
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def z_score(x: float, L: float, M: float, S: float) -> float:
    if abs(L) < 1e-9:
        return math.log(x / M) / S
    return ((x / M) ** L - 1) / (L * S)


def percentile_from_z(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2))) * 100


def percentile(indicator: str, sex: str, age: float, value: float) -> float | None:
    lms = lms_at(indicator, sex, age)
    if lms is None:
        return None
    return round(percentile_from_z(z_score(value, *lms)), 1)


def value_at_z(L: float, M: float, S: float, z: float) -> float:
    if abs(L) < 1e-9:
        return M * math.exp(S * z)
    return M * (1 + L * S * z) ** (1 / L)


def reference_curves(sex: str) -> dict:
    """Curvas de referencia mes a mes (0-60) para peso y talla."""
    result = {"max_months": MAX_MONTHS, "weight": [], "height": []}
    for indicator in ("weight", "height"):
        for month in range(MAX_MONTHS + 1):
            L, M, S = lms_at(indicator, sex, float(month))
            row = {"month": month}
            for key, z in CURVE_PERCENTILES.items():
                row[key] = round(value_at_z(L, M, S, z), 2)
            result[indicator].append(row)
    return result


def compute_for(birth_date: date, sex: str, measured_on: date, weight_kg: float, height_cm: float) -> dict:
    age = age_in_months(birth_date, measured_on)
    return {
        "age_months": round(age, 2),
        "weight_percentile": percentile("weight", sex, age, weight_kg),
        "height_percentile": percentile("height", sex, age, height_cm),
    }


def recompute_records(child) -> None:
    """Recalcula percentiles de un niño (si cambió su fecha de nacimiento o sexo)."""
    for r in child.growth_records:
        for k, v in compute_for(child.birth_date, child.sex.value, r.measured_on, r.weight_kg, r.height_cm).items():
            setattr(r, k, v)
