function leerCookie(name) {
  return document.cookie.split('; ').find(r => r.startsWith(name + '='))?.split('=')[1] || '';
}

async function login(username, password) {
  try {
    const data = await window.API.login({ username, password });
    window.location.href = '/home.html';
  } catch (e) {
    alert(e.message || 'Error');
  }
}

// Ejemplo de uso: agregar formulario
document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('#login-form');
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const username = document.querySelector('#username').value;
      const password = document.querySelector('#password').value;
      login(username, password);
    });
  }
});
