function showCartView(id) {
  document.querySelectorAll('.account-view').forEach(v => v.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  window.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' });
}

function renderCartItems() {
  const container = document.getElementById('cartItems');
  const items = CartStore.getItems();
  const checkoutBtn = document.getElementById('checkoutBtn');

  if (!items.length) {
    container.innerHTML = `
      <div class="empty-state">
        Uw winkelmand is leeg.<br>
        <a href="../index.html#shop" class="link-arrow" style="justify-content:center; margin-top:10px;">Bekijk het assortiment</a>
      </div>`;
    checkoutBtn.disabled = true;
  } else {
    checkoutBtn.disabled = false;
    container.innerHTML = items.map(item => {
      const isQuote = !!item.quote;
      const qtyCell = isQuote
        ? `<div class="qty-stepper qty-fixed">${item.qty}×</div>`
        : `<div class="qty-stepper">
            <button type="button" aria-label="Aantal verlagen" data-action="dec">−</button>
            <span aria-live="polite">${item.qty}</span>
            <button type="button" aria-label="Aantal verhogen" data-action="inc">+</button>
          </div>`;
      return `
      <div class="cart-row ${isQuote ? 'cart-row-quote' : ''}" data-id="${item.id}">
        <div class="cart-row-info">
          <strong>${item.name}</strong>
          <span>${item.cat}</span>
        </div>
        ${qtyCell}
        <div class="cart-row-price">${isQuote ? 'Op aanvraag' : CartStore.formatPrice(item.price)}</div>
        <div class="cart-row-total">${isQuote ? 'Prijs op aanvraag' : CartStore.formatPrice(item.price * item.qty)}</div>
        <button type="button" class="cart-row-remove" aria-label="${item.name} verwijderen" data-action="remove">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0-1 14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2L4 6h16Z"/></svg>
        </button>
      </div>`;
    }).join('');
  }

  document.getElementById('cartSubtotal').textContent = CartStore.formatPrice(CartStore.totalPrice());
  document.getElementById('cartTotal').textContent = CartStore.formatPrice(CartStore.totalPrice());

  const noteEl = document.getElementById('cartQuoteNote');
  if (noteEl) noteEl.hidden = !CartStore.hasQuoteItems();
}

function renderCheckoutSummary() {
  const items = CartStore.getItems();
  const list = document.getElementById('checkoutSummaryList');
  list.innerHTML = items.map(item => `
    <div class="contact-info-row">
      <div>
        <strong>${item.qty}× ${item.name}</strong>
        <span>${item.quote ? 'Prijs op aanvraag' : CartStore.formatPrice(item.price * item.qty)}</span>
      </div>
    </div>`).join('');
  document.getElementById('checkoutTotal').textContent = CartStore.formatPrice(CartStore.totalPrice());
  const noteEl = document.getElementById('checkoutQuoteNote');
  if (noteEl) noteEl.hidden = !CartStore.hasQuoteItems();
}

function goToCheckout() {
  if (!CartStore.getItems().length) return;
  renderCheckoutSummary();
  showCartView('view-checkout');
}

function handlePlaceOrder(event) {
  event.preventDefault();
  const orderNumber = '#SS-' + Math.floor(20000 + Math.random() * 9999);
  document.getElementById('confirmationOrderNumber').textContent = orderNumber;
  CartStore.clear();
  showCartView('view-confirmation');
  return false;
}

document.getElementById('cartItems').addEventListener('click', (e) => {
  const btn = e.target.closest('button[data-action]');
  if (!btn) return;
  const row = btn.closest('.cart-row');
  const id = row.dataset.id;
  const items = CartStore.getItems();
  const item = items.find(i => i.id === id);
  if (!item) return;

  if (btn.dataset.action === 'inc') CartStore.setQty(id, item.qty + 1);
  else if (btn.dataset.action === 'dec') CartStore.setQty(id, item.qty - 1);
  else if (btn.dataset.action === 'remove') CartStore.removeItem(id);

  renderCartItems();
});

document.addEventListener('DOMContentLoaded', renderCartItems);
