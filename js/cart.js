// Shared cart state (prototype). Persisted in localStorage so it survives
// reloads and carries across pages, but this is still purely client-side —
// a real webshop would sync this to a server-side cart tied to the session.
const CART_STORAGE_KEY = 'ss_cart_v1';

const CartStore = (() => {
  function read() {
    try {
      const raw = localStorage.getItem(CART_STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function write(items) {
    try {
      localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(items));
    } catch (e) {
      // storage unavailable (private mode etc.) — cart just won't persist
    }
    renderBadges();
  }

  function getItems() {
    return read();
  }

  function addItem(product, qty) {
    qty = qty || 1;
    const items = read();
    const existing = items.find(i => i.id === product.id);
    if (existing) {
      existing.qty += qty;
    } else {
      items.push({
        id: product.id,
        name: product.name,
        cat: product.cat,
        price: typeof product.price === 'number' ? product.price : null,
        quote: product.price == null,
        qty
      });
    }
    write(items);
  }

  function setQty(id, qty) {
    let items = read();
    if (qty <= 0) {
      items = items.filter(i => i.id !== id);
    } else {
      const item = items.find(i => i.id === id);
      if (item) item.qty = qty;
    }
    write(items);
  }

  function removeItem(id) {
    const items = read().filter(i => i.id !== id);
    write(items);
  }

  function clear() {
    write([]);
  }

  function totalCount() {
    return read().reduce((sum, i) => sum + i.qty, 0);
  }

  function totalPrice() {
    return read().reduce((sum, i) => sum + (typeof i.price === 'number' ? i.qty * i.price : 0), 0);
  }

  function hasQuoteItems() {
    return read().some(i => i.quote);
  }

  function formatPrice(value) {
    if (typeof value !== 'number') return 'Prijs op aanvraag';
    return '€ ' + value.toLocaleString('nl-NL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function renderBadges() {
    const count = totalCount();
    document.querySelectorAll('.cart-badge').forEach(el => {
      el.textContent = String(count);
      el.hidden = count === 0;
    });
  }

  return { getItems, addItem, setQty, removeItem, clear, totalCount, totalPrice, hasQuoteItems, formatPrice, renderBadges };
})();
// `const` bindings don't attach to `window`, but other scripts (e.g. configurator.js)
// look this up via `window.CartStore` — assign it explicitly so that works.
window.CartStore = CartStore;

// ---------- add-to-cart toast ----------
let toastTimer = null;
function showCartToast(message) {
  let toast = document.getElementById('cartToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'cartToast';
    toast.className = 'cart-toast';
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
}

document.addEventListener('DOMContentLoaded', () => {
  CartStore.renderBadges();
});
