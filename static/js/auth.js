// ── Auth JS ──────────────────────────────────────────────────
// Redirect if already logged in
fetch('/api/auth/me', { credentials: 'include' })
  .then(r => { if (r.ok) window.location.href = '/dashboard'; })
  .catch(() => {});

function showPanel(type) {
  document.getElementById('authPanel').classList.add('open');
  document.getElementById('authOverlay').classList.remove('hidden');
  switchTo(type);
}
function hidePanel() {
  document.getElementById('authPanel').classList.remove('open');
  document.getElementById('authOverlay').classList.add('hidden');
}
function switchTo(type) {
  document.getElementById('loginForm').classList.toggle('hidden', type !== 'login');
  document.getElementById('registerForm').classList.toggle('hidden', type !== 'register');
}

async function doLogin() {
  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  const errEl = document.getElementById('loginError');
  errEl.classList.add('hidden');
  if (!email || !password) { showErr(errEl, 'Please fill in all fields'); return; }
  try {
    const r = await fetch('/api/auth/login', {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await r.json();
    if (!r.ok) { showErr(errEl, data.error || 'Login failed'); return; }
    window.location.href = '/dashboard';
  } catch { showErr(errEl, 'Network error. Please try again.'); }
}

async function doRegister() {
  const name = document.getElementById('regName').value.trim();
  const email = document.getElementById('regEmail').value.trim();
  const password = document.getElementById('regPassword').value;
  const errEl = document.getElementById('registerError');
  errEl.classList.add('hidden');
  if (!name || !email || !password) { showErr(errEl, 'Please fill in all fields'); return; }
  try {
    const r = await fetch('/api/auth/register', {
      method: 'POST', credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password })
    });
    const data = await r.json();
    if (!r.ok) { showErr(errEl, data.error || 'Registration failed'); return; }
    window.location.href = '/dashboard';
  } catch { showErr(errEl, 'Network error. Please try again.'); }
}

function showErr(el, msg) {
  el.textContent = msg; el.classList.remove('hidden');
}

// Enter key support
document.addEventListener('keydown', e => {
  if (e.key !== 'Enter') return;
  const lf = document.getElementById('loginForm');
  const rf = document.getElementById('registerForm');
  if (!lf.classList.contains('hidden')) doLogin();
  else if (!rf.classList.contains('hidden')) doRegister();
});