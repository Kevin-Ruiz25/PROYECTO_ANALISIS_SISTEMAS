"""Reportes para el encargado del centro de salud y campañas masivas.

Todo se calcula a partir de una "foto" de cada niño (`snapshot`): último control de peso/talla,
percentiles y estado de su esquema de vacunación. Los reportes son tablas genéricas
(`{title, columns, rows}`) para poder mostrarlas igual en pantalla, en Excel y en PDF.

Definiciones:
  - Bajo peso:   percentil de peso del último control < 5.   Sobrepeso: > 95.
  - Dosis exigible: ya le toca según su edad (completa + atrasada + pendiente).
  - Cobertura:   dosis completas / dosis exigibles.
  - Esquema incompleto: tiene al menos una dosis atrasada o pendiente.
"""
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import growth, models, vaccination
from .alerts import HIGH_PERCENTILE, LOW_PERCENTILE

NO_COMMUNITY = "Sin comunidad"
AGE_GROUPS = [("0 a 11 meses", 0, 11), ("12 a 23 meses", 12, 23), ("24 a 35 meses", 24, 35),
              ("36 a 60 meses", 36, 60), ("Mayores de 60 meses", 61, 10_000)]


def snapshot(child, catalog, today: date) -> dict:
    records = sorted(child.growth_records, key=lambda r: r.measured_on)
    last = records[-1] if records else None
    card = vaccination.build_card(child, catalog, today)
    s = card["summary"]
    wp = last.weight_percentile if last else None
    return {
        "child": child,
        "child_id": child.id, "name": child.full_name, "sex": child.sex.value,
        "birth_date": child.birth_date,
        "age_months": int(growth.age_in_months(child.birth_date, today)),
        "community_id": child.community_id,
        "community": child.community.name if child.community else NO_COMMUNITY,
        "last_measured": last.measured_on if last else None,
        "weight_kg": last.weight_kg if last else None,
        "height_cm": last.height_cm if last else None,
        "weight_p": wp,
        "height_p": last.height_percentile if last else None,
        "low_weight": wp is not None and wp < LOW_PERCENTILE,
        "high_weight": wp is not None and wp > HIGH_PERCENTILE,
        "doses_done": s["completa"], "doses_overdue": s["atrasada"], "doses_pending": s["pendiente"],
        "doses_due": s["completa"] + s["atrasada"] + s["pendiente"],
        "items": card["items"],
        "parents": list(child.parents),
    }


def snapshots(db: Session, today: date | None = None, community_id: int | None = None) -> list[dict]:
    today = today or date.today()
    catalog = db.scalars(select(models.Vaccine)).all()
    stmt = select(models.Child).order_by(models.Child.full_name)
    if community_id:
        stmt = stmt.where(models.Child.community_id == community_id)
    return [snapshot(c, catalog, today) for c in db.scalars(stmt).all()]


def _incomplete(s: dict) -> bool:
    return s["doses_overdue"] + s["doses_pending"] > 0


def _pct(num: float, den: float) -> float | None:
    return round(100 * num / den, 1) if den else None


