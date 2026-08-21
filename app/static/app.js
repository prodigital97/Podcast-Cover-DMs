/**
 * Mobile-First Podcast Cover DM Copilot & CRM Dashboard
 */

let state = {
  leads: [],
  activeLeadId: null,
  activeFilter: 'all',
  searchQuery: '',
  composerDir: 'them',
  mobileActivePane: 'messages', // 'messages' or 'drafts'
  currentView: 'inbox', // 'inbox', 'chat', 'crm'
};

const TONE_LABELS = {
  warm: '1️⃣ Warm Option',
  direct: '2️⃣ Direct Option',
  low_pressure: '3️⃣ Low Pressure Option',
};

// --- DOM Elements ---
const el = {
  app: document.getElementById('app'),
  leadsList: document.getElementById('leads-list'),
  searchLeads: document.getElementById('search-leads'),
  filterTabs: document.querySelectorAll('.pill-tab'),
  btnBackToInbox: document.getElementById('btn-back-to-inbox'),
  headerHandle: document.getElementById('header-handle'),
  headerStageBadge: document.getElementById('header-stage-badge'),
  btnEditLeadHeader: document.getElementById('btn-edit-lead-header'),
  btnDeleteLeadHeader: document.getElementById('btn-delete-lead-header'),
  bannerPodcast: document.getElementById('banner-podcast'),
  bannerAudience: document.getElementById('banner-audience'),
  bannerScore: document.getElementById('banner-score'),
  conversionProgressBar: document.getElementById('conversion-progress-bar'),
  bannerRationale: document.getElementById('banner-rationale'),
  bannerSignals: document.getElementById('banner-signals'),
  tabShowMessages: document.getElementById('tab-show-messages'),
  tabShowDrafts: document.getElementById('tab-show-drafts'),
  draftCountBadge: document.getElementById('draft-count-badge'),
  chatDualContainer: document.querySelector('.chat-dual-container'),
  messagesContainer: document.getElementById('messages-container'),
  messageTextInput: document.getElementById('message-text-input'),
  btnSendMessage: document.getElementById('btn-send-message'),
  modeInbound: document.getElementById('mode-inbound'),
  modeOutbound: document.getElementById('mode-outbound'),
  draftsContainer: document.getElementById('drafts-container'),
  draftsLoading: document.getElementById('drafts-loading'),
  btnRedraftCard: document.getElementById('btn-redraft-card'),
  navBtnChats: document.getElementById('nav-btn-chats'),
  navBtnCrm: document.getElementById('nav-btn-crm'),
  crmTableBody: document.getElementById('crm-table-body'),
  leadModal: document.getElementById('lead-modal'),
  leadForm: document.getElementById('lead-form'),
  formIgsid: document.getElementById('form-igsid'),
  formHandle: document.getElementById('form-handle'),
  formPodcast: document.getElementById('form-podcast'),
  formAudience: document.getElementById('form-audience'),
  formBio: document.getElementById('form-bio'),
  formInitialMsg: document.getElementById('form-initial-msg'),
  initialMsgGroup: document.getElementById('initial-msg-group'),
  formNotes: document.getElementById('form-notes'),
  modalTitle: document.getElementById('modal-title'),
  toast: document.getElementById('toast'),
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  loadLeads();
  setMobileChatPane('messages');
});

