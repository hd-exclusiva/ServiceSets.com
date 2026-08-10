 function showPage(id){
    document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
    document.getElementById('page-'+id).classList.add('active');
    document.querySelectorAll('nav.primary a').forEach(a=>a.classList.toggle('active', a.dataset.page===id));
    window.scrollTo({top:0, behavior:'instant' in window ? 'instant':'auto'});
    closeMobileNav();
  }
  function scrollToId(id){
    setTimeout(()=>{ const el=document.getElementById(id); if(el) el.scrollIntoView({behavior:'smooth'}); }, 60);
  }

  // ---------- mobile nav ----------
  function toggleMobileNav(){
    const nav=document.getElementById('primaryNav');
    nav.style.display = (nav.style.display==='flex') ? 'none' : 'flex';
    nav.style.flexDirection='column';
    nav.style.position='absolute'; nav.style.top='100%'; nav.style.left='0'; nav.style.right='0';
    nav.style.background='#fff'; nav.style.padding='10px 20px 20px'; nav.style.borderBottom='1px solid #E4E7E6';
  }
  function closeMobileNav(){
    if(window.innerWidth<=980){ const nav=document.getElementById('primaryNav'); nav.style.display='none'; }
  }

  // ---------- language selector ----------
  function toggleLang(e){
    e.stopPropagation();
    closeSearch();
    document.getElementById('langSelect').classList.toggle('open');
  }
  function setLang(code, e){
    if(e) e.stopPropagation();
    document.getElementById('langCurrent').textContent = code;
    document.querySelectorAll('.lang-menu button').forEach(b=>b.setAttribute('aria-pressed','false'));
    document.getElementById('langSelect').classList.remove('open');
  }

  // ---------- header search ----------
  function toggleSearch(e){
    e.stopPropagation();
    document.getElementById('langSelect').classList.remove('open');
    const panel = document.getElementById('searchPanel');
    const toggleBtn = document.getElementById('searchToggle');
    const isOpen = panel.classList.toggle('open');
    toggleBtn.classList.toggle('active', isOpen);
    toggleBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    if(isOpen){
      setTimeout(()=>document.getElementById('searchInput').focus(), 60);
    }
  }
  function closeSearch(){
    document.getElementById('searchPanel').classList.remove('open');
    document.getElementById('searchToggle').classList.remove('active');
    document.getElementById('searchToggle').setAttribute('aria-expanded', 'false');
  }