// Smoke test for B3 login UI and AuthAPI
(async () => {
  // Simulate browser environment with jsdom
  const { JSDOM } = require('jsdom');
  const fs = require('fs');
  const path = require('path');

  // Load index.html
  const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
  const dom = new JSDOM(html, { runScripts: 'dangerously', resources: 'usable', url: 'http://localhost/' });
  const { window } = dom;

  // Wait for scripts to load
  await new Promise(resolve => {
    window.addEventListener('DOMContentLoaded', resolve);
  });

  // Check AuthAPI global
  if (typeof window.AuthAPI !== 'object' || typeof window.AuthAPI.login !== 'function') {
    throw new Error('AuthAPI.login no está disponible en window');
  }

  // Test AuthAPI.login with dummy credentials
  let loginError = null;
  try {
    await window.AuthAPI.login({ username: 'x', password: 'y' });
  } catch (e) {
    loginError = e;
  }

  // Simulate filling the form and submitting
  window.document.getElementById('username').value = 'x';
  window.document.getElementById('password').value = 'y';
  const submitBtn = window.document.getElementById('login-submit');
  submitBtn.click();

  // Check loading state
  if (submitBtn.textContent !== 'Ingresando...') {
    throw new Error('El botón no muestra "Ingresando..." al enviar');
  }

  // Wait for login to finish
  await new Promise(r => setTimeout(r, 1500));

  // Check error message
  const errBox = window.document.getElementById('login-error');
  if (loginError && !errBox.textContent) {
    throw new Error('No se muestra mensaje de error al fallo de login');
  }

  console.log('Smoke test B3 login: OK');
})();
