from __future__ import annotations
from typing import Optional, List, Literal
from datetime import date
from pydantic import BaseModel, Field, constr, conint, confloat, model_validator, EmailStr

IdSPM = constr(min_length=1, strip_whitespace=True, to_lower=True)

class LoginRequest(BaseModel):
    id: IdSPM
    password: constr(min_length=1)

class RegisterRequest(BaseModel):
    id: IdSPM
    password: constr(min_length=6)
    nombre: constr(min_length=1, strip_whitespace=True)
    apellido: constr(min_length=1, strip_whitespace=True)
    rol: constr(min_length=1, strip_whitespace=True) = "Solicitante"

class MaterialSearchQuery(BaseModel):
    q: Optional[constr(min_length=1, strip_whitespace=True)] = None
    codigo: Optional[constr(min_length=1, strip_whitespace=True)] = None
    descripcion: Optional[constr(min_length=1, strip_whitespace=True)] = None
    limit: conint(ge=1, le=100000) = 100

    @model_validator(mode="after")
    def _check_filters(self) -> "MaterialSearchQuery":
        provided = [self.q, self.codigo, self.descripcion]
        if not any(value for value in provided if isinstance(value, str) and value.strip()):
            raise ValueError("Debe indicar código, descripción o un término de búsqueda")
        return self

class SolicitudItem(BaseModel):
    codigo: constr(min_length=1, strip_whitespace=True)
    descripcion: Optional[str] = None
    cantidad: conint(ge=1)
    precio_unitario: confloat(ge=0) = 0.0
    comentario: Optional[str] = None

class SolicitudBase(BaseModel):
    id_usuario: IdSPM
    centro: constr(min_length=1)
    sector: constr(min_length=1)
    justificacion: constr(min_length=5)
    centro_costos: constr(min_length=1)
    almacen_virtual: constr(min_length=1)
    criticidad: Literal["Normal", "Alta"] = "Normal"
    fecha_necesidad: date

class SolicitudDraft(SolicitudBase):
    pass

class SolicitudCreate(SolicitudBase):
    items: List[SolicitudItem] = Field(default_factory=list)

class Pagination(BaseModel):
    page: conint(ge=1) = 1
    page_size: conint(ge=1, le=100) = 50


class BudgetIncreaseCreate(BaseModel):
    centro: constr(min_length=1, strip_whitespace=True)
    sector: Optional[constr(strip_whitespace=True)] = None
    monto: confloat(gt=0)
    motivo: Optional[constr(min_length=3, strip_whitespace=True)] = None


class BudgetIncreaseDecision(BaseModel):
    accion: Literal["aprobar", "rechazar"]
    comentario: Optional[constr(strip_whitespace=True, max_length=500)] = None


class UpdatePhoneRequest(BaseModel):
    telefono: constr(min_length=5, strip_whitespace=True, max_length=30)


class UpdateMailRequest(BaseModel):
    mail: EmailStr


class AdditionalCentersRequest(BaseModel):
    centros: constr(min_length=3, strip_whitespace=True, max_length=200)
    motivo: Optional[constr(strip_whitespace=True, max_length=500)] = None


class CentroRequestDecision(BaseModel):
    accion: Literal["aprobar", "rechazar"]
    comentario: Optional[constr(strip_whitespace=True, max_length=500)] = None


class TratamientoItemUpdate(BaseModel):
    item_index: conint(ge=0)
    decision: Literal["stock", "compra", "servicio", "equivalente"]
    cantidad_aprobada: confloat(gt=0)
    codigo_equivalente: Optional[constr(strip_whitespace=True)] = None
    proveedor_sugerido: Optional[constr(strip_whitespace=True)] = None
    precio_unitario_estimado: Optional[confloat(ge=0)] = None
    comentario: Optional[constr(strip_whitespace=True)] = None


class TratamientoItemsPayload(BaseModel):
    items: List[TratamientoItemUpdate]


class RechazoTratamiento(BaseModel):
    motivo: constr(min_length=3, max_length=500, strip_whitespace=True)


class TrasladoCreate(BaseModel):
    solicitud_id: conint(ge=1)
    item_index: conint(ge=0)
    material: constr(min_length=1, strip_whitespace=True)
    um: Optional[constr(strip_whitespace=True)] = None
    cantidad: confloat(gt=0)
    origen_centro: constr(min_length=1, strip_whitespace=True)
    origen_almacen: constr(min_length=1, strip_whitespace=True)
    origen_lote: Optional[constr(strip_whitespace=True)] = None
    destino_centro: constr(min_length=1, strip_whitespace=True)
    destino_almacen: constr(min_length=1, strip_whitespace=True)


class TrasladoUpdate(BaseModel):
    status: Literal["en_transito", "recibido", "cancelado"]
    referencia: Optional[constr(strip_whitespace=True)] = None


class SolpedCreate(BaseModel):
    solicitud_id: conint(ge=1)
    item_index: conint(ge=0)
    material: constr(min_length=1, strip_whitespace=True)
    um: Optional[constr(strip_whitespace=True)] = None
    cantidad: confloat(gt=0)
    precio_unitario_est: Optional[confloat(ge=0)] = None
    numero: Optional[constr(strip_whitespace=True)] = None


class SolpedUpdate(BaseModel):
    status: Literal["liberada", "rechazada", "cancelada"]
    numero: Optional[constr(strip_whitespace=True)] = None


class PurchaseOrderCreate(BaseModel):
    solped_id: conint(ge=1)
    solicitud_id: conint(ge=1)
    proveedor_email: constr(strip_whitespace=True)
    proveedor_nombre: constr(min_length=1, strip_whitespace=True)
    numero: Optional[constr(strip_whitespace=True)] = None
    subtotal: Optional[confloat(ge=0)] = None
    moneda: Optional[constr(strip_whitespace=True)] = "USD"


class PurchaseOrderUpdate(BaseModel):
    status: Literal["enviada", "entregada_parcial", "entregada_total", "cerrada", "cancelada"]


class NotaCreate(BaseModel):
    item_index: Optional[conint(ge=0)] = None
    texto: constr(min_length=1, strip_whitespace=True)
