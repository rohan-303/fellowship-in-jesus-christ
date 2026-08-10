(function(){
'use strict';

const feed = document.getElementById('feed');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const lastUpdated = document.getElementById('lastUpdated');
const DATA_URL = 'messages.json';
let lastTimestamp = '';
let pollTimer;

// ── Lightbox ──────────────────────────────
let lb;
function getLightbox(){
  if(!lb){
    lb = document.createElement('div'); lb.className='lightbox';
    lb.innerHTML = '<span class="close">&times;</span>';
    lb.addEventListener('click', e => { if(e.target===lb||e.target.className==='close') closeLightbox() });
    document.body.appendChild(lb);
  }
  return lb;
}
function openLightbox(html){
  const box = getLightbox();
  box.querySelector('.close').insertAdjacentElement('afterend', html);
  box.classList.add('active');
  document.body.style.overflow='hidden';
}
function closeLightbox(){
  const box = getLightbox();
  const kids = [...box.children];
  kids.forEach(c => { if(!c.className.includes('close')) c.remove() });
  box.classList.remove('active');
  document.body.style.overflow='';
}

// ── Time formatter ────────────────────────
function formatTime(iso){
  const d = new Date(iso);
  const now = new Date();
  const diff = now - d;
  const mins = Math.floor(diff/60000);
  if(mins<1) return 'Just now';
  if(mins<60) return `${mins}m ago`;
  const hrs = Math.floor(mins/60);
  if(hrs<24) return `${hrs}h ago`;
  const days = Math.floor(hrs/24);
  if(days<7) return `${days}d ago`;
  return d.toLocaleDateString('en-US',{month:'short',day:'numeric',year: d.getFullYear()!==now.getFullYear()?'numeric':undefined});
}

// ── Render a single message card ──────────
function renderCard(msg, idx){
  const card = document.createElement('div');
  card.className = 'card';
  card.style.animationDelay = `${Math.min(idx,20)*0.04}s`;

  const initials = (msg.sender||'?').split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase();

  let bodyHTML = '';
  // Text
  if(msg.text){
    bodyHTML += `<div class="card-body">${linkify(escapeHTML(msg.text))}</div>`;
  }
  // Images
  if(msg.images && msg.images.length){
    bodyHTML += '<div class="media-grid">';
    msg.images.forEach(img => {
      bodyHTML += `<div class="media-item" onclick="window._openMedia('image','${escapeAttr(img)}')"><img src="${escapeAttr(img)}" alt="Shared image" loading="lazy"></div>`;
    });
    bodyHTML += '</div>';
  }
  // Videos
  if(msg.videos && msg.videos.length){
    msg.videos.forEach(v => {
      bodyHTML += `<a class="video-link" href="${escapeAttr(v.url||v)}" target="_blank" rel="noopener"><div class="play-icon"></div><div><strong>📹 Video</strong><br><small>${escapeHTML(v.title||'Tap to watch')}</small></div></a>`;
    });
  }
  // Video links in text
  if(msg.videoLinks && msg.videoLinks.length){
    msg.videoLinks.forEach(vl => {
      bodyHTML += `<a class="video-link" href="${escapeAttr(vl.url)}" target="_blank" rel="noopener"><div class="play-icon"></div><div><strong>📹 ${escapeHTML(vl.platform||'Video')}</strong><br><small>Tap to watch</small></div></a>`;
    });
  }

  card.innerHTML = `
    <div class="card-header">
      <div class="avatar">${initials}</div>
      <span class="sender">${escapeHTML(msg.sender||'Unknown')}</span>
      <span class="time">${formatTime(msg.timestamp)}</span>
    </div>
    ${bodyHTML}
  `;
  return card;
}

// ── Render feed ───────────────────────────
function renderFeed(messages){
  feed.innerHTML = '';
  if(!messages.length){
    feed.innerHTML = `<div class="empty-state"><div class="icon">🕊️</div><h2>No messages yet</h2><p>Messages from the WhatsApp group will appear here as they arrive.</p></div>`;
    return;
  }
  const frag = document.createDocumentFragment();
  messages.forEach((msg,i) => frag.appendChild(renderCard(msg,i)));
  feed.appendChild(frag);
}

// ── Load and render ───────────────────────
async function loadMessages(){
  try{
    const resp = await fetch(DATA_URL + '?t=' + Date.now());
    if(!resp.ok) throw new Error(resp.status);
    const data = await resp.json();
    const msgs = data.messages || [];
    const ts = data.last_updated || '';

    if(ts !== lastTimestamp){
      renderFeed(msgs);
      lastTimestamp = ts;
    }

    statusDot.className = 'dot live';
    statusText.textContent = `${msgs.length} message${msgs.length!==1?'s':''}`;
    if(data.last_updated){
      lastUpdated.textContent = '· Updated ' + formatTime(data.last_updated);
    }
  }catch(e){
    statusDot.className = 'dot error';
    statusText.textContent = 'Offline';
    if(feed.querySelector('.loading-state')){
      feed.innerHTML = `<div class="empty-state"><div class="icon">⛅</div><h2>Connecting...</h2><p>Waiting for the first messages to arrive.</p></div>`;
    }
  }
}

// ── Helpers ───────────────────────────────
function escapeHTML(s){ const d=document.createElement('div'); d.textContent=s; return d.innerHTML }
function escapeAttr(s){ return s.replace(/"/g,'&quot;').replace(/'/g,'&#39;') }
function linkify(text){
  return text
    .replace(/https?:\/\/[^\s<]+/g, url => {
      try{ new URL(url); return `<a href="${url}" target="_blank" rel="noopener">${url}</a>` }
      catch{ return url }
    });
}

// ── Media click handler ───────────────────
window._openMedia = function(type, src){
  if(type==='image'){
    const img = document.createElement('img'); img.src=src; img.alt='';
    openLightbox(img);
  }
};

// ── Keyboard ──────────────────────────────
document.addEventListener('keydown',e=>{ if(e.key==='Escape') closeLightbox() });

// ── Polling ───────────────────────────────
function startPolling(){ loadMessages(); pollTimer = setInterval(loadMessages, 30000) }
function stopPolling(){ clearInterval(pollTimer) }
document.addEventListener('visibilitychange', ()=>{ document.hidden?stopPolling():startPolling() });

// ── Init ──────────────────────────────────
loadMessages();
pollTimer = setInterval(loadMessages, 30000);

})();
