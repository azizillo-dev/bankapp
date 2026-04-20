// NexBank — main.js

// Password toggle
function togglePw(id) {
  const inp = document.getElementById(id);
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

// Toast notification
function showToast(msg, duration = 3000) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), duration);
}

// Auto-dismiss flash after 5s
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.flash').forEach(f => {
    setTimeout(() => f.remove(), 5000);
  });
});
