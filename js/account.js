// Prototype-only mock auth. No credentials are ever persisted (not even in
// localStorage) — this file only demonstrates the intended front-end flow.
// Real authentication must happen server-side (Odoo portal login) once connected.
const DEMO_EMAIL = 'demo@servicesets.com';
const DEMO_PASSWORD = 'demo1234';

function showAccountView(id) {
  document.querySelectorAll('.account-view').forEach(v => v.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  window.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' });
}

function showLogin(event) {
  if (event) event.preventDefault();
  showAccountView('view-login');
}

function showForgotPassword(event) {
  if (event) event.preventDefault();
  showAccountView('view-forgot');
}

function togglePasswordVisibility() {
  const input = document.getElementById('lg-password');
  const btn = document.getElementById('passwordToggle');
  const showing = input.type === 'text';
  input.type = showing ? 'password' : 'text';
  btn.setAttribute('aria-pressed', String(!showing));
  btn.setAttribute('aria-label', showing ? 'Wachtwoord tonen' : 'Wachtwoord verbergen');
}

function setLoginLoading(isLoading) {
  const btn = document.getElementById('loginSubmit');
  const label = document.getElementById('loginSubmitText');
  btn.disabled = isLoading;
  label.textContent = isLoading ? 'Bezig met inloggen…' : 'Inloggen';
}

function handleLogin(event) {
  event.preventDefault();
  const email = document.getElementById('lg-email').value.trim();
  const password = document.getElementById('lg-password').value;
  const errorBox = document.getElementById('authError');

  errorBox.hidden = true;
  setLoginLoading(true);

  // Simulated network round-trip so the loading state is visible.
  setTimeout(() => {
    setLoginLoading(false);
    const ok = email.toLowerCase() === DEMO_EMAIL && password === DEMO_PASSWORD;
    if (ok) {
      document.getElementById('lg-password').value = '';
      showAccountView('view-dashboard');
      showAccountPanel('profiel');
    } else {
      document.getElementById('lg-password').value = '';
      document.getElementById('lg-password').focus();
      errorBox.hidden = false;
    }
  }, 500);

  return false;
}

function handleForgotPassword(event) {
  event.preventDefault();
  document.getElementById('forgotForm').hidden = true;
  document.getElementById('forgotSuccess').hidden = false;
  return false;
}

function handleLogout() {
  document.getElementById('loginForm').reset();
  document.getElementById('authError').hidden = true;
  showAccountView('view-login');
}

function showAccountPanel(name) {
  document.querySelectorAll('.account-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  document.querySelectorAll('.account-nav-item[data-panel]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.panel === name);
  });
}
