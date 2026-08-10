 let cfgStepIndex = 1;
  function updateCfgUI(){
    for(let i=1;i<=4;i++){
      document.getElementById('cfg-step-'+i).classList.toggle('active', i===cfgStepIndex);
      document.getElementById('seg'+i).style.width = (i<=cfgStepIndex ? '100%':'0%');
      document.getElementById('lbl'+i).classList.toggle('on', i<=cfgStepIndex);
    }
    document.getElementById('cfgPrev').style.visibility = cfgStepIndex===1 ? 'hidden':'visible';
    document.getElementById('cfgNext').textContent = cfgStepIndex===4 ? 'Offerte aanvragen' : 'Volgende →';
    document.getElementById('cfgNext').onclick = cfgStepIndex===4 ? function(){alert('In het echte platform stuurt dit de configuratie als offerteaanvraag naar Odoo.');} : function(){cfgStep(1);};
  }
  function cfgStep(dir){
    cfgStepIndex = Math.min(4, Math.max(1, cfgStepIndex+dir));
    updateCfgUI();
  }
  function selectOption(btn, step, multi){
    if(multi){
      btn.classList.toggle('selected');
    } else {
      btn.parentElement.querySelectorAll('.cfg-option').forEach(o=>o.classList.remove('selected'));
      btn.classList.add('selected');
    }
    updateSummary();
  }
  function updateSummary(){
    const inhoudCount = document.querySelectorAll('#cfg-step-2 .cfg-option.selected').length;
    const verpakking = document.querySelector('#cfg-step-3 .cfg-option.selected');
    const sumInhoud = document.getElementById('sumInhoud');
    const sumVerpakking = document.getElementById('sumVerpakking');
    if(inhoudCount>0){
      sumInhoud.classList.remove('muted');
      sumInhoud.innerHTML = `<span>Inhoud</span><span>${inhoudCount} onderdelen gekozen</span>`;
      document.getElementById('sumBox2').setAttribute('opacity','1');
    }
    if(verpakking){
      sumVerpakking.classList.remove('muted');
      sumVerpakking.innerHTML = `<span>Verpakking</span><span>${verpakking.querySelector('strong').textContent}</span>`;
    }
  }
  updateCfgUI();