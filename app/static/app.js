/**
 * Podcast Cover DM Copilot & CRM Dashboard Frontend
 */

let state = {
  leads: [],
  activeLeadId: null,
  activeFilter: 'all',
  searchQuery: '',
  composerDir: 'them',
};

const TONE_LABELS = {
  warm: '1️⃣ Warm Option',
  direct: '2️⃣ Direct Option',
  low_pressure: '3️⃣ Low Pressure Option',
};

// --- DOM Elements ---
const elements = {
  leadsList: document.getElementById('leads-list'),
  searchLeads: document.getElementById('search-leads'),
  filterTabs: document.querySelectorAll('.filter-tab'),
  noLeadSelected: document.getElementById('no-lead-selected'),
  leadActiveView: document.getElementById('lead-active-view'),
  activeLeadAvatar: document.getElementById('active-lead-avatar'),
  activeLeadHandle: document.getElementById('active-lead-handle'),
  activeLeadStageBadge: document.getElementById('active-lead-stage-badge'),
  activeLeadPodcast: document.getElementById('active-lead-podcast'),
  activeLeadAudience: document.getElementById('active-lead-audience'),
  btnEditLead: document.getElementById('btn-edit-lead'),
  btnDeleteLead: document.getElementById('btn-delete-lead'),
  conversionScore: document.getElementById('conversion-score'),
  conversionTag: document.getElementById('conversion-tag'),
  conversionBar: document.getElementById('conversion-bar'),
  conversionRationale: document.getElementById('conversion-rationale'),
  buyingSignalsList: document.getElementById('buying-signals-list'),
  messagesContainer: document.getElementById('messages-container'),
  messageTextInput: document.getElementById('message-text-input'),
  btnSendMessage: document.getElementById('btn-send-message'),
  modeInbound: document.getElementById('mode-inbound'),
  modeOutbound: document.getElementById('mode-outbound'),
  draftsContainer: document.getElementById('drafts-container'),
  draftsLoading: document.getElementById('drafts-loading'),
  btnRedraftCard: document.getElementById('btn-redraft-card'),
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
  crmModal: document.getElementById('crm-modal'),
  crmTableBody: document.getElementById('crm-table-body'),
  btnExportCsv: document.getElementById('btn-export-csv'),
  btnViewCrm: document.getElementById('btn-view-crm'),
  btnNewLead: document.getElementById('btn-new-lead'),
  mobileMenuBtn: document.getElementById('mobile-menu-btn'),
  sidebar: document.getElementById('sidebar'),
  toast: document.getElementById('toast'),
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  loadLeads();
});

function initEventListeners() {
  // Search and Filters
  elements.searchLeads.addEventListener('input', (e) => {
    state.searchQuery = e.target.value.toLowerCase();
    renderLeadsList();
  });

  elements.filterTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      elements.filterTabs.forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      state.activeFilter = tab.dataset.filter;
      renderLeadsList();
    });
  });

  // Message Composer Switch
  elements.modeInbound.addEventListener('click', () => {
    state.composerDir = 'them';
    elements.modeInbound.classList.add('active');
    elements.modeOutbound.classList.remove('active');
    elements.messageTextInput.placeholder = 'Paste incoming DM from them (generates 3 drafts)...';
  });

  elements.modeOutbound.addEventListener('click', () => {
    state.composerDir = 'pronoy';
    elements.modeOutbound.classList.add('active');
    elements.modeInbound.classList.remove('active');
    elements.messageTextInput.placeholder = 'Type or paste reply sent by you...';
  });

  // Send Message Button & Enter Key
  elements.btnSendMessage.addEventListener('click', handleSendMessage);
  elements.messageTextInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  // Redraft Button
  elements.btnRedraftCard.addEventListener('click', handleRedraft);

  // New Lead Button
  elements.btnNewLead.addEventListener('click', openNewLeadModal);

  // Edit & Delete Lead
  elements.btnEditLead.addEventListener('click', openEditLeadModal);
  elements.btnDeleteLead.addEventListener('click', handleDeleteActiveLead);

  // CRM Table & Export CSV
  elements.btnViewCrm.addEventListener('click', openCrmModal);
  elements.btnExportCsv.addEventListener('click', downloadCsv);

  // Lead Form Submit
  elements.leadForm.addEventListener('submit', handleLeadFormSubmit);

  // Mobile menu button
  if (elements.mobileMenuBtn) {
    elements.mobileMenuBtn.addEventListener('click', () => {
      elements.sidebar.classList.toggle('open');
    });
  }
}

