

const state = {
  currentSessionId: null,
  sessions: [],
  currentModel: '',
  availableModels: [],
  stagedAttachments: [], 
  isStreaming: false,
  streamAbortController: null,
  activeTab: 'chat', 
};

const dom = {
  
  tabChat: document.getElementById('tabChat'),
  tabKnowledge: document.getElementById('tabKnowledge'),
  chatView: document.getElementById('chatView'),
  knowledgeView: document.getElementById('knowledgeView'),
  kbBadgeCount: document.getElementById('kbBadgeCount'),
  toggleSidebarBtn: document.getElementById('toggleSidebarBtn'),
  appSidebar: document.getElementById('appSidebar'),

  
  ollamaStatusPill: document.getElementById('ollamaStatusPill'),
  ollamaStatusText: document.getElementById('ollamaStatusText'),
  modelSelect: document.getElementById('modelSelect'),
  statVectors: document.getElementById('statVectors'),
  statFiles: document.getElementById('statFiles'),

  
  newChatBtn: document.getElementById('newChatBtn'),
  sessionsList: document.getElementById('sessionsList'),
  sessionSearchInput: document.getElementById('sessionSearchInput'),
  currentSessionTitle: document.getElementById('currentSessionTitle'),
  clearChatBtn: document.getElementById('clearChatBtn'),

  
  modeDeepthink: document.getElementById('modeDeepthink'),
  modeTokenless: document.getElementById('modeTokenless'),

  
  messagesContainer: document.getElementById('messagesContainer'),
  welcomeHero: document.getElementById('welcomeHero'),
  messagesStream: document.getElementById('messagesStream'),
  demoDataBanner: document.getElementById('demoDataBanner'),
  quickImportBtn: document.getElementById('quickImportBtn'),

  
  promptInput: document.getElementById('promptInput'),
  sendBtn: document.getElementById('sendBtn'),
  sendIcon: document.getElementById('sendIcon'),
  stopIcon: document.getElementById('stopIcon'),
  attachFileBtn: document.getElementById('attachFileBtn'),
  fileInput: document.getElementById('fileInput'),
  attachmentPills: document.getElementById('attachmentPills'),
  dropOverlay: document.getElementById('dropOverlay'),

  
  kbUploadBtn: document.getElementById('kbUploadBtn'),
  kbFileInput: document.getElementById('kbFileInput'),
  kbImportProcurementBtn: document.getElementById('kbImportProcurementBtn'),
  kbSyncBtn: document.getElementById('kbSyncBtn'),
  syncIcon: document.getElementById('syncIcon'),
  syncBtnText: document.getElementById('syncBtnText'),
  syncReportSummary: document.getElementById('syncReportSummary'),
  kbSearchInput: document.getElementById('kbSearchInput'),
  kbTableBody: document.getElementById('kbTableBody'),

  
  kbStatTotalDocs: document.getElementById('kbStatTotalDocs'),
  kbStatVectors: document.getElementById('kbStatVectors'),
  kbStatActiveDocs: document.getElementById('kbStatActiveDocs'),
  kbStatEmbedModel: document.getElementById('kbStatEmbedModel'),

  
  chunkModal: document.getElementById('chunkModal'),
  modalChunkCategory: document.getElementById('modalChunkCategory'),
  modalChunkSource: document.getElementById('modalChunkSource'),
  modalChunkText: document.getElementById('modalChunkText'),
  modalCloseBtn: document.getElementById('modalCloseBtn'),
  toastContainer: document.getElementById('toastContainer'),
};

