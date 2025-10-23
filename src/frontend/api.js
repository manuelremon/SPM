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
    try { return await xfetch(p, { body }); }
    catch (e) { lastErr = e; }
  }
  throw lastErr || new Error('Login no disponible');
}

export const AuthAPI = {
  async login({ username, password }) {
    const r = await fetch(`${BASE}/api/auth/login`, {
      method: 'POST',
      ...JSON_OPTS,
      body: JSON.stringify({ username, password })
    });
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      const err = new Error(e.error || 'login_failed');
      err.status = r.status;
      throw err;
    }
    return r.json();
  },
  async me() {
    const r = await fetch('/api/auth/me', { credentials: 'include' });
    if (!r.ok) throw new Error('unauthorized');
    const data = await r.json();
    return data.user; // { username, roles, email, display_name }
  },
  async updateMe(payload) {
    const r = await fetch('/api/users/me', {
      method: 'PUT',
      headers: {'Content-Type':'application/json'},
      credentials: 'include',
      body: JSON.stringify(payload)
    });
    if (!r.ok) throw new Error((await r.json()).error || 'update_failed');
    return true;
  },
  async changePassword(current, newPw) {
    const r = await fetch('/api/auth/password', {
      method: 'PUT',
      headers: {'Content-Type':'application/json'},
      credentials: 'include',
      body: JSON.stringify({ current, new: newPw })
    });
    if (!r.ok) throw new Error((await r.json()).error || 'change_failed');
    return true;
  },
  async logout() {
    const r = await fetch(`${BASE}/api/auth/logout`, { method: 'POST', credentials: "include" });
    if (!r.ok) throw new Error('logout_failed');
    return r.json();
  }
};

export const FilesAPI = {
  async list() {
    const r = await fetch('/api/files' + (this._qs||''), { credentials:'include' });
    if (!r.ok) throw new Error('list_failed');
    return await r.json();
  },
  query(params){ // {page, per_page, q, sort, order}
    const u = new URLSearchParams(params || {});
    this._qs = u.toString() ? `?${u.toString()}` : '';
    return this;
  },
  async upload(file) {
    const fd = new FormData();
    fd.append('file', file);
  const r = await fetch('/api/files', { method:'POST', body: fd, credentials:'include', headers: _csrfHeaders() });
    if (r.status === 201) return await r.json();
    if (r.ok) return await r.json(); // duplicate_of
    const err = await r.json().catch(()=>({error:'upload_failed'}));
    throw new Error(err.error || 'upload_failed');
  },
  downloadUrl(id){ return `/api/files/${id}`; },
  async remove(id){
  const r = await fetch(`/api/files/${id}`, { method:'DELETE', credentials:'include', headers: _csrfHeaders() });
    if (!r.ok) throw new Error('delete_failed');
    return true;
  }
};

// Exponer para depuración
window.AuthAPI = AuthAPI;
