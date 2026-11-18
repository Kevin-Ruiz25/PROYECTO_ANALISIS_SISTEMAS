"""Lógica del esquema de vacunación: fechas recomendadas, estados y próxima dosis."""
import calendar
from datetime import date, timedelta

GRACE_DAYS = 30          # margen después de la fecha recomendada antes de considerarla atrasada
MIN_INTERVAL_DAYS = 28   # intervalo mínimo entre dosis cuando el niño ya va tarde


def add_months(d: date, months: int) -> date:
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def card_status(due: date, applied_on: date | None, today: date | None = None) -> str:
    """completa | atrasada | pendiente (corresponde ahora) | proxima (aún no toca)."""
    today = today or date.today()
    if applied_on:
        return "completa"
    if today > due + timedelta(days=GRACE_DAYS):
        return "atrasada"
    if today >= due:
        return "pendiente"
    return "proxima"


def suggest_next_dose(birth: date, applied_on: date, vaccine, catalog) -> date | None:
    """Fecha sugerida de la siguiente dosis de la misma vacuna (misma serie por nombre)."""
    later = [v for v in catalog if v.name == vaccine.name and v.dose_number > vaccine.dose_number]
    if not later:
        return None
    nxt = min(later, key=lambda v: v.dose_number)
    due = add_months(birth, nxt.recommended_age_months)
    return max(due, applied_on + timedelta(days=MIN_INTERVAL_DAYS))


def build_card(child, catalog, today: date | None = None) -> dict:
    today = today or date.today()
    applied = {r.vaccine_id: r for r in child.vaccinations}
    items = []
    summary = {"total": 0, "completa": 0, "atrasada": 0, "pendiente": 0, "proxima": 0}
    for v in sorted(catalog, key=lambda x: (x.recommended_age_months, x.name, x.dose_number)):
        rec = applied.get(v.id)
        due = add_months(child.birth_date, v.recommended_age_months)
        status = card_status(due, rec.applied_on if rec else None, today)
        summary["total"] += 1
        summary[status] += 1
        items.append({
            "vaccine": v, "due_date": due, "status": status,
            "vaccination_id": rec.id if rec else None,
            "applied_on": rec.applied_on if rec else None,
            "next_dose_on": rec.next_dose_on if rec else None,
        })
    return {"child_id": child.id, "summary": summary, "items": items}
