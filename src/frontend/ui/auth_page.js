function initAuthPage({ AuthAPI, doc }) {
  const form = doc.querySelector('#login-form');
  const user = doc.querySelector('#username');
  const pass = doc.querySelector('#password');
  const err  = doc.querySelector('#login-error');
  if (!form) return;
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    err.textContent = '';
    try {
      await AuthAPI.login({ username: user.value, password: pass.value });
      location.href = '/home.html';
    } catch (ex) {
      err.textContent = ex.message || 'login_failed';
    }
  });
}

module.exports = { initAuthPage };
