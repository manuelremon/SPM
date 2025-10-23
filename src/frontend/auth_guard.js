import { AuthAPI } from './api.js';
export async function ensureAuth({ redirectTo = '/index.html' } = {}) {
  try { await AuthAPI.me(); }
  catch { location.href = redirectTo; }
}
