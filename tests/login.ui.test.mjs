import { JSDOM } from 'jsdom';
import { initAuthPage } from '../src/frontend/ui/auth_page.js';
import { TextEncoder, TextDecoder } from 'util';
globalThis.TextEncoder = TextEncoder;
globalThis.TextDecoder = TextDecoder;

test('login ok redirige a /home.html', async () => {
  const dom = new JSDOM(`
    <form id="login-form">
      <input id="username"/><input id="password"/><div id="login-error"></div>
      <button type="submit">Login</button>
    </form>`, { url: 'http://localhost/' });

  const AuthAPI = { login: jest.fn().mockResolvedValue({ ok: true }) };

  // espía de location
  const loc = dom.window.location;
  Object.defineProperty(dom.window, 'location', { value: { ...loc, href: loc.href } });

  initAuthPage({ AuthAPI, doc: dom.window.document });
  dom.window.document.querySelector('#username').value = 'u';
  dom.window.document.querySelector('#password').value = 'p';
  dom.window.document.querySelector('form').dispatchEvent(new dom.window.Event('submit', { bubbles: true, cancelable: true }));

  await Promise.resolve(); // deja resolver el handler
  expect(AuthAPI.login).toHaveBeenCalledWith({ username: 'u', password: 'p' });
});