function initEventListeners() {
  // Mobile Back button
  el.btnBackToInbox.addEventListener('click', () => {
    switchView('inbox');
  });

  // Search & Filter Tabs
  el.searchLeads.addEventListener('input', (e) => {
    state.searchQuery = e.target.value.toLowerCase();
    renderLeadsList();
  });

  el.filterTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      el.filterTabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      state.activeFilter = tab.dataset.filter;
      renderLeadsList();
    });
  });

  // Mobile Chat vs Drafts Toggle
  if (el.tabShowMessages && el.tabShowDrafts) {
    el.tabShowMessages.addEventListener('click', () => setMobileChatPane('messages'));
    el.tabShowDrafts.addEventListener('click', () => setMobileChatPane('drafts'));
  }

  // Composer Direction Toggle
  el.modeInbound.addEventListener('click', () => {
    state.composerDir = 'them';
    el.modeInbound.classList.add('active');
    el.modeOutbound.classList.remove('active');
    el.messageTextInput.placeholder = 'Paste their incoming DM here...';
  });

  el.modeOutbound.addEventListener('click', () => {
    state.composerDir = 'pronoy';
    el.modeOutbound.classList.add('active');
    el.modeInbound.classList.remove('active');
    el.messageTextInput.placeholder = 'Type reply sent by you...';
  });

  // Send Message button & Enter key
  el.btnSendMessage.addEventListener('click', handleSendMessage);
  el.messageTextInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  // Redraft Button
  el.btnRedraftCard.addEventListener('click', handleRedraft);

  // Edit & Delete Active Lead
  el.btnEditLeadHeader.addEventListener('click', openEditLeadModal);
  el.btnDeleteLeadHeader.addEventListener('click', handleDeleteActiveLead);

  // Bottom Navigation (Mobile)
  if (el.navBtnChats) {
    el.navBtnChats.addEventListener('click', () => {
      el.navBtnChats.classList.add('active');
      el.navBtnCrm.classList.remove('active');
      switchView('inbox');
    });
  }

  if (el.navBtnCrm) {
    el.navBtnCrm.addEventListener('click', () => {
      el.navBtnCrm.classList.add('active');
      el.navBtnChats.classList.remove('active');
      switchView('crm');
      renderCrmTable();
    });
  }

  // Lead Form Submit
  el.leadForm.addEventListener('submit', handleLeadFormSubmit);
}

// --- View Switching ---

function switchView(viewName) {
  state.currentView = viewName;
  el.app.className = `mobile-view-${viewName}`;
  window.scrollTo(0, 0);
}

function setMobileChatPane(paneName) {
  state.mobileActivePane = paneName;
  if (!el.chatDualContainer) return;

  if (paneName === 'drafts') {
    el.chatDualContainer.classList.add('show-drafts');
    el.chatDualContainer.classList.remove('show-messages');
    if (el.tabShowDrafts) el.tabShowDrafts.classList.add('active');
    if (el.tabShowMessages) el.tabShowMessages.classList.remove('active');
  } else {
    el.chatDualContainer.classList.add('show-messages');
    el.chatDualContainer.classList.remove('show-drafts');
    if (el.tabShowMessages) el.tabShowMessages.classList.add('active');
    if (el.tabShowDrafts) el.tabShowDrafts.classList.remove('active');
  }
}

// --- API & State Handling ---

async function loadLeads(selectId = null) {
  try {
    const res = await fetch('/api/leads');
    const data = await res.json();
    state.leads = data.leads || [];
    renderLeadsList();

    if (selectId) {
      selectLead(selectId);
    } else if (window.innerWidth >= 769 && state.leads.length > 0 && !state.activeLeadId) {
      selectLead(state.leads[0].igsid);
    }
  } catch (err) {
    console.error('Failed to load leads:', err);
    showToast('Failed to load chats');
  }
}

async function selectLead(igsid) {
  state.activeLeadId = igsid;
  renderLeadsList();
  switchView('chat');
  setMobileChatPane('messages');

  try {
    const res = await fetch(`/api/leads/${igsid}`);
    if (!res.ok) throw new Error('Lead not found');
    const data = await res.json();
    renderActiveChat(data.lead, data.messages, data.open_approval);
  } catch (err) {
    console.error('Failed to load lead details:', err);
    showToast('Failed to open chat');
  }
}

