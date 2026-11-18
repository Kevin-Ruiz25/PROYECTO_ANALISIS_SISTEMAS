"""Catálogo inicial de vacunas.

Basado en el esquema regular del MSPAS de Guatemala (publicado en 2026).
IMPORTANTE: el esquema cambia según la disponibilidad de vacunas y la situación
epidemiológica (p. ej. hexavalente en lugar de pentavalente + polio inyectada).
Verifica este listado con tu centro de salud y ajústalo desde la pantalla
"Catálogo de vacunas" (administrador o encargado del centro).

Formato: (nombre, número de dosis, edad recomendada en meses; 0 = al nacer)
"""
PENTA = "Pentavalente / Hexavalente"
POLIO = "Poliomielitis (IPV / OPV)"

SEED_VACCINES = [
    ("Hepatitis B", 1, 0),
    ("BCG (tuberculosis)", 1, 0),
    (PENTA, 1, 2), (POLIO, 1, 2), ("Rotavirus", 1, 2), ("Neumococo", 1, 2),
    (PENTA, 2, 4), (POLIO, 2, 4), ("Rotavirus", 2, 4), ("Neumococo", 2, 4),
    (PENTA, 3, 6), (POLIO, 3, 6), ("Influenza", 1, 6),
    ("SPR (sarampión, rubéola y paperas)", 1, 12), ("Neumococo", 3, 12), ("Influenza", 2, 12),
    ("Varicela", 1, 15),
    ("SPR (sarampión, rubéola y paperas)", 2, 18), (PENTA, 4, 18), (POLIO, 4, 18),
    ("DPT", 1, 48), (POLIO, 5, 48), ("Varicela", 2, 48),
]
