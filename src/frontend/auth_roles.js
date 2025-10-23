import { AuthAPI } from './api.js';
export async function ensureRole(required = []) {
  const user = await AuthAPI.me();
  if (!required.length) return user;
  const ok = user.roles?.some(r => required.includes(r));
  if (!ok) location.href = '/index.html';
  return user;
}