async function handleSendMessage() {
  const text = el.messageTextInput.value.trim();
  if (!text || !state.activeLeadId) return;

  el.messageTextInput.value = '';
  const dir = state.composerDir;

  if (dir === 'them') {
    el.draftsLoading.classList.remove('hidden');
    el.draftsContainer.innerHTML = '';
    // Automatically focus on drafts tab on mobile if an inbound message arrives!
    if (window.innerWidth < 769) {
      setMobileChatPane('drafts');
    }
  }

  try {
    const res = await fetch(`/api/leads/${state.activeLeadId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, direction: dir }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Message failed');

    renderActiveChat(
      data.lead,
      data.messages,
      data.drafts ? { drafts: data.drafts.drafts, read: data.drafts.read, stage: data.drafts.stage, id: data.drafts.approval_id } : null
    );
    loadLeads();
  } catch (err) {
    console.error('Message error:', err);
    showToast(`Error: ${err.message}`);
  } finally {
    el.draftsLoading.classList.add('hidden');
  }
}

async function handleRedraft() {
  if (!state.activeLeadId) return;
  el.draftsLoading.classList.remove('hidden');
  el.draftsContainer.innerHTML = '';

  try {
    const res = await fetch(`/api/leads/${state.activeLeadId}/redraft`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error('Redrafting failed');
    renderDrafts(data.drafts.drafts, data.drafts.approval_id);
    renderConversionBanner(data.lead);
    showToast('Generated 3 fresh angles!');
  } catch (err) {
    showToast('Redrafting failed');
  } finally {
    el.draftsLoading.classList.add('hidden');
  }
}

async function handleApproveDraft(approvalId, text) {
  if (!state.activeLeadId) return;
  try {
    const res = await fetch(`/api/leads/${state.activeLeadId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approval_id: approvalId, text }),
    });
    const data = await res.json();
    renderActiveChat(data.lead, data.messages, null);
    showToast('Marked as sent!');
    setMobileChatPane('messages');
    loadLeads();
  } catch (err) {
    showToast('Failed to mark sent');
  }
}