function showToast(message, type = 'info', duration = 3500) {
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span class="toast-badge">[${type === 'success' ? 'SUCCESS' : type === 'error' ? 'ERROR' : 'INFO'}]</span>
    <span>${escapeHtml(message)}</span>
  `;
  dom.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 250);
  }, duration);
}

function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(text).replace(/[&<>"']/g, (m) => map[m]);
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function timeAgo(dateString) {
  if (!dateString) return '';
  const now = new Date();
  const date = new Date(dateString);
  const diff = Math.floor((now - date) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function renderMarkdown(raw) {
  if (!raw) return '';
  let text = escapeHtml(raw);

  
  text = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    const language = lang || 'code';
    return `
      <div class="code-block-container">
        <div class="code-header-bar">
          <span>${language}</span>
          <button class="copy-code-btn" onclick="copyCode(this)">Copy</button>
        </div>
        <pre><code class="language-${language}">${code.trim()}</code></pre>
      </div>
    `;
  });

  
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>');

  
  text = text.replace(/((\|[^\n]+\|\n?){2,})/g, (tableText) => {
    const lines = tableText.trim().split('\n');
    if (lines.length < 2) return tableText;

    let html = '<table><thead><tr>';
    const headerCols = lines[0].split('|').slice(1, -1);
    headerCols.forEach((col) => {
      html += `<th>${col.trim()}</th>`;
    });
    html += '</tr></thead><tbody>';

    
    for (let i = 2; i < lines.length; i++) {
      html += '<tr>';
      const cols = lines[i].split('|').slice(1, -1);
      cols.forEach((col) => {
        html += `<td>${col.trim()}</td>`;
      });
      html += '</tr>';
    }
    html += '</tbody></table>';
    return html;
  });

  
  text = text.replace(/^>\s+(.+)$/gm, '<blockquote>$1</blockquote>');

  
  text = text.replace(/^#### (.*$)/gm, '<h4>$1</h4>');
  text = text.replace(/^### (.*$)/gm, '<h3>$1</h3>');
  text = text.replace(/^## (.*$)/gm, '<h2>$1</h2>');
  text = text.replace(/^# (.*$)/gm, '<h1>$1</h1>');

  
  text = text.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
  text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');

  
  text = text.replace(/^\s*[-*]\s+(.*)$/gm, '<li>$1</li>');
  text = text.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

  
  const paragraphs = text.split(/\n{2,}/).map((p) => {
    if (p.startsWith('<table') || p.startsWith('<pre') || p.startsWith('<div class="code') || p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<blockquote')) {
      return p;
    }
    return `<p>${p.replace(/\n/g, '<br>')}</p>`;
  });

  return paragraphs.join('\n');
}

window.copyCode = function (btn) {
  const code = btn.closest('.code-block-container').querySelector('code').innerText;
  navigator.clipboard.writeText(code).then(() => {
    btn.innerText = 'Copied!';
    setTimeout(() => (btn.innerText = 'Copy'), 2000);
  });
};

window.copyMessageText = function (btn) {
  const messageCard = btn.closest('.message-card');
  const markdownText = messageCard.querySelector('.markdown-body').innerText;
  navigator.clipboard.writeText(markdownText).then(() => {
    btn.innerText = 'Copied';
    setTimeout(() => (btn.innerText = 'Copy'), 2000);
  });
};

async function initApp() {
  setupEventListeners();
  await checkStatus();
  await loadSessions();
  await loadKnowledgeBase();

  
  setInterval(checkStatus, 15000);
}

async function checkStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();

    
    if (data.ollama.running) {
      dom.ollamaStatusPill.className = 'status-indicator-pill online';
      dom.ollamaStatusText.innerText = `Ollama: ${data.ollama.port}`;
    } else {
      dom.ollamaStatusPill.className = 'status-indicator-pill';
      dom.ollamaStatusText.innerText = 'Ollama Offline';
    }

    
    state.availableModels = data.ollama.available_models || [];
    state.currentModel = data.ollama.active_model || '';
    renderModelSelect();

    
    dom.statVectors.innerText = data.rag.vectors_count || 0;
    dom.statFiles.innerText = data.rag.documents_count || 0;
    dom.kbBadgeCount.innerText = data.rag.documents_count || 0;
    dom.kbStatTotalDocs.innerText = data.rag.documents_count || 0;
    dom.kbStatVectors.innerText = data.rag.vectors_count || 0;
    dom.kbStatActiveDocs.innerText = data.rag.active_documents_count || 0;

    
    if (data.procurement_demo_available && data.rag.documents_count === 0) {
      dom.demoDataBanner.classList.remove('hidden');
    } else {
      dom.demoDataBanner.classList.add('hidden');
    }
  } catch (err) {
    console.error('Failed to fetch status:', err);
    dom.ollamaStatusText.innerText = 'Server Error';
  }
}

function renderModelSelect() {
  dom.modelSelect.innerHTML = '';
  if (!state.availableModels.length) {
    const opt = document.createElement('option');
    opt.value = state.currentModel;
    opt.innerText = state.currentModel || 'No models found';
    dom.modelSelect.appendChild(opt);
    return;
  }

  state.availableModels.forEach((m) => {
    const opt = document.createElement('option');
    opt.value = m;
    opt.innerText = m;
    if (m === state.currentModel) opt.selected = true;
    dom.modelSelect.appendChild(opt);
  });
}

async function loadSessions() {
  try {
    const res = await fetch('/api/sessions');
    state.sessions = await res.json();
    renderSessionsList();

    if (state.sessions.length > 0) {
      if (!state.currentSessionId) {
        selectSession(state.sessions[0].id);
      }
    } else {
      await createNewSession();
    }
  } catch (err) {
    console.error('Failed to load sessions:', err);
  }
}

function renderSessionsList(filterText = '') {
  dom.sessionsList.innerHTML = '';

  const filtered = state.sessions.filter((s) =>
    s.title.toLowerCase().includes(filterText.toLowerCase())
  );

  if (!filtered.length) {
    dom.sessionsList.innerHTML = `<div class="empty-state-cell" style="padding:16px;">No chats found</div>`;
    return;
  }

  filtered.forEach((session) => {
    const item = document.createElement('div');
    item.className = `session-item ${session.id === state.currentSessionId ? 'active' : ''}`;
    item.dataset.id = session.id;

    item.innerHTML = `
      <div class="session-item-content">
        <div class="session-item-title">${escapeHtml(session.title)}</div>
        <div class="session-item-sub">
          <span>${timeAgo(session.updated_at)}</span>
          <span>•</span>
          <span>${session.message_count} msgs</span>
        </div>
      </div>
      <div class="session-actions">
        <button class="action-icon-btn delete-btn" title="Delete conversation" onclick="event.stopPropagation(); deleteSession('${session.id}')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
        </button>
      </div>
    `;

    item.addEventListener('click', () => selectSession(session.id));
    dom.sessionsList.appendChild(item);
  });
}

async function selectSession(sessionId) {
  if (state.isStreaming) {
    showToast('Please wait for generation to finish or click stop.', 'info');
    return;
  }
  state.currentSessionId = sessionId;
  renderSessionsList();

  try {
    const res = await fetch(`/api/sessions/${sessionId}`);
    const data = await res.json();

    dom.currentSessionTitle.innerText = data.title || 'New chat';

    
    const modes = data.modes || ['deepthink'];
    dom.modeDeepthink.checked = modes.includes('deepthink');
    dom.modeTokenless.checked = modes.includes('tokenless');

    renderMessages(data.messages || []);
  } catch (err) {
    console.error('Failed to select session:', err);
    showToast('Could not load session', 'error');
  }
}

async function createNewSession() {
  if (state.isStreaming) return;
  try {
    const res = await fetch('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'New chat' }),
    });
    const newSession = await res.json();
    state.sessions.unshift({
      id: newSession.id,
      title: newSession.title,
      created_at: newSession.created_at,
      updated_at: newSession.updated_at,
      message_count: 0,
      snippet: '',
    });
    await selectSession(newSession.id);
  } catch (err) {
    console.error('Failed to create session:', err);
    showToast('Failed to create chat', 'error');
  }
}

window.deleteSession = async function (sessionId) {
  if (!confirm('Are you sure you want to delete this conversation?')) return;
  try {
    await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
    state.sessions = state.sessions.filter((s) => s.id !== sessionId);

    if (state.currentSessionId === sessionId) {
      state.currentSessionId = null;
      if (state.sessions.length > 0) {
        selectSession(state.sessions[0].id);
      } else {
        createNewSession();
      }
    } else {
      renderSessionsList();
    }
    showToast('Chat deleted', 'info');
  } catch (err) {
    console.error('Failed to delete session:', err);
    showToast('Could not delete session', 'error');
  }
};

async function updateSessionTitle(newTitle) {
  if (!state.currentSessionId) return;
  try {
    await fetch(`/api/sessions/${state.currentSessionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: newTitle }),
    });
    const s = state.sessions.find((x) => x.id === state.currentSessionId);
    if (s) s.title = newTitle;
    renderSessionsList();
  } catch (err) {
    console.error('Failed to update title:', err);
  }
}

