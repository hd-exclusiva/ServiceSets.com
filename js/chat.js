  function toggleChat(){
    document.getElementById('chatPanel').classList.toggle('open');
  }
  function chatQuick(msg){
    addBubble(msg, 'user');
    respond(msg);
  }
  function chatSend(){
    const input = document.getElementById('chatInput');
    if(!input.value.trim()) return;
    addBubble(input.value, 'user');
    respond(input.value);
    input.value='';
  }
  function addBubble(text, who){
    const body = document.getElementById('chatBody');
    const b = document.createElement('div');
    b.className = 'bubble '+who;
    b.textContent = text;
    body.appendChild(b);
    body.scrollTop = body.scrollHeight;
  }
  function respond(msg){
    setTimeout(()=>{
      let reply = "Goede vraag — in de live omgeving beantwoordt onze AI-chatbot dit op basis van de kennisbank, of verbindt ik je met een collega.";
      if(/levertijd/i.test(msg)) reply = "Standaardpakketten zijn uit voorraad leverbaar, meestal binnen 2–3 werkdagen. Maatwerk sets hangen af van de configuratie.";
      if(/maatwerk|180/i.test(msg)) reply = "Maatwerk service-sets, inclusief eigen verpakking, kunnen we vanaf 180 sets samenstellen.";
      if(/medewerker/i.test(msg)) reply = "Ik verbind je door — je kunt ook direct bellen naar 088 435 66 88, ma–vr 8:30–17:00.";
      addBubble(reply, 'bot');
    }, 500);
  }