async function handleDeleteActiveLead() {
  if (!state.activeLeadId) return;
  if (!confirm('Are you sure you want to delete this conversation?')) return;

  try {
    const res = await fetch(`/api/leads/${state.activeLeadId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Delete failed');
    showToast('Conversation deleted');
    state.activeLeadId = null;
    switchView('inbox');
    loadLeads();
  } catch (err) {
    showToast('Failed to delete');
  }
}

async function handleLeadFormSubmit(e) {
  e.preventDefault();
  const igsid = el.formIgsid.value;
  const isEdit = Boolean(igsid);

  const payload = {
    handle: el.formHandle.value.trim(),
    podcast_name: el.formPodcast.value.trim() || null,
    audience_size: el.formAudience.value.trim() || null,
    bio: el.formBio.value.trim() || null,
    notes: el.formNotes.value.trim() || '',
  };

  if (!isEdit) {
    payload.initial_message = el.formInitialMsg.value.trim() || null;
  }

  try {
    const url = isEdit ? `/api/leads/${igsid}` : '/api/leads';
    const method = isEdit ? 'PUT' : 'POST';
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Save failed');

    closeLeadModal();
    showToast(isEdit ? 'Lead updated!' : 'Chat created!');
    const targetId = isEdit ? igsid : data.igsid;
    loadLeads(targetId);
    selectLead(targetId);
  } catch (err) {
    showToast(`Error: ${err.message}`);
  }
}

// --- Render Functions ---

function renderLeadsList() {
  let filtered = state.leads.filter((l) => {
    const matchSearch =
      !state.searchQuery ||
      (l.handle && l.handle.toLowerCase().includes(state.searchQuery)) ||
      (l.podcast_name && l.podcast_name.toLowerCase().includes(state.searchQuery)) ||
      (l.bio && l.bio.toLowerCase().includes(state.searchQuery));

    let matchFilter = true;
    if (state.activeFilter === 'hot') {
      matchFilter = (l.conversion_probability || 50) >= 70;
    } else if (state.activeFilter === 'green_light') {
      matchFilter = l.status === 'green_light';
    } else if (state.activeFilter === 'building') {
      matchFilter = l.status === 'building' || l.status === 'first_contact';
    }

    return matchSearch && matchFilter;
  });

  if (filtered.length === 0) {
    el.leadsList.innerHTML = '<div style="padding: 30px 14px; text-align: center; color: var(--text-dim); font-size: 0.86rem;">No conversations found.<br><br>Tap <b>+ New Chat</b> to create one!</div>';
    return;
  }

  el.leadsList.innerHTML = filtered
    .map((lead) => {
      const activeClass = lead.igsid === state.activeLeadId ? 'active' : '';
      const prob = lead.conversion_probability || 50;
      const lastSnippet = lead.last_message ? lead.last_message.text : 'No messages yet';

      return `
        <div class="lead-card-item ${activeClass}" onclick="selectLead('${lead.igsid}')">
          <div class="lead-card-top">
            <span class="lead-card-handle">${escapeHtml(lead.handle || lead.igsid)}</span>
            <span class="lead-card-score">🔥 ${prob}%</span>
          </div>
          <div class="lead-card-podcast">${escapeHtml(lead.podcast_name || lead.bio || 'New Lead')}</div>
          <div class="lead-card-snippet">${escapeHtml(lastSnippet)}</div>
        </div>
      `;
    })
    .join('');
}

function renderActiveChat(lead, messages, openApproval) {
  // Header
  const handle = lead.handle || lead.igsid;
  el.headerHandle.textContent = handle;
  el.headerStageBadge.textContent = lead.status || 'first_contact';

  // Banner
  renderConversionBanner(lead);

  // Messages
  renderMessages(messages || []);

  // AI Drafts
  if (openApproval && openApproval.drafts && openApproval.drafts.length > 0) {
    renderDrafts(openApproval.drafts, openApproval.id);
    if (el.draftCountBadge) el.draftCountBadge.textContent = openApproval.drafts.length;
  } else {
    el.draftsContainer.innerHTML = '<div style="padding: 30px 14px; text-align: center; color: var(--text-dim); font-size: 0.85rem;">Paste an incoming DM to generate 3 strategic options with Gemini 3.7 Flash.</div>';
    if (el.draftCountBadge) el.draftCountBadge.textContent = '0';
  }
}

function renderConversionBanner(lead) {
  const prob = lead.conversion_probability || 50;
  el.bannerScore.textContent = `${prob}%`;
  el.conversionProgressBar.style.width = `${prob}%`;
  el.bannerPodcast.textContent = lead.podcast_name || 'Podcast Show';
  el.bannerAudience.textContent = lead.audience_size ? `${lead.audience_size} followers` : 'Audience unset';
  el.bannerRationale.textContent = lead.conversion_rationale || lead.needs || 'Analyzing conversation stage...';

  let signals = [];
  try {
    signals = typeof lead.buying_signals === 'string' ? JSON.parse(lead.buying_signals) : lead.buying_signals || [];
  } catch (e) {
    signals = [];
  }

  if (signals.length > 0) {
    el.bannerSignals.innerHTML = signals.map((s) => `<span class="signal-pill">✓ ${escapeHtml(s)}</span>`).join('');
  } else {
    el.bannerSignals.innerHTML = `<span class="signal-pill">Stage: ${lead.status || 'first_contact'}</span>`;
  }
}

function renderMessages(messages) {
  if (messages.length === 0) {
    el.messagesContainer.innerHTML = '<div style="margin: auto; color: var(--text-dim); font-size: 0.88rem; text-align: center; padding: 20px;">No messages yet.<br>Paste their incoming DM below!</div>';
    return;
  }

  el.messagesContainer.innerHTML = messages
    .map((m) => {
      const isThem = m.direction === 'them';
      const bubbleClass = isThem ? 'msg-inbound' : 'msg-outbound';
      const timeStr = m.created_at ? new Date(m.created_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

      return `
        <div class="msg-bubble ${bubbleClass}">
          <div class="msg-text">${escapeHtml(m.text)}</div>
          <div class="msg-time">${timeStr}</div>
        </div>
      `;
    })
    .join('');

  el.messagesContainer.scrollTop = el.messagesContainer.scrollHeight;
}

function renderDrafts(drafts, approvalId) {
  if (!drafts || drafts.length === 0) {
    el.draftsContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-dim);">No drafts available.</div>';
    return;
  }

  el.draftsContainer.innerHTML = drafts
    .map((draft, idx) => {
      const tone = draft.tone || 'warm';
      const title = TONE_LABELS[tone] || `Option ${idx + 1}`;
      const toneClass = `tone-${tone}`;

      return `
        <div class="draft-card">
          <div class="draft-card-header">
            <span class="draft-tone-title ${toneClass}">${title}</span>
          </div>
          <div class="draft-text-content">${escapeHtml(draft.text)}</div>
          <div class="draft-button-row">
            <button class="btn-copy-draft" onclick="copyDraftText(this, \`${escapeJsString(draft.text)}\`)">
              📋 1-Tap Copy
            </button>
            <button class="btn btn-primary btn-mark-sent" onclick="handleApproveDraft('${approvalId}', \`${escapeJsString(draft.text)}\`)">
              ✅ Mark Sent
            </button>
          </div>
        </div>
      `;
    })
    .join('');
}

function renderCrmTable() {
  el.crmTableBody.innerHTML = state.leads
    .map((l) => {
      const prob = l.conversion_probability || 50;
      const lastDate = l.updated_at ? new Date(l.updated_at * 1000).toLocaleDateString() : '-';
      return `
        <tr onclick="selectLead('${l.igsid}');" style="cursor: pointer;">
          <td><b>${escapeHtml(l.handle || l.igsid)}</b></td>
          <td>${escapeHtml(l.podcast_name || '-')}</td>
          <td><span class="badge">${escapeHtml(l.status || 'first_contact')}</span></td>
          <td><b>🔥 ${prob}%</b></td>
          <td>${escapeHtml(l.audience_size || '-')}</td>
          <td>${escapeHtml(l.price || 'not discussed')}</td>
          <td>${l.message_count || 0}</td>
          <td>${lastDate}</td>
        </tr>
      `;
    })
    .join('');
}

// --- Modals & Utility ---

function openNewLeadModal() {
  el.formIgsid.value = '';
  el.formHandle.value = '';
  el.formPodcast.value = '';
  el.formAudience.value = '';
  el.formBio.value = '';
  el.formInitialMsg.value = '';
  el.formNotes.value = '';
  el.modalTitle.textContent = 'New Lead Conversation';
  el.initialMsgGroup.classList.remove('hidden');
  el.leadModal.classList.remove('hidden');
}

function openEditLeadModal() {
  const lead = state.leads.find((l) => l.igsid === state.activeLeadId);
  if (!lead) return;

  el.formIgsid.value = lead.igsid;
  el.formHandle.value = lead.handle || '';
  el.formPodcast.value = lead.podcast_name || '';
  el.formAudience.value = lead.audience_size || '';
  el.formBio.value = lead.bio || '';
  el.formNotes.value = lead.notes || '';
  el.modalTitle.textContent = `Edit Lead ${lead.handle || ''}`;
  el.initialMsgGroup.classList.add('hidden');
  el.leadModal.classList.remove('hidden');
}

function closeLeadModal() {
  el.leadModal.classList.add('hidden');
}

function downloadCsv() {
  window.location.href = '/api/export/csv';
}

function copyDraftText(button, text) {
  navigator.clipboard.writeText(text).then(() => {
    const orig = button.innerHTML;
    button.innerHTML = '✓ Copied to Clipboard!';
    button.style.backgroundColor = 'var(--emerald-accent)';
    button.style.color = '#ffffff';
    showToast('Copied! Ready to paste in Instagram');
    setTimeout(() => {
      button.innerHTML = orig;
      button.style.backgroundColor = '';
      button.style.color = '';
    }, 2000);
  });
}

function showToast(msg) {
  el.toast.textContent = msg;
  el.toast.classList.remove('hidden');
  setTimeout(() => {
    el.toast.classList.add('hidden');
  }, 2400);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeJsString(str) {
  if (!str) return '';
  return String(str).replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$');
}
