# API SPM – Contratos Clave

Todos los endpoints responden JSON (`Content-Type: application/json`). Las respuestas de error siguen la forma:

```json
{
  "ok": false,
  "error": { "code": "CODE", "message": "Descripción" },
  "request_id": "abc123" // opcional, siempre que haya request id disponible
}
```

La sesion se mantiene en una cookie **HttpOnly** llamada `access_token`; salvo que se configure lo contrario, usa `SameSite=Lax`.

## Autenticación

### `POST /api/login`
Inicia sesión usando `id SPN` o email. Devuelve el usuario y setea cookies.

**Request**
```json
{
  "id": "tester",
  "password": "secret123"
}
```

**Response (200)**
```json
{
  "ok": true,
  "usuario": {
    "id": "tester",
    "nombre": "Test",
    "apellido": "User",
    "rol": "Admin",
    "posicion": "Analyst",
    "sector": "QA",
    "mail": "tester@example.com",
    "telefono": "+5400000000",
    "id_red": "RED1",
    "jefe": "Boss",
    "gerente1": "Boss2",
    "gerente2": "Boss3",
    "centros": ["C1"]
  },
  "request_id": "..."
}
```

**Errores**
- `401 AUTH` credenciales inválidas.
**Errores**
- `401 AUTH` credenciales invalidas.
- `429 RATE_LIMIT` mas de 5 intentos fallidos en 5 minutos por IP.

> Nota: no existe un endpoint de refresh; si la cookie vence deberas iniciar sesion nuevamente.

**Response (200)**
```json
{ "ok": true, "request_id": "..." }
```

## Identidad

### `GET /api/me`
Devuelve los datos del usuario autenticado.

**Response (200)**
```json
{
  "ok": true,
  "usuario": {
    "id": "tester",
    "nombre": "Test",
    "apellido": "User",
    "...": "..."
  },
  "request_id": "..."
}
```

**Errores**
- `401 NOAUTH` sin sesión.
- `401 BADTOKEN` token expirado/inválido (el frontend reintenta refrescar automáticamente).
- `404 NOUSER` si el usuario ya no existe.

## Salud

### `GET /api/health`
```json
{
  "ok": true,
  "db": true
}
```

## Materiales

### `GET /api/materiales`
Acepta filtros `q`, `codigo`, `descripcion`, `limit` (1–100000). Al menos un filtro de texto es obligatorio.

**Ejemplo**
```
GET /api/materiales?q=cable&limit=50
```

**Response (200)**
```json
[
  {
    "codigo": "MAT-01",
    "descripcion": "Cable de prueba",
    "descripcion_larga": "Cable de prueba largo",
    "unidad": "m",
    "precio_usd": 10.5
  }
]
```

**Errores**
- `422 HTTP_422` si no se envían criterios de búsqueda válidos.

## Actualizaciones de perfil

Todas requieren sesión activa y devuelven `{ "ok": true }` con el dato actualizado:

| Endpoint                               | Payload JSON                        | Comentario                        |
|----------------------------------------|-------------------------------------|------------------------------------|
| `POST /api/me/telefono`                | `{ "telefono": "+540..." }`         | Valida largo 5–30.                 |
| `POST /api/me/mail`                    | `{ "mail": "usuario@dominio.com" }` | Normaliza a minúsculas.            |
| `POST /api/me/centros/solicitud`       | `{ "centros": "ABC,DEF", "motivo": "" }` | Persiste solicitud + notificaciones. |

Errores comunes: `401 NOAUTH`, `401 BADTOKEN`, `403` o `422` según validación.

## Convenciones

- Todas las rutas devuelven `Cache-Control: no-store`.
- Logs y respuestas incluyen `request_id`. Enviar `X-Request-Id`/`X-Correlation-Id` fuerza un ID propio.
- Los mensajes de error nunca incluyen stack traces cuando `SPM_DEBUG=0`.
