import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"

SYSTEM_PROMPT = (
    "Eres un asistente de planificación de materiales. Normaliza descripciones cortas de materiales en estilo catálogo. "
    "Devuelve una frase breve, sin adjetivos innecesarios."
)

async def normalize_description(texto: str) -> str:
    prompt = f"Normaliza para catálogo: {texto}"
    payload = {"model": MODEL, "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}", "stream": False}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(OLLAMA_URL, json=payload)
        r.raise_for_status()
        data = r.json()
        return (data.get("response") or texto).strip()

