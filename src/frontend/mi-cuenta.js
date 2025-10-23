import { AuthAPI } from './api.js';

document.addEventListener('DOMContentLoaded', async () => {
  const user = await AuthAPI.me();
  document.querySelector('#username').textContent = user.username;
  document.querySelector('#display_name').value = user.display_name || '';
  document.querySelector('#email').value = user.email || '';

  document.querySelector('#profileForm').addEventListener('submit', async (e)=>{
    e.preventDefault();
    const display_name = document.querySelector('#display_name').value.trim();
    const email = document.querySelector('#email').value.trim();
    try {
      await AuthAPI.updateMe({ display_name, email });
      alert('Perfil actualizado');
    } catch(err) { alert('Error: ' + err.message); }
  });

  document.querySelector('#passwordForm').addEventListener('submit', async (e)=>{
    e.preventDefault();
    const current = document.querySelector('#current_pw').value;
    const newPw = document.querySelector('#new_pw').value;
    const newPw2 = document.querySelector('#new_pw2').value;
    if (newPw !== newPw2) return alert('Las contraseñas no coinciden');
    try {
      await AuthAPI.changePassword(current, newPw);
      alert('Contraseña actualizada');
      e.target.reset();
    } catch(err) { alert('Error: ' + err.message); }
  });
});
