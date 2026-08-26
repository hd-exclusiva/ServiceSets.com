const products = [
  { id: 'recreatie-start', name: 'Recreatie Startpakket', cat: 'Recreatie', price: 6.95, avail: 'stock', ribbon: 'stock', ribbonLabel: 'Op voorraad', c1: '#3F8F86', c2: '#1A171B' },
  { id: 'hotel-wellness-duo', name: 'Hotel Wellness Duo', cat: 'Hotel & Wellness', price: 4.50, avail: 'order', ribbon: 'order', ribbonLabel: 'Bestel-item', c1: '#1A171B', c2: '#66C0B5' },
  { id: 'koffie-compleet', name: 'Koffie Compleet', cat: 'Koffie', price: 3.25, avail: 'stock', ribbon: 'stock', ribbonLabel: 'Op voorraad', c1: '#66C0B5', c2: '#1A171B' },
  { id: 'bad-douche-basis', name: 'Bad & Douche Basis', cat: 'Bad & Douche', price: 5.10, avail: 'stock', ribbon: 'sale', ribbonLabel: 'Uitverkoop', c1: '#4A4A4C', c2: '#66C0B5' },
  { id: 'schoonmaak-compact', name: 'Schoonmaakset Compact', cat: 'Schoonmaak', price: 7.80, avail: 'stock', ribbon: 'stock', ribbonLabel: 'Op voorraad', c1: '#1A171B', c2: '#EAF7F5' },
  { id: 'recreatie-xl', name: 'Recreatie XL', cat: 'Recreatie', price: 9.40, avail: 'order', ribbon: 'order', ribbonLabel: 'Bestel-item', c1: '#3F8F86', c2: '#66C0B5' },
];

const shopState = { term: '', sort: 'aanbevolen' };

function renderProducts(list) {
  const grid = document.getElementById('productGrid');
  grid.innerHTML = '';
  if (!list.length) {
    grid.innerHTML = '<div class="empty-state">Geen service-sets gevonden die aan uw filters voldoen. Pas uw filters aan of <a href="#" onclick="resetShopFilters(event)">bekijk het volledige assortiment</a>.</div>';
    return;
  }
  list.forEach(p => {
    const el = document.createElement('div');
    el.className = 'product-card';
    el.dataset.id = p.id;
    el.dataset.name = p.name;
    el.dataset.cat = p.cat;
    el.innerHTML = `
      <div class="product-media">
        <span class="ribbon ${p.ribbon}">${p.ribbonLabel}</span>
        <svg viewBox="0 0 300 300" width="100%" height="100%" preserveAspectRatio="xMidYMid slice">
          <rect width="300" height="300" fill="${p.c1}"/>
          <rect x="70" y="70" width="160" height="160" rx="18" fill="${p.c2}" opacity=".55"/>
        </svg>
      </div>
      <div class="product-info">
        <span class="cat">${p.cat}</span>
        <h3>${p.name}</h3>
        <div class="price">${CartStore.formatPrice(p.price)} <button class="mini-add" type="button" data-id="${p.id}" aria-label="${p.name} toevoegen aan winkelmand">+</button></div>
      </div>`;
    grid.appendChild(el);
  });
}

function getCheckedValues(blockLabel) {
  const blocks = document.querySelectorAll('.filter-block');
  let target = null;
  blocks.forEach(b => { if (b.querySelector('h4') && b.querySelector('h4').textContent.trim() === blockLabel) target = b; });
  if (!target) return [];
  return Array.from(target.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.parentElement.textContent.trim());
}

function applyShopFilters() {
  const term = shopState.term.toLowerCase();
  const categories = getCheckedValues('Categorie');
  const availabilityLabels = getCheckedValues('Beschikbaarheid');
  const availMap = { 'Op voorraad': 'stock', 'Bestel-item': 'order' };
  const availValues = availabilityLabels.map(l => availMap[l]).filter(Boolean);

  let list = products.filter(p => {
    const matchesTerm = !term || p.name.toLowerCase().includes(term) || p.cat.toLowerCase().includes(term);
    const matchesCat = categories.length === 0 || categories.includes(p.cat);
    const matchesAvail = availValues.length === 0 || availValues.includes(p.avail);
    return matchesTerm && matchesCat && matchesAvail;
  });

  if (shopState.sort === 'prijs-laag') list = list.slice().sort((a, b) => a.price - b.price);
  else if (shopState.sort === 'prijs-hoog') list = list.slice().sort((a, b) => b.price - a.price);
  else if (shopState.sort === 'naam') list = list.slice().sort((a, b) => a.name.localeCompare(b.name));

  renderProducts(list);

  const countEl = document.getElementById('resultCount');
  countEl.textContent = term
    ? `${list.length} service-set${list.length === 1 ? '' : 's'} gevonden voor "${shopState.term}"`
    : `${list.length} service-set${list.length === 1 ? '' : 's'} gevonden`;
}

function performSearch(e) {
  e.preventDefault();
  shopState.term = document.getElementById('searchInput').value.trim();
  closeSearch();
  showPage('shop');
  applyShopFilters();
  return false;
}

function resetShopFilters(e) {
  if (e) e.preventDefault();
  document.querySelectorAll('.filter-block input[type="checkbox"]').forEach(cb => { cb.checked = false; });
  shopState.term = '';
  const searchInput = document.getElementById('searchInput');
  if (searchInput) searchInput.value = '';
  applyShopFilters();
}

document.addEventListener('DOMContentLoaded', () => {
  applyShopFilters();

  document.querySelectorAll('.filter-block input[type="checkbox"]').forEach(cb => {
    cb.addEventListener('change', applyShopFilters);
  });

  const sortSelect = document.querySelector('.sort-select');
  if (sortSelect) {
    const sortMap = { 0: 'aanbevolen', 1: 'prijs-laag', 2: 'prijs-hoog', 3: 'naam' };
    sortSelect.addEventListener('change', () => {
      shopState.sort = sortMap[sortSelect.selectedIndex] || 'aanbevolen';
      applyShopFilters();
    });
  }

  document.getElementById('productGrid').addEventListener('click', (e) => {
    const btn = e.target.closest('.mini-add');
    if (!btn) return;
    const product = products.find(p => p.id === btn.dataset.id);
    if (!product) return;
    CartStore.addItem(product, 1);
    showCartToast(`${product.name} toegevoegd aan winkelmand`);
    btn.classList.add('added');
    setTimeout(() => btn.classList.remove('added'), 700);
  });
});
