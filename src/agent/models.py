from pydantic import BaseModel, Field
from typing import Optional

class SuggestRequest(BaseModel):
    texto: str = Field(..., description="Texto libre del usuario")
    planta: Optional[str] = None

class SuggestResponse(BaseModel):
    codigo: Optional[str]
    descripcion_normalizada: str
    uom: Optional[str]
    confianza: float
    explicacion: str

class ValidateRequest(BaseModel):
    codigo: str
    uom: str
    planta: str
    adjuntos_ok: bool = False
    monto_estimado: Optional[float] = None

class ValidateResponse(BaseModel):
    ok: bool
    errores: list[str]
    warnings: list[str]

class PriorityRequest(BaseModel):
    motivo: str
    impacto: Optional[str] = None

class PriorityResponse(BaseModel):
    nivel: str
    razones: list[str]