def _avg(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def _round(v, n=1):
    return None if v is None else round(v, n)


def summary(snaps: list[dict]) -> dict:
    due = sum(s["doses_due"] for s in snaps)
    done = sum(s["doses_done"] for s in snaps)
    return {
        "children": len(snaps),
        "low_weight": sum(s["low_weight"] for s in snaps),
        "high_weight": sum(s["high_weight"] for s in snaps),
        "incomplete_vaccines": sum(_incomplete(s) for s in snaps),
        "without_measurements": sum(s["last_measured"] is None for s in snaps),
        "vaccine_coverage_pct": _pct(done, due),
    }


# ---------------------------------------------------------------- tablas
def _col(key, label, kind="text"):
    return {"key": key, "label": label, "kind": kind}


_CHILD_COLS = [_col("name", "Niño"), _col("sex", "Sexo"), _col("age", "Edad"), _col("community", "Comunidad")]


def _age_text(months: int) -> str:
    if months < 24:
        return f"{months} {'mes' if months == 1 else 'meses'}"
    y, m = divmod(months, 12)
    return f"{y} años {m} m" if m else f"{y} años"


def _child_row(s: dict) -> dict:
    return {"name": s["name"], "sex": "F" if s["sex"] == "F" else "M",
            "age": _age_text(s["age_months"]), "community": s["community"]}


def _weight_report(snaps, title, flag):
    rows = []
    for s in sorted((x for x in snaps if x[flag]), key=lambda x: x["weight_p"] if flag == "low_weight" else -x["weight_p"]):
        rows.append({**_child_row(s), "last_measured": s["last_measured"], "weight_kg": s["weight_kg"],
                     "height_cm": s["height_cm"], "weight_p": _round(s["weight_p"]), "height_p": _round(s["height_p"])})
    cols = _CHILD_COLS + [_col("last_measured", "Último control", "date"), _col("weight_kg", "Peso (kg)", "float"),
                          _col("height_cm", "Talla (cm)", "float"), _col("weight_p", "Percentil peso", "float"),
                          _col("height_p", "Percentil talla", "float")]
    return {"title": title, "columns": cols, "rows": rows}


def _incomplete_report(snaps):
    rows = []
    for s in sorted((x for x in snaps if _incomplete(x)), key=lambda x: -x["doses_overdue"]):
        late = [f"{i['vaccine'].name} (dosis {i['vaccine'].dose_number})" for i in s["items"] if i["status"] == "atrasada"]
        rows.append({**_child_row(s), "doses_overdue": s["doses_overdue"], "doses_pending": s["doses_pending"],
                     "doses_done": s["doses_done"], "detail": "; ".join(late[:4]) + (f" y {len(late) - 4} más" if len(late) > 4 else "")})
    cols = _CHILD_COLS + [_col("doses_overdue", "Atrasadas", "int"), _col("doses_pending", "Pendientes", "int"),
                          _col("doses_done", "Completas", "int"), _col("detail", "Dosis atrasadas")]
    return {"title": "Niños con vacunas incompletas", "columns": cols, "rows": rows}


def _group(snaps, key_fn, order=None):
    groups = defaultdict(list)
    for s in snaps:
        groups[key_fn(s)].append(s)
    keys = order or sorted(groups, key=lambda k: (k == NO_COMMUNITY, k))
    return [(k, groups.get(k, [])) for k in keys]


def _coverage_report(snaps):
    rows = []
    for name, grp in _group(snaps, lambda s: s["community"]):
        due, done = sum(s["doses_due"] for s in grp), sum(s["doses_done"] for s in grp)
        incomplete = sum(_incomplete(s) for s in grp)
        rows.append({"community": name, "children": len(grp), "doses_due": due, "doses_done": done,
                     "coverage": _pct(done, due), "incomplete": incomplete,
                     "up_to_date_pct": _pct(len(grp) - incomplete, len(grp))})
    tot_due, tot_done = sum(s["doses_due"] for s in snaps), sum(s["doses_done"] for s in snaps)
    inc = sum(_incomplete(s) for s in snaps)
    if rows:
        rows.append({"community": "TOTAL", "children": len(snaps), "doses_due": tot_due, "doses_done": tot_done,
                     "coverage": _pct(tot_done, tot_due), "incomplete": inc,
                     "up_to_date_pct": _pct(len(snaps) - inc, len(snaps))})
    cols = [_col("community", "Comunidad"), _col("children", "Niños", "int"), _col("doses_due", "Dosis exigibles", "int"),
            _col("doses_done", "Dosis aplicadas", "int"), _col("coverage", "Cobertura (%)", "float"),
            _col("incomplete", "Niños con esquema incompleto", "int"), _col("up_to_date_pct", "Niños al día (%)", "float")]
    return {"title": "Cobertura de vacunación por comunidad", "columns": cols, "rows": rows}


def _growth_row(label, grp, label_key):
    measured = [s for s in grp if s["last_measured"]]
    return {label_key: label, "children": len(grp), "measured": len(measured),
            "avg_weight": _avg([s["weight_kg"] for s in measured]), "avg_height": _avg([s["height_cm"] for s in measured]),
            "avg_weight_p": _avg([s["weight_p"] for s in measured]), "avg_height_p": _avg([s["height_p"] for s in measured]),
            "low": sum(s["low_weight"] for s in grp), "high": sum(s["high_weight"] for s in grp)}


def _growth_cols(label_key, label):
    return [_col(label_key, label), _col("children", "Niños", "int"), _col("measured", "Con controles", "int"),
            _col("avg_weight", "Peso promedio (kg)", "float"), _col("avg_height", "Talla promedio (cm)", "float"),
            _col("avg_weight_p", "Percentil de peso promedio", "float"), _col("avg_height_p", "Percentil de talla promedio", "float"),
            _col("low", "Bajo peso", "int"), _col("high", "Sobrepeso", "int")]


def _growth_report(snaps):
    rows = [_growth_row(n, g, "community") for n, g in _group(snaps, lambda s: s["community"])]
    return {"title": "Crecimiento promedio por comunidad", "columns": _growth_cols("community", "Comunidad"), "rows": rows}


def _growth_age_report(snaps):
    def bucket(s):
        return next(n for n, lo, hi in AGE_GROUPS if lo <= s["age_months"] <= hi)
    rows = [_growth_row(n, g, "group") for n, g in _group(snaps, bucket, [n for n, _, _ in AGE_GROUPS]) if g]
    return {"title": "Crecimiento promedio por grupo de edad", "columns": _growth_cols("group", "Grupo de edad"), "rows": rows}


KINDS = {
    "bajo-peso": lambda sn: _weight_report(sn, "Niños con bajo peso (percentil < 5)", "low_weight"),
    "sobrepeso": lambda sn: _weight_report(sn, "Niños con sobrepeso (percentil > 95)", "high_weight"),
    "vacunas-incompletas": _incomplete_report,
    "cobertura": _coverage_report,
    "crecimiento": _growth_report,
    "crecimiento-edad": _growth_age_report,
}
# Los reportes de cobertura y crecimiento comparan comunidades: no se filtran por una sola.
UNFILTERED = {"cobertura"}


def build(kind: str, snaps: list[dict]) -> dict:
    return KINDS[kind](snaps)


# ---------------------------------------------------------------- campañas
VACC_FILTERS = {"todos", "con_pendientes", "atrasadas", "al_dia"}


def campaign_targets(snaps: list[dict], community_ids: list[int] | None, age_min: int, age_max: int,
                     vaccination_filter: str, vaccine_name: str | None) -> list[dict]:
    """Niños que cumplen los filtros de la campaña (edad en meses, comunidad y estado de vacunación)."""
    out = []
    for s in snaps:
        if community_ids and s["community_id"] not in community_ids:
            continue
        if not age_min <= s["age_months"] <= age_max:
            continue
        items = [i for i in s["items"] if not vaccine_name or i["vaccine"].name == vaccine_name]
        overdue = any(i["status"] == "atrasada" for i in items)
        pending = any(i["status"] == "pendiente" for i in items)
        ok = {"todos": True, "atrasadas": overdue, "con_pendientes": overdue or pending,
              "al_dia": not overdue and not pending}[vaccination_filter]
        if ok:
            out.append(s)
    return out


def campaign_recipients(targets: list[dict]) -> dict[int, dict]:
    """Un solo mensaje por padre/tutor, aunque tenga varios niños en la campaña."""
    by_parent: dict[int, dict] = {}
    for s in targets:
        for p in s["parents"]:
            entry = by_parent.setdefault(p.id, {"parent": p, "children": []})
            entry["children"].append(s["name"])
    return by_parent
