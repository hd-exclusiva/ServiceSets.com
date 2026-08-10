
    function performSearch(e){
    e.preventDefault();
    const term = document.getElementById('searchInput').value.trim();
    closeSearch();
    filterProductGrid(term);
    showPage('shop');
    return false;
  }
  function filterProductGrid(term){
    const cards = document.querySelectorAll('#productGrid .product-card');
    let visibleCount = 0;
    cards.forEach(card=>{
      const name = card.dataset.name.toLowerCase();
      const cat = card.dataset.cat.toLowerCase();
      const match = !term || name.includes(term.toLowerCase()) || cat.includes(term.toLowerCase());
      card.style.display = match ? '' : 'none';
      if(match) visibleCount++;
    });
    const countEl = document.getElementById('resultCount');
    countEl.textContent = term
      ? `${visibleCount} service-set${visibleCount===1?'':'s'} gevonden voor "${term}"`
      : `${cards.length} service-sets gevonden`;
  }

   const products = [
    {name:'Recreatie Startpakket', cat:'Recreatie', price:'€ 6,95', ribbon:'stock', ribbonLabel:'Op voorraad', c1:'#3F8F86', c2:'#1A171B'},
    {name:'Hotel Wellness Duo', cat:'Hotel & Wellness', price:'€ 4,50', ribbon:'order', ribbonLabel:'Bestel-item', c1:'#1A171B', c2:'#66C0B5'},
    {name:'Koffie Compleet', cat:'Koffie', price:'€ 3,25', ribbon:'stock', ribbonLabel:'Op voorraad', c1:'#66C0B5', c2:'#1A171B'},
    {name:'Bad & Douche Basis', cat:'Bad & Douche', price:'€ 5,10', ribbon:'sale', ribbonLabel:'Uitverkoop', c1:'#4A4A4C', c2:'#66C0B5'},
    {name:'Schoonmaakset Compact', cat:'Schoonmaak', price:'€ 7,80', ribbon:'stock', ribbonLabel:'Op voorraad', c1:'#1A171B', c2:'#EAF7F5'},
    {name:'Recreatie XL', cat:'Recreatie', price:'€ 9,40', ribbon:'order', ribbonLabel:'Bestel-item', c1:'#3F8F86', c2:'#66C0B5'},
  ];
  const grid = document.getElementById('productGrid');
  products.forEach(p=>{
    const el = document.createElement('div');
    el.className='product-card';
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
        <div class="price">${p.price} <button class="mini-add" aria-label="Toevoegen">+</button></div>
      </div>`;
    grid.appendChild(el);
  });