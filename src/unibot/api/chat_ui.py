CHAT_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>UniBot Chat</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',-apple-system,sans-serif;background:#0f0f1a;color:#e4e4f0;height:100vh;display:flex;flex-direction:column}
header{background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);padding:16px 24px;display:flex;align-items:center;gap:14px;border-bottom:1px solid rgba(255,255,255,.06);flex-shrink:0}
header .logo{width:38px;height:38px;border-radius:10px;background:linear-gradient(135deg,#4facfe,#00f2fe);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;color:#fff}
header h1{font-size:18px;font-weight:600;letter-spacing:-.3px;color:#f0f0ff}
header p{font-size:12px;color:rgba(255,255,255,.45);margin-top:1px}
#chat-container{flex:1;overflow-y:auto;padding:24px 16px;scroll-behavior:smooth}
#chat-container::-webkit-scrollbar{width:5px}
#chat-container::-webkit-scrollbar-track{background:transparent}
#chat-container::-webkit-scrollbar-thumb{background:rgba(255,255,255,.1);border-radius:3px}
.message{padding:20px 24px;border-radius:16px;max-width:780px;margin:12px auto;line-height:1.65;font-size:14px;animation:fadeIn .3s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.message.user{background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#fff;margin-left:auto;margin-right:24px;border-bottom-right-radius:4px;max-width:600px}
.message.bot{background:#1e1e32;border:1px solid rgba(255,255,255,.06);margin-right:auto;margin-left:24px;border-bottom-left-radius:4px;color:#d0d0e0}
.message.bot .header{font-size:13px;font-weight:600;color:#4facfe;margin-bottom:10px;display:flex;align-items:center;gap:8px}
.message.bot .header .status-dot{width:7px;height:7px;border-radius:50%;background:#22c55e;display:inline-block;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.message.bot .answer{white-space:pre-wrap;word-wrap:break-word}
.message.bot .citations{margin-top:16px;padding-top:14px;border-top:1px solid rgba(255,255,255,.06)}
.message.bot .citations summary{cursor:pointer;font-size:13px;color:rgba(255,255,255,.5);font-weight:500}
.message.bot .citations .cite-item{background:rgba(255,255,255,.03);border-radius:8px;padding:10px 14px;margin-top:8px;font-size:12px;line-height:1.5}
.message.bot .citations .cite-item .cite-url{color:#4facfe;word-break:break-all;font-size:11px;margin-top:3px}
.message.bot .citations .cite-item .cite-id{color:rgba(255,255,255,.35);font-size:11px;margin-right:8px}
#unibot-error{background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.3);border-radius:12px;padding:14px 18px;max-width:600px;margin:12px auto;font-size:13px;color:#fca5a5;display:none}
#welcome-screen{text-align:center;padding:60px 20px 40px}
#welcome-screen .icon{font-size:48px;margin-bottom:16px}
#welcome-screen h2{font-size:22px;font-weight:600;color:#f0f0ff;margin-bottom:8px}
#welcome-screen p{color:rgba(255,255,255,.45);font-size:14px;max-width:460px;margin:0 auto 28px;line-height:1.6}
#welcome-screen .suggestions{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;max-width:600px;margin:0 auto}
#welcome-screen .suggestions button{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.08);color:rgba(255,255,255,.7);padding:10px 18px;border-radius:20px;font-size:13px;cursor:pointer;transition:all .2s;font-family:inherit}
#welcome-screen .suggestions button:hover{background:rgba(79,172,254,.15);border-color:rgba(79,172,254,.3);color:#4facfe}
#input-area{background:#1a1a2e;border-top:1px solid rgba(255,255,255,.06);padding:16px 24px;flex-shrink:0}
#input-area .input-row{max-width:780px;margin:0 auto;display:flex;gap:10px}
#input-area input{flex:1;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:12px 18px;font-size:14px;color:#e4e4f0;outline:none;font-family:inherit;transition:border .2s}
#input-area input:focus{border-color:rgba(79,172,254,.5);background:rgba(255,255,255,.08)}
#input-area input::placeholder{color:rgba(255,255,255,.3)}
#input-area button{background:linear-gradient(135deg,#4facfe,#00f2fe);border:none;border-radius:12px;padding:12px 20px;font-size:14px;font-weight:600;cursor:pointer;transition:opacity .2s;color:#fff;font-family:inherit;white-space:nowrap}
#input-area button:disabled{opacity:.4;cursor:not-allowed}
#input-area button:not(:disabled):hover{opacity:.9}
.loading-dots{display:flex;gap:4px;padding:4px 0}
.loading-dots span{width:7px;height:7px;border-radius:50%;background:rgba(255,255,255,.4);animation:bounce 1.4s ease-in-out infinite}
.loading-dots span:nth-child(2){animation-delay:.2s}
.loading-dots span:nth-child(3){animation-delay:.4s}
@keyframes bounce{0%,80%,100%{transform:scale(.6)}40%{transform:scale(1)}}
.hidden{display:none!important}
@media(max-width:640px){.message{padding:16px 18px;font-size:13px;margin:8px 0}
.message.user{margin-left:auto;margin-right:0}
.message.bot{margin-right:auto;margin-left:0}
#input-area{padding:12px 16px}
header{padding:12px 16px}
#welcome-screen{padding:30px 16px 20px}
#welcome-screen .suggestions button{padding:8px 14px;font-size:12px}}
</style>
</head>
<body>
<header>
<div class="logo">U</div>
<div><h1>UniBot</h1><p>KFUEIT Intelligent Query System</p></div>
</header>
<div id="chat-container">
<div id="welcome-screen">
<div class="icon">🤖</div>
<h2>Ask me anything about KFUEIT</h2>
<p>Ask about programs, admissions, scholarships, faculty, events, and more.</p>
<div class="suggestions">
<button onclick="ask('What programs does KFUEIT offer?')">What programs does KFUEIT offer?</button>
<button onclick="ask('What scholarships are available?')">What scholarships are available?</button>
<button onclick="ask('How do I apply for admission?')">How do I apply for admission?</button>
<button onclick="ask('List the engineering faculties')">List the engineering faculties</button>
</div>
</div>
</div>
<div id="input-area">
<div class="input-row">
<input id="query-input" type="text" placeholder="Ask a question about KFUEIT..." onkeydown="if(event.key==='Enter')send()">
<button id="send-btn" onclick="send()">Send</button>
</div>
</div>
<script>
const chat=document.getElementById('chat-container');
const input=document.getElementById('query-input');
const btn=document.getElementById('send-btn');
let loading=false;

function addMessage(text,role){
const welcome=document.getElementById('welcome-screen');
if(welcome&&!welcome.classList.contains('hidden'))welcome.classList.add('hidden');
const div=document.createElement('div');
div.className='message '+role;
if(role==='user'){
div.textContent=text;
}else{
div.innerHTML=`
<div class="header"><span class="status-dot"></span>UniBot</div>
<div class="answer">${text}</div>`;
}
chat.appendChild(div);
chat.scrollTop=chat.scrollHeight;
return div;
}

function addError(msg){
const welcome=document.getElementById('welcome-screen');
if(welcome&&!welcome.classList.contains('hidden'))welcome.classList.add('hidden');
const el=document.getElementById('unibot-error');
el.textContent=msg;
el.style.display='block';
chat.appendChild(el);
chat.scrollTop=chat.scrollHeight;
}

function showLoading(){
const div=document.createElement('div');
div.className='message bot loading-msg';
div.id='loading-msg';
div.innerHTML='<div class="loading-dots"><span></span><span></span><span></span></div>';
chat.appendChild(div);
chat.scrollTop=chat.scrollHeight;
}

function removeLoading(){
const el=document.getElementById('loading-msg');
if(el)el.remove();
}

function formatAnswer(text,claims,citations){
let html=escapeHtml(text).replace(/\n/g,'<br>');
if(citations&&citations.length>0){
html+='<div class="citations"><details><summary>📚 Sources ('+citations.length+')</summary>';
citations.forEach(c=>{
html+=`<div class="cite-item"><span class="cite-id">${escapeHtml(c.citation_id)}</span>${escapeHtml(c.source_url||'')}<div class="cite-url">${c.chunk_id||''}</div></div>`;
});
html+='</details></div>';
}
return html;
}

function escapeHtml(s){
const d=document.createElement('div');
d.textContent=s||'';
return d.innerHTML;
}

async function ask(text){
input.value=text;
await send();
}

async function send(){
if(loading)return;
const q=input.value.trim();
if(!q)return;
loading=true;
btn.disabled=true;
input.disabled=true;
addMessage(q,'user');
input.value='';
showLoading();
try{
const res=await fetch('/query',{
method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({query_text:q})
});
removeLoading();
if(!res.ok){
let err='';
try{const e=await res.json();err=e.detail||JSON.stringify(e)}catch{err='Server error ('+res.status+')'}
addError('Error: '+err);
loading=false;btn.disabled=false;input.disabled=false;input.focus();
return;
}
const data=await res.json();
const html=formatAnswer(data.answer_text||'No answer',data.claims,data.citations);
addMessage(html,'bot');
}catch(e){
removeLoading();
addError('Network error: '+e.message);
}
loading=false;
btn.disabled=false;
input.disabled=false;
input.focus();
}
</script>
</body>
</html>
"""
