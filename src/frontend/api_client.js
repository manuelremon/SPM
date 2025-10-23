function _readCookie(n){
  return document.cookie.split('; ').find(r=>r.startsWith(n+'='))?.split('=')[1] || '';
}
function _csrfHeaders(){
  const t = _readCookie('spm_csrf_token');
  return t ? {'X-CSRF-Token': t} : {};
}
// Cliente de API minimal. Intenta rutas comunes automáticamente.
const BASE =
  window.__API_BASE__ ||
  `${location.protocol}//${location.hostname}:${location.port}`;

const JSON_OPTS = { headers: { "Content-Type": "application/json" }, credentials: "include" };

async function xfetch(url, opts = {}) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    body: JSON.stringify(opts.body || {}),
    credentials: 'include',
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const msg = data?.message || data?.error || `HTTP ${r.status}`;
    const e = new Error(msg);
    e.status = r.status;
    e.data = data;
    throw e;
  }
  return data;
}

async function tryLogin(body) {
  // intenta /api/auth/login y /auth/login
  const paths = [
    `${BASE}/api/auth/login`,
    `${BASE}/auth/login`,
  ];
  let lastErr;
  for (const p of paths) {
    try {
      return await xfetch(p, { body, headers: _csrfHeaders() });
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr;
}

export const AuthAPI = {
  login: tryLogin,
  logout: async function() {
    const url = `${BASE}/api/auth/logout`;
    await xfetch(url, { headers: _csrfHeaders() });
  }
};

// Asignar a window para uso como script
window.API = AuthAPI;