// --- API Calls ---

async function loadLeads(selectId = null) {
  try {
    const res = await fetch('/api/leads');
    const data = await res.json();
    state.leads = data.leads || [];
    renderLeadsList();

    if (selectId) {
      selectLead(selectId);
    } else if (state.leads.length > 0 && !state.activeLeadId) {
      selectLead(state.leads[0].igsid);
    }
  } catch (err) {
    console.error('Failed to load leads:', err);
    showToast('Failed to load leads');
  }
}

async function selectLead(igsid) {
  state.activeLeadId = igsid;
  if (elements.sidebar) elements.sidebar.classList.remove('open');
  renderLeadsList();

  elements.noLeadSelected.classList.add('hidden');
  elements.leadActiveView.classList.remove('hidden');

  try {
    const res = await fetch(`/api/leads/${igsid}`);
    if (!res.ok) throw new Error('Lead not found');
    const data = await res.json();
    renderActiveLead(data.lead, data.messages, data.open_approval);
  } catch (err) {
    console.error('Failed to fetch lead details:', err);
    showToast('Failed to load lead details');
  }
}

async function handleSendMessage() {
  const text = elements.messageTextInput.value.trim();
  if (!text || !state.activeLeadId) return;

  elements.messageTextInput.value = '';
  const dir = state.composerDir;

  // Show AI loader if inbound
  if (dir === 'them') {
    elements.draftsLoading.classList.remove('hidden');
    elements.draftsContainer.innerHTML = '';
  }

  try {
    const res = await fetch(`/api/leads/${state.activeLeadId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, direction: dir }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to send message');

    renderActiveLead(data.lead, data.messages, data.drafts ? { drafts: data.drafts.drafts, read: data.drafts.read, stage: data.drafts.stage, id: data.drafts.approval_id } : null);
    loadLeads(); // refresh sidebar list snippet
  } catch (err) {
    console.error('Failed to send message:', err);
    showToast(`Error: ${err.message}`);
  } finally {
    elements.draftsLoading.classList.add('hidden');
  }
}

async function handleRedraft() {
  if (!state.activeLeadId) return;
  elements.draftsLoading.classList.remove('hidden');
  elements.draftsContainer.innerHTML = '';

  try {
    const res = await fetch(`/api/leads/${state.activeLeadId}/redraft`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok) throw new Error('Redrafting failed');
    renderDrafts(data.drafts.drafts, data.drafts.approval_id);
    renderConversion(data.lead);
  } catch (err) {
    console.error('Redraft failed:', err);
    showToast('Redrafting failed');
  } finally {
    elements.draftsLoading.classList.add('hidden');
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
    renderActiveLead(data.lead, data.messages, null);
    showToast('Reply marked as sent!');
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
    showToast('Lead deleted');
    state.activeLeadId = null;
    elements.leadActiveView.classList.add('hidden');
    elements.noLeadSelected.classList.remove('hidden');
    loadLeads();
  } catch (err) {
    showToast('Failed to delete lead');
  }
}

async function handleLeadFormSubmit(e) {
  e.preventDefault();
  const igsid = elements.formIgsid.value;
  const isEdit = Boolean(igsid);

  const payload = {
    handle: elements.formHandle.value.trim(),
    podcast_name: elements.formPodcast.value.trim() || null,
    audience_size: elements.formAudience.value.trim() || null,
    bio: elements.formBio.value.trim() || null,
    notes: elements.formNotes.value.trim() || '',
  };

  if (!isEdit) {
    payload.initial_message = elements.formInitialMsg.value.trim() || null;
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
    showToast(isEdit ? 'Lead updated!' : 'Lead created!');
    const targetId = isEdit ? igsid : data.igsid;
    loadLeads(targetId);
  } catch (err) {
    showToast(`Error: ${err.message}`);
  }
}

// --- Render Functions ---

function renderLeadsList() {
  let filtered = state.leads.filter((l) => {
    // Search query
    const matchSearch =
      !state.searchQuery ||
      (l.handle && l.handle.toLowerCase().includes(state.searchQuery)) ||
      (l.podcast_name && l.podcast_name.toLowerCase().includes(state.searchQuery)) ||
      (l.bio && l.bio.toLowerCase().includes(state.searchQuery));

    // Filter tab
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
    elements.leadsList.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 0.8rem;">No conversations found</div>';
    return;
  }

  elements.leadsList.innerHTML = filtered
    .map((lead) => {
      const activeClass = lead.igsid === state.activeLeadId ? 'active' : '';
      const prob = lead.conversion_probability || 50;
      let scoreClass = '';
      if (prob >= 75) scoreClass = 'score-hot';
      if (lead.status === 'active_client') scoreClass = 'score-won';

      const lastSnippet = lead.last_message ? lead.last_message.text : 'No messages yet';

      return `
        <div class="lead-item ${activeClass}" onclick="selectLead('${lead.igsid}')">
          <div class="lead-item-top">
            <span class="lead-item-handle">${escapeHtml(lead.handle || lead.igsid)}</span>
            <span class="lead-item-score ${scoreClass}">🔥 ${prob}%</span>
          </div>
          <div class="lead-item-podcast">${escapeHtml(lead.podcast_name || lead.bio || 'New Lead')}</div>
          <div class="lead-item-snippet">${escapeHtml(lastSnippet)}</div>
        </div>
      `;
    })
    .join('');
}

function renderActiveLead(lead, messages, openApproval) {
  // Header
  const handle = lead.handle || lead.igsid;
  elements.activeLeadHandle.textContent = handle;
  elements.activeLeadAvatar.textContent = handle.replace('@', '').charAt(0).toUpperCase() || '@';
  elements.activeLeadStageBadge.textContent = lead.status || 'first_contact';
  elements.activeLeadPodcast.textContent = lead.podcast_name || 'Show name unset';
  elements.activeLeadAudience.textContent = lead.audience_size ? `${lead.audience_size} followers` : 'Audience unset';

  // Conversion Card
  renderConversion(lead);

  // Chat Bubbles
  renderMessages(messages || []);

  // AI Drafts
  if (openApproval && openApproval.drafts && openApproval.drafts.length > 0) {
    renderDrafts(openApproval.drafts, openApproval.id);
  } else {
    elements.draftsContainer.innerHTML = '<div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 0.82rem;">Paste an incoming DM on the left to generate 3 strategic options with Gemini 3.7 Flash.</div>';
  }
}

function renderConversion(lead) {
  const prob = lead.conversion_probability || 50;
  elements.conversionScore.textContent = `${prob}%`;
  elements.conversionBar.style.width = `${prob}%`;

  if (prob >= 75) {
    elements.conversionTag.textContent = '🔥 High Buying Intent';
    elements.conversionTag.style.color = 'var(--accent-amber)';
    elements.conversionBar.style.background = 'linear-gradient(90deg, #f59e0b, #10b981)';
  } else if (prob >= 45) {
    elements.conversionTag.textContent = '⚡ Active Conversation';
    elements.conversionTag.style.color = 'var(--accent-cyan)';
    elements.conversionBar.style.background = 'linear-gradient(90deg, #06b6d4, #3b82f6)';
  } else {
    elements.conversionTag.textContent = '🌱 Nurturing Stage';
    elements.conversionTag.style.color = 'var(--text-muted)';
    elements.conversionBar.style.background = 'linear-gradient(90deg, #64748b, #94a3b8)';
  }

  elements.conversionRationale.textContent = lead.conversion_rationale || lead.needs || 'Analyzing conversation stage and lead cues...';

  let signals = [];
  try {
    signals = typeof lead.buying_signals === 'string' ? JSON.parse(lead.buying_signals) : lead.buying_signals || [];
  } catch (e) {
    signals = [];
  }

  if (signals.length > 0) {
    elements.buyingSignalsList.innerHTML = signals.map((s) => `<span class="signal-tag">✓ ${escapeHtml(s)}</span>`).join('');
  } else {
    elements.buyingSignalsList.innerHTML = `<span class="signal-tag">Stage: ${lead.status || 'first_contact'}</span>`;
  }
}

function renderMessages(messages) {
  if (messages.length === 0) {
    elements.messagesContainer.innerHTML = '<div style="margin: auto; color: var(--text-muted); font-size: 0.85rem; text-align: center;">No messages yet. Paste their DM below to start!</div>';
    return;
  }

  elements.messagesContainer.innerHTML = messages
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

  // Scroll to bottom
  elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}

function renderDrafts(drafts, approvalId) {
  if (!drafts || drafts.length === 0) {
    elements.draftsContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted);">No drafts available.</div>';
    return;
  }

  elements.draftsContainer.innerHTML = drafts
    .map((draft, idx) => {
      const tone = draft.tone || 'warm';
      const title = TONE_LABELS[tone] || `Option ${idx + 1}`;
      const toneClass = `tone-${tone}`;

      return `
        <div class="draft-card">
          <div class="draft-card-header">
            <span class="draft-tone ${toneClass}">${title}</span>
            <div class="draft-actions">
              <button class="btn btn-sm btn-secondary" onclick="copyDraftText(this, \`${escapeJsString(draft.text)}\`)">
                📋 Copy
              </button>
              <button class="btn btn-sm btn-primary" onclick="handleApproveDraft('${approvalId}', \`${escapeJsString(draft.text)}\`)">
                ✅ Mark Sent
              </button>
            </div>
          </div>
          <div class="draft-text">${escapeHtml(draft.text)}</div>
        </div>
      `;
    })
    .join('');
}

// --- Modals & Utilities ---

function openNewLeadModal() {
  elements.formIgsid.value = '';
  elements.formHandle.value = '';
  elements.formPodcast.value = '';
  elements.formAudience.value = '';
  elements.formBio.value = '';
  elements.formInitialMsg.value = '';
  elements.formNotes.value = '';
  elements.modalTitle.textContent = 'New Lead Conversation';
  elements.initialMsgGroup.classList.remove('hidden');
  elements.leadModal.classList.remove('hidden');
}

function openEditLeadModal() {
  const lead = state.leads.find((l) => l.igsid === state.activeLeadId);
  if (!lead) return;

  elements.formIgsid.value = lead.igsid;
  elements.formHandle.value = lead.handle || '';
  elements.formPodcast.value = lead.podcast_name || '';
  elements.formAudience.value = lead.audience_size || '';
  elements.formBio.value = lead.bio || '';
  elements.formNotes.value = lead.notes || '';
  elements.modalTitle.textContent = `Edit Lead ${lead.handle || ''}`;
  elements.initialMsgGroup.classList.add('hidden');
  elements.leadModal.classList.remove('hidden');
}

function closeLeadModal() {
  elements.leadModal.classList.add('hidden');
}

async function openCrmModal() {
  elements.crmModal.classList.remove('hidden');
  try {
    const res = await fetch('/api/leads');
    const data = await res.json();
    const leads = data.leads || [];

    elements.crmTableBody.innerHTML = leads
      .map((l) => {
        const prob = l.conversion_probability || 50;
        const lastDate = l.updated_at ? new Date(l.updated_at * 1000).toLocaleDateString() : '-';
        return `
          <tr onclick="selectLead('${l.igsid}'); closeCrmModal();" style="cursor: pointer;">
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
  } catch (err) {
    showToast('Failed to load CRM data');
  }
}

function closeCrmModal() {
  elements.crmModal.classList.add('hidden');
}

function downloadCsv() {
  window.location.href = '/api/export/csv';
}

function copyDraftText(button, text) {
  navigator.clipboard.writeText(text).then(() => {
    const originalText = button.innerHTML;
    button.innerHTML = '✓ Copied!';
    button.style.backgroundColor = 'var(--accent-emerald)';
    button.style.color = '#ffffff';
    showToast('Copied to clipboard!');
    setTimeout(() => {
      button.innerHTML = originalText;
      button.style.backgroundColor = '';
      button.style.color = '';
    }, 2000);
  });
}

function showToast(msg) {
  elements.toast.textContent = msg;
  elements.toast.classList.remove('hidden');
  setTimeout(() => {
    elements.toast.classList.add('hidden');
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
