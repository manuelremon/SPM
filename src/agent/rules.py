from typing import Tuple, List

REQUIRED_ADJUNTOS = {"VALV-2IN-INOX": True, "BOMBA-3HP": True}
VALID_UOM = {"UN", "PAR", "M", "KG"}

APPROVAL_LIMITS = [
    (0, 5000, ["JefeArea"]),
    (5000, 20000, ["JefeArea", "Compras"]),
    (20000, 99999999, ["Gerencia", "Compras"])
]

def validate(codigo: str, uom: str, planta: str, adjuntos_ok: bool, monto: float | None) -> Tuple[bool, List[str], List[str]]:
    errores: List[str] = []
    warnings: List[str] = []

    if uom not in VALID_UOM:
        errores.append(f"UoM no válida: {uom}")

    if REQUIRED_ADJUNTOS.get(codigo, False) and not adjuntos_ok:
        errores.append("Faltan adjuntos obligatorios (ficha técnica/certificados)")

    if not planta:
        errores.append("Planta es obligatoria")

    if monto is not None:
        for low, high, approvers in APPROVAL_LIMITS:
            if low <= monto < high:
                warnings.append(f"Aprobación sugerida: {' → '.join(approvers)}")
                break

    return (len(errores) == 0), errores, warnings

def prioritize(motivo: str, impacto: str | None) -> tuple[str, list[str]]:
    motivo_l = (motivo or "").lower()
    razones = []
    if "parada" in motivo_l:
        razones.append("Parada de planta")
        return "CRITICO", razones
    if impacto and "stockout" in impacto.lower():
        razones.append("Riesgo de stockout")
        return "ALTO", razones
    if "seguridad" in motivo_l:
        razones.append("Impacto en seguridad")
        return "ALTO", razones
    return "MEDIO", ["Operación rutinaria"]

