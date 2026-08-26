const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

// ---------- scroll reveal ----------
const revealObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('in-view');
      revealObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.15 });

document.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));

// ---------- count-up stats ----------
function animateCountUp(el) {
  const target = parseInt(el.dataset.target, 10);
  const suffix = el.dataset.suffix || '';
  const duration = 1200;
  const start = performance.now();

  function tick(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(target * eased) + suffix;
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

const countObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      animateCountUp(entry.target);
      countObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.4 });

document.querySelectorAll('.count-up').forEach(el => countObserver.observe(el));

// ---------- category card tilt ----------
if (!prefersReducedMotion.matches) {
  document.querySelectorAll('.tilt').forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      card.style.transform = `translateY(-6px) rotateX(${(-y * 10).toFixed(2)}deg) rotateY(${(x * 10).toFixed(2)}deg)`;
    });
    card.addEventListener('mouseleave', () => {
      card.style.transform = '';
    });
  });
}

// ---------- hero parallax ----------
const heroSection = document.getElementById('heroSection');
const heroVisual = document.getElementById('heroVisual');
if (heroSection && heroVisual && !prefersReducedMotion.matches) {
  heroSection.addEventListener('mousemove', (e) => {
    const rect = heroSection.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    heroVisual.style.transform = `translate(${(x * 14).toFixed(2)}px, ${(y * 14).toFixed(2)}px)`;
  });
  heroSection.addEventListener('mouseleave', () => {
    heroVisual.style.transform = '';
  });
}

// ---------- newsletter micro-interaction ----------
function handleNewsletterSubmit(event) {
  event.preventDefault();
  const form = document.getElementById('nlForm');
  const btn = document.getElementById('nlSubmitBtn');
  const input = form.querySelector('input[type="email"]');
  if (!input.value) return false;
  btn.textContent = 'Aangemeld ✓';
  btn.classList.add('sent');
  form.classList.add('sent');
  input.disabled = true;
  setTimeout(() => {
    btn.textContent = 'Aanmelden';
    btn.classList.remove('sent');
    form.classList.remove('sent');
    input.disabled = false;
    input.value = '';
  }, 3000);
  return false;
}