async function updateSessionModes() {
  if (!state.currentSessionId) return;
  const modes = [];
  if (dom.modeDeepthink.checked) modes.push('deepthink');
  if (dom.modeTokenless.checked) modes.push('tokenless');

  try {
    await fetch(`/api/sessions/${state.currentSessionId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ modes }),
    });
  } catch (err) {
    console.error('Failed to update modes:', err);
  }
}

function renderMessages(messages) {
  dom.messagesStream.innerHTML = '';

  if (!messages || messages.length === 0) {
    dom.welcomeHero.classList.remove('hidden');
    return;
  }

  dom.welcomeHero.classList.add('hidden');

  messages.forEach((msg) => {
    appendMessageElement(msg.role, msg.content, { skipScroll: true });
  });

  scrollToBottom();
}

function appendMessageElement(role, content, options = {}) {
  dom.welcomeHero.classList.add('hidden');

  const row = document.createElement('div');
  row.className = `message-row ${role}-row`;

  const avatar = document.createElement('div');
  avatar.className = 'message-avatar';
  avatar.innerHTML = role === 'user' ? '<span class="avatar-label">USER</span>' : '<span class="avatar-label">AI</span>';

  const body = document.createElement('div');
  body.className = 'message-body';

  const card = document.createElement('div');
  card.className = 'message-card';

  const markdownDiv = document.createElement('div');
  markdownDiv.className = 'markdown-body';
  markdownDiv.innerHTML = renderMarkdown(content);
  card.appendChild(markdownDiv);

  if (role === 'assistant') {
    const actions = document.createElement('div');
    actions.className = 'message-actions';
    actions.innerHTML = `
      <button class="action-icon-btn" onclick="copyMessageText(this)" title="Copy message">Copy</button>
    `;
    card.appendChild(actions);
  }

  body.appendChild(card);
  row.appendChild(avatar);
  row.appendChild(body);

  dom.messagesStream.appendChild(row);

  if (!options.skipScroll) {
    scrollToBottom();
  }

  return { row, card, markdownDiv };
}

function scrollToBottom() {
  dom.messagesContainer.scrollTop = dom.messagesContainer.scrollHeight;
}

async function handleSendMessage() {
  const prompt = dom.promptInput.value.trim();
  if ((!prompt && state.stagedAttachments.length === 0) || state.isStreaming) return;

  const currentPrompt = prompt || 'Please examine the attached file(s).';
  dom.promptInput.value = '';
  dom.promptInput.style.height = 'auto';

  
  appendMessageElement('user', currentPrompt);

  
  const { card: assistantCard, markdownDiv: assistantMarkdown } = appendMessageElement('assistant', '');

  
  let thoughtAccordion = null;
  let thoughtContent = null;
  let thoughtStartTime = Date.now();
  let thoughtTimerInterval = null;

  if (dom.modeDeepthink.checked) {
    thoughtAccordion = document.createElement('div');
    thoughtAccordion.className = 'thought-accordion';
    thoughtAccordion.innerHTML = `
      <div class="thought-header">
        <div class="thought-title-group">
          <span class="thought-badge">
            <span class="thought-spinner"></span>
            Reasoning...
          </span>
          <span class="thought-timer">(0s)</span>
        </div>
        <span class="thought-chevron">[Details]</span>
      </div>
      <div class="thought-content"></div>
    `;

    thoughtContent = thoughtAccordion.querySelector('.thought-content');
    const thoughtTimer = thoughtAccordion.querySelector('.thought-timer');

    thoughtTimerInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - thoughtStartTime) / 1000);
      thoughtTimer.innerText = `(${elapsed}s)`;
    }, 1000);

    thoughtAccordion.querySelector('.thought-header').addEventListener('click', () => {
      thoughtAccordion.classList.toggle('collapsed');
    });

    assistantCard.insertBefore(thoughtAccordion, assistantMarkdown);
  }

  
  let ragContainer = null;

  
  const attachmentsToSend = [...state.stagedAttachments];
  clearStagedAttachments();

  
  const modes = [];
  if (dom.modeDeepthink.checked) modes.push('deepthink');
  if (dom.modeTokenless.checked) modes.push('tokenless');

  
  setStreamingState(true);

  let accumulatedContent = '';
  let accumulatedThought = '';

  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.currentSessionId,
        prompt: currentPrompt,
        model: state.currentModel,
        modes: modes,
        attachments: attachmentsToSend,
      }),
    });

    if (!response.ok) {
      const errData = await response.json();
      throw new Error(errData.detail || 'Chat request failed');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop(); 

      for (const block of lines) {
        if (!block.trim()) continue;

        let eventType = 'message';
        let eventData = '';

        for (const line of block.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            eventData = line.slice(6).trim();
          }
        }

        if (!eventData) continue;
        const payload = JSON.parse(eventData);

        if (eventType === 'rag') {
          
          const chunks = payload.chunks || [];
          if (chunks.length > 0) {
            ragContainer = document.createElement('div');
            ragContainer.className = 'rag-citations-box';
            ragContainer.innerHTML = `
              <span class="rag-label">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
                Referenced ${chunks.length} Sources:
              </span>
            `;

            chunks.forEach((chunk, i) => {
              const chip = document.createElement('span');
              chip.className = 'rag-chip';
              chip.innerText = `[${chunk.category}] ${chunk.source.split('/').pop()}`;
              chip.title = 'Click to inspect retrieved chunk';
              chip.addEventListener('click', () => openChunkModal(chunk));
              ragContainer.appendChild(chip);
            });

            if (thoughtAccordion) {
              assistantCard.insertBefore(ragContainer, thoughtAccordion);
            } else {
              assistantCard.insertBefore(ragContainer, assistantMarkdown);
            }
          }
        } else if (eventType === 'thinking') {
          if (thoughtAccordion && thoughtContent) {
            accumulatedThought += payload.content || '';
            thoughtContent.innerText = accumulatedThought;
            thoughtContent.scrollTop = thoughtContent.scrollHeight;
          }
        } else if (eventType === 'token') {
          
          if (thoughtTimerInterval) {
            clearInterval(thoughtTimerInterval);
            thoughtTimerInterval = null;
            if (thoughtAccordion) {
              const spinner = thoughtAccordion.querySelector('.thought-spinner');
              if (spinner) spinner.remove();
              const badge = thoughtAccordion.querySelector('.thought-badge');
              if (badge) badge.innerHTML = 'Thought Process';
              
              thoughtAccordion.classList.add('collapsed');
            }
          }

          accumulatedContent += payload.content || '';
          assistantMarkdown.innerHTML = renderMarkdown(accumulatedContent);
          scrollToBottom();
        } else if (eventType === 'done') {
          if (payload.title) {
            dom.currentSessionTitle.innerText = payload.title;
            const currentSess = state.sessions.find((s) => s.id === state.currentSessionId);
            if (currentSess) {
              currentSess.title = payload.title;
              currentSess.updated_at = new Date().toISOString();
              currentSess.message_count += 2;
              renderSessionsList();
            }
          }
        } else if (eventType === 'error') {
          assistantMarkdown.innerHTML += `<div class="toast error" style="margin-top:10px;">${escapeHtml(payload.error)}</div>`;
        }
      }
    }
  } catch (err) {
    console.error('Chat streaming failed:', err);
    assistantMarkdown.innerHTML += `<div class="toast error" style="margin-top:10px;">Error: ${escapeHtml(err.message)}</div>`;
  } finally {
    if (thoughtTimerInterval) clearInterval(thoughtTimerInterval);
    setStreamingState(false);
    scrollToBottom();
  }
}

async function handleStopGeneration() {
  if (!state.isStreaming || !state.currentSessionId) return;
  try {
    await fetch('/api/chat/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: state.currentSessionId }),
    });
    setStreamingState(false);
    showToast('Generation stopped', 'info');
  } catch (err) {
    console.error('Failed to stop generation:', err);
  }
}

function setStreamingState(isStreaming) {
  state.isStreaming = isStreaming;
  if (isStreaming) {
    dom.sendBtn.classList.add('streaming');
    dom.sendIcon.classList.add('hidden');
    dom.stopIcon.classList.remove('hidden');
    dom.sendBtn.title = 'Stop Generating';
  } else {
    dom.sendBtn.classList.remove('streaming');
    dom.sendIcon.classList.remove('hidden');
    dom.stopIcon.classList.add('hidden');
    dom.sendBtn.title = 'Send Message';
  }
}

async function handleAttachmentUpload(files) {
  for (const file of files) {
    const formData = new FormData();
    formData.append('file', file);

    try {
      showToast(`Extracting ${file.name}...`, 'info', 2000);
      const res = await fetch('/api/attachments/extract', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Extraction failed');
      }

      const data = await res.json();
      state.stagedAttachments.push({
        name: data.name,
        content: data.content,
        size: data.size,
      });
      renderStagedAttachments();
      showToast(`Attached ${data.name}`, 'success');
    } catch (err) {
      console.error('Attachment upload failed:', err);
      showToast(`Failed to attach ${file.name}: ${err.message}`, 'error');
    }
  }
}

function renderStagedAttachments() {
  if (state.stagedAttachments.length === 0) {
    dom.attachmentPills.classList.add('hidden');
    dom.attachmentPills.innerHTML = '';
    return;
  }

  dom.attachmentPills.classList.remove('hidden');
  dom.attachmentPills.innerHTML = '';

  state.stagedAttachments.forEach((att, index) => {
    const chip = document.createElement('div');
    chip.className = 'attachment-chip';
    chip.innerHTML = `
      <span class="att-label">File:</span>
      <span>${escapeHtml(att.name)}</span>
      <span style="color:var(--text-dim);font-size:0.7rem;">(${formatBytes(att.size)})</span>
      <button class="remove-att-btn" title="Remove attachment" onclick="removeStagedAttachment(${index})">&times;</button>
    `;
    dom.attachmentPills.appendChild(chip);
  });
}

window.removeStagedAttachment = function (index) {
  state.stagedAttachments.splice(index, 1);
  renderStagedAttachments();
};

function clearStagedAttachments() {
  state.stagedAttachments = [];
  renderStagedAttachments();
}

async function loadKnowledgeBase() {
  try {
    const res = await fetch('/api/knowledge');
    const entries = await res.json();
    renderKnowledgeTable(entries);
  } catch (err) {
    console.error('Failed to load knowledge base:', err);
  }
}

function renderKnowledgeTable(entries, filterText = '') {
  dom.kbTableBody.innerHTML = '';

  const filtered = entries.filter(
    (e) =>
      e.filename.toLowerCase().includes(filterText.toLowerCase()) ||
      e.category.toLowerCase().includes(filterText.toLowerCase())
  );

  if (!filtered.length) {
    dom.kbTableBody.innerHTML = `
      <tr>
        <td colspan="7" class="empty-state-cell">No documents found. Upload files or import demo dataset above.</td>
      </tr>
    `;
    return;
  }

  filtered.forEach((entry) => {
    const tr = document.createElement('tr');

    const statusBadge = entry.chunk_count > 0
      ? `<span class="badge" style="background:rgba(16,185,129,0.15);color:var(--accent-emerald);">Indexed</span>`
      : `<span class="badge" style="background:rgba(245,158,11,0.15);color:var(--accent-amber);">Unindexed</span>`;

    tr.innerHTML = `
      <td class="doc-name-cell">
        <span class="cat-tag">[${entry.category === 'parts' ? 'PARTS' : entry.category === 'pdf' ? 'PDF' : 'TEXT'}]</span>
        <div>
          <div>${escapeHtml(entry.filename)}</div>
          <div style="font-size:0.72rem;color:var(--text-dim);">${escapeHtml(entry.path)}</div>
        </div>
      </td>
      <td>
        <select class="category-select" onchange="updateKbCategory('${escapeHtml(entry.path)}', this.value)">
          <option value="parts" ${entry.category === 'parts' ? 'selected' : ''}>Parts (SAP)</option>
          <option value="pdf" ${entry.category === 'pdf' ? 'selected' : ''}>PDF (Contract)</option>
          <option value="txt" ${entry.category === 'txt' ? 'selected' : ''}>Text Document</option>
        </select>
      </td>
      <td>${statusBadge}</td>
      <td><span style="font-family:var(--font-mono);font-size:0.85rem;">${entry.chunk_count}</span></td>
      <td>${formatBytes(entry.size)}</td>
      <td style="font-size:0.8rem;color:var(--text-dim);">${timeAgo(entry.indexed_at) || 'Pending sync'}</td>
      <td>
        <button class="action-icon-btn" title="Remove file" onclick="deleteKbEntry('${escapeHtml(entry.path)}')">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
        </button>
      </td>
    `;
    dom.kbTableBody.appendChild(tr);
  });
}

window.updateKbCategory = async function (path, newCat) {
  try {
    await fetch('/api/knowledge/entry', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, category: newCat }),
    });
    showToast(`Updated category to ${newCat}`, 'success');
  } catch (err) {
    showToast('Failed to update category', 'error');
  }
};

window.deleteKbEntry = async function (path) {
  if (!confirm(`Remove ${path.split('/').pop()} from knowledge base?`)) return;
  try {
    await fetch('/api/knowledge/entry', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    showToast('Removed document', 'info');
    await loadKnowledgeBase();
    await checkStatus();
  } catch (err) {
    showToast('Failed to remove document', 'error');
  }
};

async function handleKbUpload(files) {
  for (const file of files) {
    const formData = new FormData();
    formData.append('file', file);
    try {
      showToast(`Uploading ${file.name}...`, 'info');
      const res = await fetch('/api/knowledge/upload', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }
      showToast(`Uploaded ${file.name}. Click Rebuild Index to sync!`, 'success');
    } catch (err) {
      showToast(`Error: ${err.message}`, 'error');
    }
  }
  await loadKnowledgeBase();
  await checkStatus();
}

async function handleSyncKnowledgeIndex() {
  dom.syncBtnText.innerText = 'Syncing...';
  dom.syncIcon.style.animation = 'spin 1s linear infinite';
  dom.kbSyncBtn.disabled = true;

  try {
    const res = await fetch('/api/knowledge/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force: false }),
    });
    const data = await res.json();

    dom.syncReportSummary.innerText = data.summary;
    dom.syncReportSummary.classList.remove('hidden');

    showToast(`Sync complete! ${data.summary}`, 'success', 5000);
    await loadKnowledgeBase();
    await checkStatus();
  } catch (err) {
    console.error('Sync failed:', err);
    showToast('Knowledge base sync failed', 'error');
  } finally {
    dom.syncBtnText.innerText = 'Rebuild & Sync Index';
    dom.syncIcon.style.animation = '';
    dom.kbSyncBtn.disabled = false;
  }
}

async function handleImportProcurement() {
  try {
    showToast('Importing SAP datasets & contracts...', 'info');
    const res = await fetch('/api/procurement/import', { method: 'POST' });
    const data = await res.json();
    showToast(`Imported ${data.imported.length} files! Rebuilding index...`, 'success', 4000);
    dom.demoDataBanner.classList.add('hidden');
    await loadKnowledgeBase();
    await checkStatus();
  } catch (err) {
    showToast('Failed to import procurement data', 'error');
  }
}

function openChunkModal(chunk) {
  dom.modalChunkCategory.innerText = (chunk.category || 'RAG').toUpperCase();
  dom.modalChunkSource.innerText = chunk.source || 'Retrieved Context';
  dom.modalChunkText.innerText = chunk.text || '';
  dom.chunkModal.classList.remove('hidden');
}

function closeChunkModal() {
  dom.chunkModal.classList.add('hidden');
}

function setupEventListeners() {
  
  dom.tabChat.addEventListener('click', () => switchTab('chat'));
  dom.tabKnowledge.addEventListener('click', () => switchTab('knowledge'));

  
  dom.toggleSidebarBtn.addEventListener('click', () => {
    dom.appSidebar.classList.toggle('collapsed');
  });

  
  dom.newChatBtn.addEventListener('click', createNewSession);

  
  dom.sessionSearchInput.addEventListener('input', (e) => {
    renderSessionsList(e.target.value);
  });

  
  dom.currentSessionTitle.addEventListener('blur', (e) => {
    updateSessionTitle(e.target.innerText.trim() || 'New chat');
  });
  dom.currentSessionTitle.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      dom.currentSessionTitle.blur();
    }
  });

  
  dom.clearChatBtn.addEventListener('click', async () => {
    if (!state.currentSessionId) return;
    if (!confirm('Clear all messages in this conversation?')) return;
    try {
      await fetch(`/api/sessions/${state.currentSessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New chat' }),
      });
      selectSession(state.currentSessionId);
    } catch (err) {
      showToast('Failed to clear chat', 'error');
    }
  });

  
  dom.modeDeepthink.addEventListener('change', updateSessionModes);
  dom.modeTokenless.addEventListener('change', updateSessionModes);

  
  dom.modelSelect.addEventListener('change', async (e) => {
    const selected = e.target.value;
    try {
      await fetch('/api/models/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: selected }),
      });
      state.currentModel = selected;
      showToast(`Model set to ${selected}`, 'info');
    } catch (err) {
      showToast('Failed to change model', 'error');
    }
  });

  
  dom.promptInput.addEventListener('input', () => {
    dom.promptInput.style.height = 'auto';
    dom.promptInput.style.height = Math.min(dom.promptInput.scrollHeight, 200) + 'px';
  });

  dom.promptInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (state.isStreaming) {
        handleStopGeneration();
      } else {
        handleSendMessage();
      }
    }
  });

  
  dom.sendBtn.addEventListener('click', () => {
    if (state.isStreaming) {
      handleStopGeneration();
    } else {
      handleSendMessage();
    }
  });

  
  dom.attachFileBtn.addEventListener('click', () => dom.fileInput.click());
  dom.fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
      handleAttachmentUpload(Array.from(e.target.files));
      dom.fileInput.value = '';
    }
  });

  
  window.addEventListener('dragover', (e) => {
    e.preventDefault();
    dom.dropOverlay.classList.add('active');
  });

  dom.dropOverlay.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dom.dropOverlay.classList.remove('active');
  });

  dom.dropOverlay.addEventListener('drop', (e) => {
    e.preventDefault();
    dom.dropOverlay.classList.remove('active');
    if (e.dataTransfer.files.length) {
      if (state.activeTab === 'knowledge') {
        handleKbUpload(Array.from(e.dataTransfer.files));
      } else {
        handleAttachmentUpload(Array.from(e.dataTransfer.files));
      }
    }
  });

  
  document.querySelectorAll('.suggestion-card').forEach((card) => {
    card.addEventListener('click', () => {
      const promptText = card.dataset.prompt;
      if (promptText) {
        dom.promptInput.value = promptText;
        handleSendMessage();
      }
    });
  });

  
  dom.quickImportBtn?.addEventListener('click', handleImportProcurement);
  dom.kbImportProcurementBtn.addEventListener('click', handleImportProcurement);

  
  dom.kbUploadBtn.addEventListener('click', () => dom.kbFileInput.click());
  dom.kbFileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
      handleKbUpload(Array.from(e.target.files));
      dom.kbFileInput.value = '';
    }
  });
  dom.kbSyncBtn.addEventListener('click', handleSyncKnowledgeIndex);
  dom.kbSearchInput.addEventListener('input', (e) => {
    loadKnowledgeBase().then(() => {
      const rows = Array.from(dom.kbTableBody.querySelectorAll('tr'));
      const q = e.target.value.toLowerCase();
      rows.forEach((r) => {
        const text = r.innerText.toLowerCase();
        r.style.display = text.includes(q) ? '' : 'none';
      });
    });
  });

  
  dom.modalCloseBtn.addEventListener('click', closeChunkModal);
  dom.chunkModal.addEventListener('click', (e) => {
    if (e.target === dom.chunkModal) closeChunkModal();
  });

  
  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'n') {
      e.preventDefault();
      createNewSession();
    }
  });
}

function switchTab(tabName) {
  state.activeTab = tabName;
  if (tabName === 'chat') {
    dom.tabChat.classList.add('active');
    dom.tabKnowledge.classList.remove('active');
    dom.chatView.classList.add('active');
    dom.knowledgeView.classList.remove('active');
  } else {
    dom.tabKnowledge.classList.add('active');
    dom.tabChat.classList.remove('active');
    dom.knowledgeView.classList.add('active');
    dom.chatView.classList.remove('active');
    loadKnowledgeBase();
  }
}

document.addEventListener('DOMContentLoaded', initApp);
