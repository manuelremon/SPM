from fastapi import FastAPI
from agent.models import SuggestRequest, SuggestResponse, ValidateRequest, ValidateResponse, PriorityRequest, PriorityResponse
from agent.catalog import Catalog
from agent.rules import validate, prioritize
from agent.llm import normalize_description

app = FastAPI(title="Agente Solicitudes de Materiales (MVP)")
CAT = Catalog()

@app.post("/agent/suggest_line", response_model=SuggestResponse)
async def suggest_line(req: SuggestRequest):
    norm = await normalize_description(req.texto)
    row, conf = CAT.search(norm, req.planta)
    if not row:
        return SuggestResponse(codigo=None, descripcion_normalizada=norm, uom=None, confianza=conf, explicacion="Sin match en catálogo; revisar manualmente")
    return SuggestResponse(
        codigo=row.get("codigo"),
        descripcion_normalizada=norm,
        uom=row.get("uom"),
        confianza=conf,
        explicacion=f"Match por texto normalizado y planta '{req.planta or 'cualquiera'}'"
    )

@app.post("/agent/validate", response_model=ValidateResponse)
async def validate_line(req: ValidateRequest):
    ok, errs, warns = validate(req.codigo, req.uom, req.planta, req.adjuntos_ok, req.monto_estimado)
    return ValidateResponse(ok=ok, errores=errs, warnings=warns)

@app.post("/agent/priority", response_model=PriorityResponse)
async def priority(req: PriorityRequest):
    nivel, razones = prioritize(req.motivo, req.impacto)
    return PriorityResponse(nivel=nivel, razones=razones)
