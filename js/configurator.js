/* ==========================================================================
   Servicesets CPQ Configurator — logica
   Verwacht in de HTML: elementen met de id's zoals hieronder gebruikt,
   binnen een wrapper met class "ssets-cpq-configurator".
   Rekenkern draait als échte Python via Pyodide (packer_core.py).
   ========================================================================== */

(function(){
  // ---------- STATE ----------
  let products = [];
  let composition = {};
  let boxes = [
    {id:'box1', name:'Doos S', l:15, w:12, h:12},
    {id:'box2', name:'Doos M', l:20, w:15, h:15},
    {id:'box3', name:'Doos L', l:30, w:25, h:20},
    {id:'box4', name:'Doos XL', l:40, w:30, h:25},
  ];
  let uidCounter = 1;
  const nextId = (p) => p + (uidCounter++);
  const fmt = (n) => Number.isInteger(n) ? n : n.toFixed(1);

  // ---------- PYODIDE: laad de ECHTE packer_core.py ----------
  let pyodideInstance = null;
  const pyReady = (async () => {
    const pyodide = await loadPyodide();
    // Gebruik absoluut pad naar de root-map /py/
    const src = await (await fetch('cpq/python/python_packer.py')).text();
    pyodide.runPython(src);
    pyodideInstance = pyodide;
    const statusEl = document.getElementById('sscpq-pyStatus');
    statusEl.textContent = 'Python klaar (packer_core.py geladen)';
    statusEl.className = 'ready';
    const calcBtn = document.getElementById('sscpq-calcBtn');
    calcBtn.disabled = false;
    calcBtn.textContent = 'Bereken passende doos →';
    return pyodide;
  })();

  async function pySelectBox(items, candidateBoxes){
    const pyodide = await pyReady;
    pyodide.globals.set('items_json', JSON.stringify(items));
    pyodide.globals.set('boxes_json', JSON.stringify(candidateBoxes));
    const resultJson = pyodide.runPython(`
import json
_items = json.loads(items_json)
_boxes = json.loads(boxes_json)
_result = select_box(_items, _boxes)
json.dumps(_result)
`);
    return JSON.parse(resultJson);
  }

  // ---------- PRODUCT TABEL ----------
  function renderProductTable(){
    const wrap = document.getElementById('sscpq-productTableWrap');
    if(products.length === 0){ wrap.innerHTML = '<div class="sscpq-empty-hint">Nog geen producten geladen.</div>'; return; }
    let rows = products.map(p => `
      <tr class="sscpq-item-row">
        <td><input type="checkbox" data-id="${p.id}" class="sscpq-prod-check" ${composition[p.id] ? 'checked' : ''}/></td>
        <td>${p.num}</td><td class="sscpq-name-cell">${p.name}</td>
        <td>${fmt(p.l)}</td><td>${fmt(p.w)}</td><td>${fmt(p.h)}</td>
        <td><input type="number" min="0" class="sscpq-prod-qty" data-id="${p.id}" value="${composition[p.id] || 1}" style="width:48px" /></td>
      </tr>`).join('');
    wrap.innerHTML = `
      <div style="max-height:260px; overflow:auto;">
      <table><thead><tr><th></th><th>Art.nr</th><th>Naam</th><th>L</th><th>B</th><th>H</th><th>Aantal</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
      <div class="sscpq-row-actions"><button class="sscpq-btn secondary small" id="sscpq-clearProductsBtn">Wis lijst</button></div>`;
    document.querySelectorAll('.sscpq-prod-check').forEach(cb => cb.addEventListener('change', onCheckChange));
    document.querySelectorAll('.sscpq-prod-qty').forEach(inp => inp.addEventListener('input', onQtyChange));
    document.getElementById('sscpq-clearProductsBtn').addEventListener('click', () => {
      products = []; composition = {}; renderProductTable(); renderComposition();
    });
  }
  function onCheckChange(e){
    const id = e.target.dataset.id;
    if(e.target.checked){ composition[id] = parseInt(document.querySelector(`.sscpq-prod-qty[data-id="${id}"]`).value) || 1; }
    else{ delete composition[id]; }
    renderComposition();
  }
  function onQtyChange(e){
    const id = e.target.dataset.id;
    const val = Math.max(0, parseInt(e.target.value) || 0);
    if(composition[id] !== undefined){
      if(val === 0){ delete composition[id]; document.querySelector(`.sscpq-prod-check[data-id="${id}"]`).checked = false; }
      else composition[id] = val;
    }
    renderComposition();
  }
  function renderComposition(){
    const wrap = document.getElementById('sscpq-compositionWrap');
    const ids = Object.keys(composition);
    document.getElementById('sscpq-compCount').textContent = ids.reduce((s,id)=>s+composition[id],0) + ' items';
    if(ids.length === 0){ wrap.innerHTML = '<div class="sscpq-empty-hint">Vink producten aan in de tabel hierboven en zet het aantal.</div>'; return; }
    let totalVol = 0;
    let rows = ids.map(id => {
      const p = products.find(x=>x.id===id); if(!p) return '';
      totalVol += p.l*p.w*p.h*composition[id];
      return `<tr><td class="sscpq-name-cell">${p.name}</td><td>${fmt(p.l)}×${fmt(p.w)}×${fmt(p.h)}</td><td>${composition[id]}×</td></tr>`;
    }).join('');
    wrap.innerHTML = `<table><thead><tr><th>Naam</th><th>Afmeting (cm)</th><th>Aantal</th></tr></thead><tbody>${rows}</tbody></table>
      <div class="sscpq-note">Totaal itemvolume: ${(totalVol/1000).toFixed(2)} liter</div>`;
  }

  // ---------- BOX TABEL ----------
  function renderBoxTable(){
    const wrap = document.getElementById('sscpq-boxTableWrap');
    let rows = boxes.map(b => `
      <tr><td class="sscpq-name-cell">${b.name}</td><td>${fmt(b.l)}×${fmt(b.w)}×${fmt(b.h)}</td>
      <td><button class="sscpq-btn secondary small" data-id="${b.id}" data-action="del-box">✕</button></td></tr>`).join('');
    wrap.innerHTML = `<table><thead><tr><th>Naam</th><th>Afmeting (cm)</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;
    wrap.querySelectorAll('[data-action="del-box"]').forEach(btn=>{
      btn.addEventListener('click', () => { boxes = boxes.filter(b=>b.id !== btn.dataset.id); renderBoxTable(); });
    });
  }

  // ---------- SERVICESETS-CATALOGUS (automatisch geladen bij openen) ----------
async function loadCatalog(){
  const statusEl = document.getElementById('sscpq-catalogStatus');
  statusEl.textContent = 'laden…';

  try {
    const catalogUrl =
      'https://hd-exclusiva.github.io/ServiceSets.com/data/products.json';

    const resp = await fetch(catalogUrl, {
      headers: {
        Accept: 'application/json'
      }
    });

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status} bij ${catalogUrl}`);
    }

    const catalogData = await resp.json();

    if (!Array.isArray(catalogData)) {
      throw new Error('products.json bevat geen JSON-array');
    }

    products = catalogData.map(p => ({
      id: nextId('p'),
      num: p.num,
      name: p.name,
      l: Number(p.l),
      w: Number(p.w),
      h: Number(p.h),
      weight_g: p.weight_g
    }));

    composition = {};
    renderProductTable();
    renderComposition();

    statusEl.textContent =
      `${products.length} producten geladen uit catalogus`;

  } catch (err) {
    console.error('Catalogus laden mislukt:', err);
    statusEl.textContent =
      'kon catalogus niet laden (' + err.message + ')';
  }
}

  // ---------- FILE UPLOAD ----------
  function initFileUpload(){
    const dropZone = document.getElementById('sscpq-dropZone');
    const fileInput = document.getElementById('sscpq-fileInput');
    dropZone.addEventListener('click', () => fileInput.click());
    ;['dragenter','dragover'].forEach(evt => dropZone.addEventListener(evt, e => { e.preventDefault(); dropZone.classList.add('drag'); }));
    ;['dragleave','drop'].forEach(evt => dropZone.addEventListener(evt, e => { e.preventDefault(); dropZone.classList.remove('drag'); }));
    dropZone.addEventListener('drop', e => { if(e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]); });
    fileInput.addEventListener('change', e => { if(e.target.files.length) handleFile(e.target.files[0]); });
  }

  function handleFile(file){
    const reader = new FileReader();
    reader.onload = (e) => {
      try{
        const data = new Uint8Array(e.target.result);
        const wb = XLSX.read(data, {type:'array'});
        const sheet = wb.Sheets[wb.SheetNames[0]];
        const rows = XLSX.utils.sheet_to_json(sheet, {header:1, defval:''});
        let added = 0;
        rows.forEach((r, idx) => {
          if(idx === 0) return;
          const [num, name, l, w, h] = r;
          if(name === '' && num === '') return;
          const L = parseFloat(l), W = parseFloat(w), H = parseFloat(h);
          if(isNaN(L) || isNaN(W) || isNaN(H)) return;
          products.push({ id: nextId('p'), num: String(num||'').trim(), name: String(name||'').trim() || '(naamloos)', l:L, w:W, h:H });
          added++;
        });
        renderProductTable();
        if(added === 0) alert('Geen geldige rijen gevonden. Check kolom A–E en of rij 1 een kop is.');
      } catch(err){ alert('Kon het bestand niet lezen: ' + err.message); }
    };
    reader.readAsArrayBuffer(file);
  }

  function initManualAdders(){
    document.getElementById('sscpq-addManualBtn').addEventListener('click', () => {
      const num = document.getElementById('sscpq-manNum').value.trim();
      const name = document.getElementById('sscpq-manName').value.trim();
      const l = parseFloat(document.getElementById('sscpq-manL').value);
      const w = parseFloat(document.getElementById('sscpq-manW').value);
      const h = parseFloat(document.getElementById('sscpq-manH').value);
      if(!name || isNaN(l) || isNaN(w) || isNaN(h)){ alert('Vul naam, L, B en H in.'); return; }
      products.push({id: nextId('p'), num: num || '-', name, l, w, h});
      ['sscpq-manNum','sscpq-manName','sscpq-manL','sscpq-manW','sscpq-manH'].forEach(id => document.getElementById(id).value = '');
      renderProductTable();
    });

    document.getElementById('sscpq-addBoxBtn').addEventListener('click', () => {
      const name = document.getElementById('sscpq-boxName').value.trim();
      const l = parseFloat(document.getElementById('sscpq-boxL').value);
      const w = parseFloat(document.getElementById('sscpq-boxW').value);
      const h = parseFloat(document.getElementById('sscpq-boxH').value);
      if(!name || isNaN(l) || isNaN(w) || isNaN(h)){ alert('Vul naam, L, B en H in.'); return; }
      boxes.push({id: nextId('b'), name, l, w, h});
      ['sscpq-boxName','sscpq-boxL','sscpq-boxW','sscpq-boxH'].forEach(id => document.getElementById(id).value = '');
      renderBoxTable();
    });

    document.getElementById('sscpq-loadCatalogBtn').addEventListener('click', loadCatalog);
  }

  function expandItems(){
    const out = [];
    Object.keys(composition).forEach(id => {
      const p = products.find(x=>x.id===id); if(!p) return;
      for(let i=0;i<composition[id];i++){ out.push({name: p.name, l:p.l, w:p.w, h:p.h}); }
    });
    return out;
  }

  // ---------- ISOMETRISCHE VISUALISATIE ----------
  // Palet afgeleid van de merkkleur (teal) plus gedempte, professionele
  // complementaire tinten — puur functioneel om items te onderscheiden.
  const PALETTE = ['#66C0B5','#E8917B','#7EA8C4','#E8C15D','#B98FBF','#8FBF8F','#D9C48F','#4A9E93'];

  function isoProject(x,y,z, scale, ox, oy){
    const px = (x - y) * Math.cos(Math.PI/6) * scale;
    const py = ((x + y) * Math.sin(Math.PI/6) - z) * scale;
    return [ox + px, oy + py];
  }
  function shade(hex, factor){
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    const f = (v) => Math.min(255, Math.round(v*factor));
    return `rgb(${f(r)},${f(g)},${f(b)})`;
  }
  function cuboidPolygons(x,y,z,l,w,h, scale, ox, oy, color){
    const c = (dx,dy,dz) => isoProject(x+dx, y+dy, z+dz, scale, ox, oy);
    const top = [c(0,0,h), c(l,0,h), c(l,w,h), c(0,w,h)];
    const right = [c(l,0,0), c(l,w,0), c(l,w,h), c(l,0,h)];
    const front = [c(0,w,0), c(l,w,0), c(l,w,h), c(0,w,h)];
    const poly = (pts, fill) => `<polygon points="${pts.map(p=>p.join(',')).join(' ')}" fill="${fill}" stroke="#1A171B" stroke-width="0.6"/>`;
    return poly(top, shade(color,1.15)) + poly(right, shade(color,0.7)) + poly(front, shade(color,0.9));
  }
  function binWireframe(l,w,h,scale,ox,oy){
    const c = (x,y,z) => isoProject(x,y,z,scale,ox,oy);
    const pts = { o:c(0,0,0), lx:c(l,0,0), wy:c(0,w,0), lw:c(l,w,0), oz:c(0,0,h), lxz:c(l,0,h), wyz:c(0,w,h), lwz:c(l,w,h) };
    const line = (a,b) => `<line x1="${pts[a][0]}" y1="${pts[a][1]}" x2="${pts[b][0]}" y2="${pts[b][1]}" stroke="rgba(26,23,27,0.3)" stroke-width="1" stroke-dasharray="3,2"/>`;
    return ['o-lx','o-wy','o-oz','lx-lw','lx-lxz','wy-lw','wy-wyz','oz-lxz','oz-wyz','lw-lwz','lxz-lwz','wyz-lwz']
      .map(k => line(...k.split('-'))).join('');
  }
  function renderIsoSVG(bin, placements){
    const scale = 460 / (bin.l + bin.w + bin.h);
    const ox = 260, oy = 60;
    const binEdges = binWireframe(bin.l, bin.w, bin.h, scale, ox, oy);
    const sorted = [...placements].sort((a,b) => (a.x+a.y+a.z) - (b.x+b.y+b.z));
    const itemSvg = sorted.map((p,i) => cuboidPolygons(p.x,p.y,p.z,p.l,p.w,p.h, scale, ox, oy, PALETTE[i % PALETTE.length])).join('');
    return `<svg class="sscpq-iso" viewBox="0 0 560 380" xmlns="http://www.w3.org/2000/svg">${binEdges}${itemSvg}</svg>`;
  }

  // ---------- BEREKENEN (via Python/Pyodide) ----------
  function initCalculate(){
    document.getElementById('sscpq-calcBtn').addEventListener('click', async () => {
      const items = expandItems();
      const resultWrap = document.getElementById('sscpq-resultWrap');
      if(items.length === 0){ resultWrap.innerHTML = '<div class="sscpq-empty-hint">Selecteer eerst producten in stap 2.</div>'; return; }
      if(boxes.length === 0){ resultWrap.innerHTML = '<div class="sscpq-empty-hint">Voeg minstens één kandidaat-doos toe in stap 3.</div>'; return; }

      resultWrap.innerHTML = '<div class="sscpq-empty-hint">Python berekent…</div>';
      const outcome = await pySelectBox(items, boxes);

      if(!outcome.chosen_box){
        const best = outcome.attempts.reduce((a,b) => (b.result.placed_count > a.result.placed_count ? b : a));
        resultWrap.innerHTML = `
          <div class="sscpq-result-box">
            <div class="sscpq-result-status"><span class="sscpq-status-dot fail"></span><span class="sscpq-status-text">Geen enkele doos past</span></div>
            <div class="sscpq-note">Grootste kandidaat (${best.box.name}, ${fmt(best.box.l)}×${fmt(best.box.w)}×${fmt(best.box.h)}cm) kreeg ${best.result.placed_count} van ${best.result.total_count} items geplaatst.</div>
          </div>`;
        return;
      }

      const chosen = outcome.chosen_box;
      const result = outcome.result;
      const itemVol = items.reduce((s,i)=>s + i.l*i.w*i.h, 0);
      const boxVol = chosen.l*chosen.w*chosen.h;
      const util = (itemVol/boxVol*100).toFixed(1);
      const legend = result.placements.map((p,i) => `<span><span class="sscpq-swatch" style="background:${PALETTE[i%PALETTE.length]}"></span>${p.name}</span>`).join('');

      resultWrap.innerHTML = `
        <div class="sscpq-result-box">
          <div class="sscpq-result-status">
            <span class="sscpq-status-dot ok"></span><span class="sscpq-status-text">${chosen.name} past</span>
            <span class="sscpq-status-meta">${fmt(chosen.l)}×${fmt(chosen.w)}×${fmt(chosen.h)} cm</span>
          </div>
          <div class="sscpq-stat-row">
            <div><div class="sscpq-stat-label">Items</div><div class="sscpq-stat-value">${result.placed_count}</div></div>
            <div><div class="sscpq-stat-label">Volumebenutting</div><div class="sscpq-stat-value">${util}%</div></div>
            <div><div class="sscpq-stat-label">Geteste dozen</div><div class="sscpq-stat-value">${outcome.attempts.length}</div></div>
          </div>
          ${renderIsoSVG(chosen, result.placements)}
          <div class="sscpq-legend">${legend}</div>
          <div class="sscpq-note">Berekend door packer_core.py, uitgevoerd als échte Python via Pyodide (WebAssembly).</div>
        </div>`;
    });
  }

  // ---------- INIT ----------
  function init(){
    renderProductTable();
    renderComposition();
    renderBoxTable();
    initFileUpload();
    initManualAdders();
    initCalculate();
    loadCatalog();
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();