(function () {
  const root = document.getElementById('cpqJourney');
  if (!root) return;

  const state = {
    step: 'start', quantity: 0, branch: null, mode: null, sets: [], current: {}, cartMode: 'loose', multiSet: null
  };
  let catalog = [
    { name: 'Badkamer essentials', category: 'Bad & douche', detail: 'Handdoek, zeepje en shampoo' },
    { name: 'Koffie welkom', category: 'Koffie & thee', detail: 'Koffie, melk en suiker' },
    { name: 'Schoonmaak compact', category: 'Schoonmaak', detail: 'Afwasmiddel en vaatwastablet' },
    { name: 'Recreatie basis', category: 'Recreatie', detail: 'Alles voor een zorgeloos verblijf' },
    { name: 'Huisdieren welkom', category: 'Huisdieren', detail: 'Verzorgd welkom voor elke gast' },
    { name: 'Kantoor & ontvangst', category: 'Kantoor & papier', detail: 'Notitieblok en praktische extra\'s' }
  ];
  const hydrateCatalog = () => fetch('../data/products.json')
    .then((response) => response.ok ? response.json() : [])
    .then((items) => {
      if (!Array.isArray(items) || !items.length) return;
      catalog = items.map((item) => ({
        name: item.name,
        category: item.category || 'Overig',
        detail: [item.num, item.weight_g ? `${item.weight_g} g` : ''].filter(Boolean).join(' · ')
      }));
    })
    .catch(() => {});
  const recommendedAdditions = [
    { name: 'Koffie cup Lungo', detail: 'Een gastvrij extraatje bij elk verblijf', category: 'Koffie & thee' },
    { name: 'Hondenpoepzakje', detail: 'Praktisch voor accommodaties waar honden welkom zijn', category: 'Huisdieren' },
    { name: 'Afvalzak HDPE', detail: 'Handige aanvulling voor keuken en sanitair', category: 'Afval & afvalzakken' },
    { name: 'Stick limonade', detail: 'Een kleine dorstlesser voor onderweg', category: 'Dranken' }
  ];

  const branchFor = (quantity) => quantity < 500 ? 'A' : quantity <= 1000 ? 'B' : 'C';
  const branchLabel = { A: 'Kleine oplage', B: 'Maatwerk oplage', C: 'Grote oplage' };
  const button = (label, action, variant = '') => `<button class="journey-btn ${variant}" data-action="${action}">${label}</button>`;
  const back = () => button('Terug', 'back', 'journey-btn-quiet');
  const next = (label = 'Verder') => button(`${label} <span aria-hidden="true">→</span>`, 'next');
  const normalizeProductSelection = (products) => {
    const selected = Array.isArray(products) ? [...new Set(products.map((item) => Number(item)).filter((item) => Number.isInteger(item) && item >= 0))] : [];
    return selected.slice(0, 1);
  };
  const productSummary = (products) => {
    const selected = normalizeProductSelection(products);
    if (!selected.length) return 'Geen inhoud gekozen';
    const names = selected.map((index) => catalog[index]?.name).filter(Boolean);
    return names.length ? names.join(', ') : 'Geen inhoud gekozen';
  };

  function render() {
    const views = { start: renderStart, quantity: renderQuantity, choose: renderChoose, products: renderProducts, extras: renderExtras, review: renderReview, cart: renderCart, checkout: renderCheckout };
    root.innerHTML = `<section class="journey-hero"><div class="journey-hero-copy"><span class="eyebrow">ServiceSETS op maat</span><h1>Een set die precies past bij jouw gast.</h1><p>Stel in een paar stappen een eigen service-set samen. De hoeveelheid bepaalt de route die bij je past.</p></div><div class="journey-hero-art"><span class="art-label">Jouw idee</span><strong>${state.quantity ? `${state.quantity.toLocaleString('nl-NL')} sets` : 'jouw set'}</strong><i></i><i></i><i></i></div></section><div class="journey-wrap">${progress()}<div class="journey-layout"><main class="journey-main">${views[state.step]()}</main>${summary()}</div></div>`;
    root.querySelectorAll('[data-action]').forEach((el) => el.addEventListener('click', () => handle(el.dataset.action)));
    root.querySelectorAll('input, select, textarea').forEach((el) => {
      el.addEventListener('change', updateField);
      if (el.id === 'quantity') el.addEventListener('input', () => { state.quantity = Math.max(0, Number(el.value) || 0); });
    });
  }

  function progress() {
    const labels = ['Start', 'Aantal', 'Samenstellen', 'Afronden', 'Winkelmand'];
    const active = ['start', 'quantity', 'choose', 'products', 'extras', 'review', 'cart', 'checkout'].indexOf(state.step);
    return `<div class="journey-progress">${labels.map((label, index) => `<span class="${index <= Math.min(active, 4) ? 'is-done' : ''}"><b>${index + 1}</b>${label}</span>`).join('')}</div>`;
  }

  function renderStart() { const selected = state.multiSet === null ? '' : state.multiSet ? 'multi' : 'single'; return `<div class="journey-kicker">Start je aanvraag</div><h2>Hoeveel verschillende sets wil je samenstellen?</h2><p class="lead">Begin met één set, of geef meteen aan dat je meerdere samenstellingen nodig hebt. Je kunt later altijd nog een extra set toevoegen.</p><div class="choice-grid"><button class="journey-choice ${selected === 'single' ? 'selected' : ''}" data-action="set-count-single" aria-pressed="${selected === 'single'}"><span class="choice-icon">1</span><span><strong>Eén set</strong><small>Een enkele samenstelling voor jouw project.</small></span><span class="choice-check" aria-hidden="true">${selected === 'single' ? '✓' : ''}</span></button><button class="journey-choice ${selected === 'multi' ? 'selected' : ''}" data-action="set-count-multi" aria-pressed="${selected === 'multi'}"><span class="choice-icon">+</span><span><strong>Meerdere sets</strong><small>Verschillende samenstellingen binnen één aanvraag.</small></span><span class="choice-check" aria-hidden="true">${selected === 'multi' ? '✓' : ''}</span></button></div><div class="journey-actions"><span></span>${next('Start met aantallen')}</div>`; }
  function renderQuantity() { const multipleIntro = state.multiSet ? 'Dit is de oplage voor je eerste set. Na afronding kun je direct een volgende samenstelling toevoegen.' : 'Zo tonen we meteen de route die past bij jouw project.'; return `<div class="journey-kicker">Stap 1 van 4</div><h2>${state.multiSet ? 'Hoeveel sets heeft je eerste samenstelling nodig?' : 'Hoeveel sets heb je nodig?'}</h2><p class="lead">${multipleIntro}</p><div class="quantity-entry"><label for="quantity">Aantal sets</label><input id="quantity" type="number" min="1" value="${state.quantity || ''}" placeholder="bijv. 750" autofocus><span>sets</span></div><div class="range-notes"><span><b>&lt; 500</b> klein en snel</span><span><b>500–1000</b> extra maatwerk</span><span><b>1000+</b> persoonlijk traject</span></div><div class="journey-actions">${back()}${next()}</div>`; }
  function renderChoose() { const branch = branchFor(state.quantity); const selected = state.mode || ''; return `<div class="journey-kicker">Case ${branch} · ${branchLabel[branch]}</div><h2>${branch === 'A' ? 'Kies een startpunt voor je set.' : branch === 'B' ? 'Hoe wil je jouw samenstelling opbouwen?' : 'Van referentie naar volledig eigen concept.'}</h2><p class="lead">${branch === 'C' ? 'Gebruik een populaire samenstelling als vertrekpunt, of laat ons samen met jou iets nieuws ontwikkelen.' : 'Je kunt altijd later nog inhoud, aantallen en uitstraling aanpassen.'}</p><div class="choice-grid">${presetChoice(branch === 'A' ? 'Populairste standaardset' : 'Populaire samenstelling', 'Een bewezen combinatie als handig vertrekpunt.', 'popular', '★', selected)}${presetChoice('Zelf samenstellen', 'Kies zelf categorieën en producten.', 'custom', '＋', selected)}</div><div class="journey-actions">${back()}${next()}</div>`; }
  function choice(title, detail, action, icon) { return `<button class="journey-choice" data-action="${action}"><span class="choice-icon">${icon}</span><span><strong>${title}</strong><small>${detail}</small></span><b aria-hidden="true">→</b></button>`; }
  function presetChoice(title, detail, action, icon, selected) { return `<button class="journey-choice ${selected === action ? 'selected' : ''}" data-action="select-${action}" aria-pressed="${selected === action}"><span class="choice-icon">${icon}</span><span><strong>${title}</strong><small>${detail}</small></span><span class="choice-check" aria-hidden="true">${selected === action ? '✓' : ''}</span></button>`; }
  function renderProducts() {
    const selected = normalizeProductSelection(state.current.products || []);
    const ownSelected = state.current.ownArticles || [];
    const branch = branchFor(state.quantity);
    const activeCategory = state.current.category || 'Alle categorieën';
    const categories = ['Alle categorieën', ...new Set(catalog.map((item) => item.category))];
    const groupedProducts = categories.filter((category) => category !== 'Alle categorieën').reduce((acc, category) => {
      acc[category] = catalog.filter((item) => item.category === category);
      return acc;
    }, {});
    const visibleCategories = activeCategory === 'Alle categorieën' ? Object.keys(groupedProducts) : [activeCategory];

    return `<div class="journey-kicker">Stap 2 · Inhoud</div><h2>${branch === 'C' ? 'Kies assortiment of eigen artikelen.' : 'Kies wat er in jouw set komt.'}</h2><p class="lead">${branch === 'C' ? 'Kies eerst een productcategorie en voeg daarna artikelen toe aan je set.' : 'Kies een categorie en selecteer één product dat je gast nodig heeft.'}</p><div class="category-grid">${categories.map((category) => `<button class="category-choice ${activeCategory === category ? 'selected' : ''}" data-action="category-${category}">${category}<span>${category === 'Alle categorieën' ? catalog.length : (groupedProducts[category] || []).length}</span></button>`).join('')}</div><div class="catalog-groups">${visibleCategories.map((category) => `<div class="catalog-group"><h3>${category}</h3><div class="catalog-grid">${(groupedProducts[category] || []).map((item) => { const index = catalog.indexOf(item); return `<label class="catalog-item ${selected.includes(index) ? 'selected' : ''}"><input type="radio" name="catalog-item" value="${index}" ${selected.includes(index) ? 'checked' : ''}><span class="catalog-mark">0${index + 1}</span><span><strong>${item.name}</strong><small>${item.category} · ${item.detail}</small></span><span class="product-check" aria-hidden="true">${selected.includes(index) ? '✓' : '+'}</span></label>`; }).join('')}</div></div>`).join('')}</div>${branch === 'C' ? `<div class="recommended-additions"><div class="recommended-heading"><strong>Aanbevolen toevoegingen</strong><small>Voeg artikelen met één klik toe aan je set.</small></div><div class="recommended-grid">${recommendedAdditions.map((item, index) => `<button class="recommended-item ${ownSelected.includes(index) ? 'selected' : ''}" data-action="own-${index}"><span class="recommended-plus">${ownSelected.includes(index) ? '✓' : '+'}</span><span><strong>${item.name}</strong><small>${item.category} · ${item.detail}</small></span></button>`).join('')}</div></div>` : ''}<div class="journey-actions">${back()}${next()}</div>`;
  }
  function renderExtras() { const branch = branchFor(state.quantity); return `<div class="journey-kicker">Stap 3 · Afwerking</div><h2>Maak de uitstraling eigen.</h2><p class="lead">${branch === 'A' ? 'Kies een standaard sticker en bekijk passende extra\'s.' : branch === 'B' ? 'Pas de inhoud aan en lever straks je eigen stickerontwerp aan.' : 'Kies verpakking en geef aan waarbij ons team kan ondersteunen.'}</p><div class="form-stack">${branch === 'C' ? `<label>Verpakking<select id="packaging"><option>Individuele sets</option><option>Een gezamenlijke omdoos</option><option>Advies van ServiceSETS</option></select></label><label class="toggle-row"><input id="support" type="checkbox"> <span>Ik wil gratis ondersteuning bij mijn aanvraag</span></label><label>Doosontwerp<select id="boxDesign"><option>Geen ontwerp nodig</option><option>Ik wil een ontwerp laten maken</option></select></label><label>Stickerontwerp<select id="stickerDesign"><option>Geen stickerontwerp nodig</option><option>Ik wil een ontwerp laten maken</option></select></label>` : `<label>Sticker<select id="sticker"><option>Standaard sticker · ServiceSETS</option><option>Eigen logo op standaard formaat</option><option>Ik lever een ontwerp aan</option></select></label><label class="toggle-row"><input id="upsell" type="checkbox"> <span>Toon passende extra producten</span></label>`}</div><div class="journey-note"><b>${branch === 'C' ? 'Persoonlijk traject' : 'Bijna klaar'}</b><span>${branch === 'C' ? 'Bij gratis ondersteuning neemt een specialist contact met je op.' : 'Je kunt de set na toevoegen gewoon nog wijzigen.'}</span></div><div class="journey-actions">${back()}${next('Bekijk je set')}</div>`; }
  function renderReview() { const products = normalizeProductSelection(state.current.products || []).map((index) => catalog[index].name); const additions = (state.current.ownArticles || []).map((index) => recommendedAdditions[index].name); return `<div class="journey-kicker">Stap 4 · Controle</div><h2>Dit is jouw set.</h2><p class="lead">Controleer de keuzes voordat je de set toevoegt aan je winkelmand.</p><div class="review-sheet"><div><span>Oplage</span><strong>${state.quantity.toLocaleString('nl-NL')} sets</strong></div><div><span>Route</span><strong>Case ${state.branch}</strong></div><div><span>Inhoud</span><strong>${products.length ? products.join(', ') : 'Geen inhoud gekozen'}</strong></div>${additions.length ? `<div><span>Aanbevolen</span><strong>${additions.join(', ')}</strong></div>` : ''}<div><span>Afwerking</span><strong>${state.current.sticker || state.current.packaging || 'Standaard uitvoering'}</strong></div></div><div class="journey-actions">${back()}${button('Set toevoegen', 'add-set', 'journey-btn-primary')}</div>`; }
  function summary() { const count = state.sets.length; const setLines = state.sets.length ? state.sets.map((set, index) => { const selectedProduct = normalizeProductSelection(set.products || []); const productName = selectedProduct.length ? catalog[selectedProduct[0]]?.name || 'Eigen artikel' : 'Geen artikel gekozen'; return `<div class="summary-line"><span>Set ${index + 1}</span><strong>${set.quantity.toLocaleString('nl-NL')} · ${productName}</strong></div>`; }).join('') : state.quantity ? `<div class="summary-line"><span>Oplage</span><strong>${state.quantity.toLocaleString('nl-NL')}</strong></div>` : '<p>Je keuzes verschijnen hier terwijl je samenstelt.</p>'; return `<aside class="journey-summary"><div class="summary-top"><span>Jouw aanvraag</span><b>${count} ${count === 1 ? 'set' : 'sets'}</b></div>${setLines}<div class="summary-rule"></div><span class="summary-foot">Nog geen prijsberekening</span></aside>`; }
  function renderCart() { return `<div class="journey-kicker">Winkelmand</div><h2>Je aanvraag staat klaar.</h2><p class="lead">${state.sets.length} ${state.sets.length === 1 ? 'set is' : 'sets zijn'} toegevoegd. Kies hoe we ze voor je verpakken.</p><div class="cart-list">${state.sets.map((set, index) => { const setProducts = normalizeProductSelection(set.products || []); const productText = setProducts.length ? ` · ${catalog[setProducts[0]]?.name || 'Inhoud'}` : ''; return `<div class="cart-item"><span class="cart-number">0${index + 1}</span><div><strong>Eigen service-set</strong><small>${set.quantity.toLocaleString('nl-NL')} sets · Case ${set.branch}${productText}</small></div><button aria-label="Set verwijderen" data-action="remove-${index}">×</button></div>`; }).join('')}</div><div class="pack-choice"><label class="pack-option ${state.cartMode === 'loose' ? 'selected' : ''}"><input type="radio" name="cartMode" value="loose" ${state.cartMode === 'loose' ? 'checked' : ''}> <strong>Losse sets</strong><small>Elke set apart verpakt</small></label><label class="pack-option ${state.cartMode === 'combined' ? 'selected' : ''}"><input type="radio" name="cartMode" value="combined" ${state.cartMode === 'combined' ? 'checked' : ''}> <strong>Eén gezamenlijke omdoos</strong><small>Jou sets per combinatie in een omdoos</small></label></div><div class="journey-actions">${button('Nog een set samenstellen', 'new-set', 'journey-btn-quiet')}${button('Naar aanvraag', 'checkout', 'journey-btn-primary')}</div>`; }
  function renderCheckout() { return `<div class="success-mark">✓</div><div class="journey-kicker">Aanvraag ontvangen</div><h2>We gaan ermee aan de slag.</h2><p class="lead">Bedankt. We hebben je configuratie klaargezet voor controle. In een echte shop volgt nu de checkout en bevestigingsmail.</p><div class="journey-note"><b>Volgende stap</b><span>Een bevestiging en eventuele ontwerpvraag komen per e-mail. Bij een niet-afgeronde checkout sturen we een herinnering.</span></div>${button('Terug naar winkelmand', 'cart', 'journey-btn-quiet')}`; }

  function updateField(event) { const el = event.target; if (el.id === 'quantity') { state.quantity = Math.max(0, Number(el.value) || 0); return; } if (el.name === 'cartMode') state.cartMode = el.value; if (el.closest('.catalog-item') && (el.type === 'radio' || el.type === 'checkbox')) { const index = Number(el.value); const nextSelection = el.checked ? [index] : []; state.current.products = nextSelection; render(); return; } if (el.id === 'sticker' || el.id === 'packaging' || el.id === 'boxDesign' || el.id === 'stickerDesign') state.current[el.id] = el.value; if (el.id === 'upsell' || el.id === 'support') state.current[el.id] = el.checked; render(); }
  function handle(action) {
    if (action === 'quantity') state.step = 'quantity';
    else if (action === 'set-count-single' || action === 'set-count-multi') { state.multiSet = action === 'set-count-multi'; state.step = 'quantity'; }
    else if (action === 'select-popular' || action === 'select-custom') { state.mode = action.replace('select-', ''); }
    else if (action === 'popular' || action === 'custom') { state.mode = action; state.branch = branchFor(state.quantity); state.current = { products: action === 'popular' ? [0] : [] }; state.step = 'products'; }
    else if (action.startsWith('own-')) { const index = Number(action.split('-')[1]); const selected = state.current.ownArticles || []; state.current.ownArticles = selected.includes(index) ? selected.filter((item) => item !== index) : [...selected, index]; }
    else if (action.startsWith('category-')) { state.current.category = action.replace('category-', ''); }
    else if (action === 'next') { if (state.step === 'start') { if (state.multiSet === null) return; state.step = 'quantity'; } else if (state.step === 'quantity') { if (!state.quantity) return; state.branch = branchFor(state.quantity); state.step = 'choose'; } else if (state.step === 'choose') { if (!state.mode) return; state.branch = branchFor(state.quantity); state.current = { products: state.mode === 'popular' ? [0] : [] }; state.step = 'products'; } else if (state.step === 'products') { state.current.products = normalizeProductSelection([...root.querySelectorAll('.catalog-item input:checked')].map((input) => Number(input.value))); state.step = 'extras'; } else if (state.step === 'extras') state.step = 'review'; }
    else if (action === 'back') { const previous = { quantity: 'start', choose: 'quantity', products: 'choose', extras: 'products', review: 'extras' }; state.step = previous[state.step] || 'start'; }
    else if (action === 'add-set') { state.sets.push({ ...state.current, quantity: state.quantity, branch: state.branch }); state.step = 'cart'; }
    else if (action === 'new-set') { state.current = {}; state.mode = null; state.step = 'quantity'; }
    else if (action === 'checkout') state.step = 'checkout';
    else if (action === 'cart') state.step = 'cart';
    else if (action.startsWith('remove-')) state.sets.splice(Number(action.split('-')[1]), 1);
    else return;
    render();
  }
  hydrateCatalog().then(() => render());
  render();
})();
