/* ============================================================
   LCARS — MYTECHBOOKSWIZZARD
   Application logic
   ============================================================ */

// ---- DOM references ----
const messagesEl  = document.getElementById('messages');
const inputEl     = document.getElementById('input');
const sendBtn     = document.getElementById('btn-send');
const webChk      = document.getElementById('chk-web');
const reindexBtn  = document.getElementById('btn-reindex');
const statusBox   = document.getElementById('status-box');
const docList     = document.getElementById('doc-list');
const statusDot   = document.getElementById('status-dot');
const scanBar     = document.getElementById('scan-bar');
const stardateEl  = document.getElementById('stardate-value');

let history = [];

// ---- Stardate display ----
// Stardate formula: year-based decimal (TNG era style)
function computeStardate() {
  const now   = new Date();
  const year  = now.getFullYear();
  // TNG stardates ran ~41000–57999 from 2364–2370
  // We map current year from 2000 baseline at 1000 units/year
  const base  = 2000;
  const units = 1000;
  const dayOfYear = (Date.UTC(year, now.getMonth(), now.getDate()) -
                     Date.UTC(year, 0, 0)) / 86400000;
  const fraction  = dayOfYear / 365.25;
  const stardate  = ((year - base) * units) + (fraction * units);
  return stardate.toFixed(1);
}

function updateStardate() {
  if (stardateEl) {
    stardateEl.textContent = computeStardate();
  }
}

updateStardate();
// Refresh stardate every minute
setInterval(updateStardate, 60_000);

// ---- Scan bar helpers ----
function showScanning() {
  if (scanBar) scanBar.classList.add('active');
}

function hideScanning() {
  if (scanBar) scanBar.classList.remove('active');
}

// ---- Status ----
async function loadStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const lastSync = d.last_sync
      ? new Date(d.last_sync).toLocaleString()
      : 'NEVER';

    if (statusBox) {
      statusBox.innerHTML =
        `CHUNKS: <span class="val">${d.total_chunks}</span><br>` +
        `FILES: <span class="val">${d.indexed_files.length}</span><br>` +
        `SYNCED: <span class="val">${lastSync}</span><br>` +
        `MODEL: <span class="val">${d.model}</span>`;
    }

    // Pulse dot green when online
    if (statusDot) {
      statusDot.style.background = 'var(--lcars-orange)';
    }

    if (docList) {
      docList.innerHTML = '';
      d.indexed_files.forEach(f => {
        const li = document.createElement('li');
        li.textContent = f.split('/').pop();
        li.title = f;
        docList.appendChild(li);
      });
    }
  } catch (e) {
    if (statusBox) statusBox.textContent = 'UNAVAILABLE';
    if (statusDot) statusDot.style.background = 'var(--lcars-red)';
  }
}

if (reindexBtn) {
  reindexBtn.addEventListener('click', async () => {
    reindexBtn.disabled = true;
    reindexBtn.textContent = 'INDEXING…';
    await fetch('/api/reindex', { method: 'POST' });
    setTimeout(() => {
      loadStatus();
      reindexBtn.disabled = false;
      reindexBtn.textContent = 'REINDEX';
    }, 3000);
  });
}

loadStatus();
setInterval(loadStatus, 60_000);

// ---- Chat ----
function appendMessage(role, content, sources = [], webResults = [], suggestions = []) {
  const wrapper = document.createElement('div');
  wrapper.className = `msg msg-${role}`;

  // Role label
  const label = document.createElement('div');
  label.className = 'msg-label';
  label.textContent = role === 'bot' ? 'COMPUTER' : 'OPERATOR';
  wrapper.appendChild(label);

  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  if (role === 'bot') {
    bubble.innerHTML = DOMPurify.sanitize(marked.parse(content));
  } else {
    bubble.textContent = content;
  }

  wrapper.appendChild(bubble);

  // Source tags
  if (sources.length) {
    const div = document.createElement('div');
    div.className = 'sources';
    sources.forEach(s => {
      const tag = document.createElement('span');
      tag.className = 'source-tag';
      tag.textContent = `DOC: ${s.filename} (${s.score})`;
      tag.dataset.excerpt = s.excerpt;
      div.appendChild(tag);
    });
    wrapper.appendChild(div);
  }

  // Web result links
  if (webResults.length) {
    const div = document.createElement('div');
    div.className = 'sources';
    webResults.forEach(r => {
      const a = document.createElement('a');
      a.className = 'web-tag';
      a.href = r.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.textContent = `NET: ${r.title}`;
      div.appendChild(a);
    });
    wrapper.appendChild(div);
  }

  // Suggestion boxes
  if (suggestions.length) {
    suggestions.forEach(s => {
      const box = document.createElement('div');
      box.className = 'suggestion-box';
      box.textContent = `RECOMMENDATION: ${s}`;
      wrapper.appendChild(box);
    });
  }

  messagesEl.appendChild(wrapper);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return wrapper;
}

function appendTyping() {
  const el = document.createElement('div');
  el.className = 'typing';
  el.textContent = 'PROCESSING QUERY…';
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text) return;

  inputEl.value = '';
  sendBtn.disabled = true;

  appendMessage('user', text);
  history.push({ role: 'user', content: text });

  const typing = appendTyping();
  showScanning();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        history: history.slice(-16),
        use_web_search: webChk ? webChk.checked : false,
      }),
    });

    typing.remove();
    hideScanning();

    if (!res.ok) {
      appendMessage('bot', `ERROR ${res.status}: ${res.statusText}`);
      return;
    }

    const data = await res.json();
    appendMessage('bot', data.message, data.sources, data.web_results, data.suggestions);
    history.push({ role: 'assistant', content: data.message });

    if (history.length > 40) history = history.slice(-40);
  } catch (err) {
    typing.remove();
    hideScanning();
    appendMessage('bot', `NETWORK ERROR: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

if (sendBtn) {
  sendBtn.addEventListener('click', sendMessage);
}

if (inputEl) {
  inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
}
