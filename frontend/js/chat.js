/**
 * Chat Interface — handles querying with streaming + structured response rendering.
 *
 * Flow:
 *   1. On init, show the PDF selection screen (Step 1).
 *   2. User picks a manual → transition to the welcome/suggestions screen (Step 2).
 *   3. Queries are locked to the selected manual.
 *   4. User can change the manual via the badge in the welcome screen or input bar.
 */

class ChatInterface {
  constructor() {
    this.messages = [];
    this.isStreaming = false;
    this.sourcesMap = {};
    this.abortController = null;
    this.selectedManualId = null;
    this.selectedManualName = null;
    this.manualsList = [];
  }

  init() {
    this.bindEvents();
    this.loadPdfSelector();
  }

  bindEvents() {
    const textarea = $('#chat-textarea');
    const sendBtn = $('#chat-send-btn');
    const topKRange = $('#chat-topk');
    const topKValue = $('#chat-topk-value');

    if (textarea) {
      textarea.addEventListener('input', () => {
        autoResize(textarea);
        this.updateSendButton();
      });

      textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });
    }

    if (sendBtn) {
      sendBtn.addEventListener('click', () => this.sendMessage());
    }

    if (topKRange && topKValue) {
      topKRange.addEventListener('input', () => {
        topKValue.textContent = topKRange.value;
      });
    }

    // Suggestion chips
    $$('.chat-suggestion').forEach(chip => {
      chip.addEventListener('click', () => {
        const textarea = $('#chat-textarea');
        if (textarea) {
          textarea.value = chip.textContent.trim();
          autoResize(textarea);
          this.updateSendButton();
          this.sendMessage();
        }
      });
    });
  }

  updateSendButton() {
    const textarea = $('#chat-textarea');
    const sendBtn = $('#chat-send-btn');
    if (textarea && sendBtn) {
      sendBtn.disabled = !textarea.value.trim() || this.isStreaming || !this.selectedManualId;
    }
  }

  // ── Step 1: PDF Selector ──────────────────────────────────────────────

  async loadPdfSelector() {
    const container = $('#pdf-select-container');
    if (!container) return;

    try {
      const data = await api.listManuals();
      this.manualsList = data.manuals || [];
      this.renderPdfSelector();
    } catch (err) {
      container.innerHTML = `
        <div class="pdf-select-error">
          <p>Failed to load manuals: ${escapeHtml(err.message)}</p>
          <button class="btn btn-primary btn-sm" onclick="chatInterface.loadPdfSelector()">Retry</button>
        </div>
      `;
    }
  }

  renderPdfSelector() {
    const container = $('#pdf-select-container');
    if (!container) return;

    if (this.manualsList.length === 0) {
      container.innerHTML = `
        <div class="pdf-select-empty">
          <p>No manuals have been uploaded yet.</p>
          <button class="btn btn-primary" onclick="navigateTo('upload')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            Upload a Manual
          </button>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="pdf-select-grid">
        ${this.manualsList.map(m => `
          <button class="pdf-select-card hover-lift" data-manual-id="${escapeHtml(m.manual_id)}" data-manual-name="${escapeHtml(m.filename)}">
            <div class="pdf-select-card-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
            </div>
            <div class="pdf-select-card-name">${escapeHtml(m.filename)}</div>
            <div class="pdf-select-card-meta">${formatNumber(m.total_chunks)} chunks</div>
          </button>
        `).join('')}
      </div>
    `;

    // Bind card clicks
    container.querySelectorAll('.pdf-select-card').forEach(card => {
      card.addEventListener('click', () => {
        const manualId = card.dataset.manualId;
        const manualName = card.dataset.manualName;
        this.selectManual(manualId, manualName);
      });
    });
  }

  selectManual(manualId, manualName) {
    this.selectedManualId = manualId;
    this.selectedManualName = manualName;

    // Set the hidden filter dropdown
    const select = $('#chat-manual-filter');
    if (select) select.value = manualId;

    // Hide PDF selector, show welcome
    const pdfSelect = $('#chat-pdf-select');
    const welcome = $('#chat-welcome');
    if (pdfSelect) pdfSelect.style.display = 'none';
    if (welcome) welcome.style.display = '';

    // Update active manual badge in welcome screen
    this.updateManualBadge();

    // Update the input bar chip
    this.updateInputBarChip();

    // Enable/disable send button
    this.updateSendButton();
  }

  updateManualBadge() {
    const badge = $('#active-manual-badge');
    if (!badge || !this.selectedManualName) return;

    badge.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
        <polyline points="14 2 14 8 20 8"/>
      </svg>
      <span>Querying: <strong>${escapeHtml(this.selectedManualName)}</strong></span>
      <button class="change-manual-btn" onclick="chatInterface.goBackToPdfSelect()" title="Change manual">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>
        Change
      </button>
    `;
  }

  updateInputBarChip() {
    const chip = $('#chat-input-manual-chip');
    if (!chip) return;

    if (!this.selectedManualName) {
      chip.innerHTML = '';
      return;
    }

    const shortName = this.selectedManualName.length > 25
      ? this.selectedManualName.substring(0, 22) + '…'
      : this.selectedManualName;

    chip.innerHTML = `
      <span class="input-manual-chip">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
        ${escapeHtml(shortName)}
      </span>
    `;
  }

  goBackToPdfSelect() {
    // Reset selection
    this.selectedManualId = null;
    this.selectedManualName = null;

    const select = $('#chat-manual-filter');
    if (select) select.value = '';

    // Reset chat state
    this.messages = [];
    this.sourcesMap = {};
    const messagesInner = $('#chat-messages-inner');
    if (messagesInner) messagesInner.innerHTML = '';

    // Show PDF selector, hide welcome and messages
    const pdfSelect = $('#chat-pdf-select');
    const welcome = $('#chat-welcome');
    const messages = $('#chat-messages');
    if (pdfSelect) pdfSelect.style.display = '';
    if (welcome) welcome.style.display = 'none';
    if (messages) messages.style.display = 'none';

    // Clear the input bar chip
    this.updateInputBarChip();
    this.updateSendButton();

    // Reload the manual list (in case new ones were uploaded)
    this.loadPdfSelector();
  }

  // ── Legacy: keep loadManualFilter for external callers ────────────────

  async loadManualFilter() {
    // Reload the hidden select and the PDF grid if visible
    const select = $('#chat-manual-filter');
    if (!select) return;

    try {
      const data = await api.listManuals();
      this.manualsList = data.manuals || [];

      const current = select.value;
      select.innerHTML = '<option value="">All Manuals</option>';
      this.manualsList.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m.manual_id;
        opt.textContent = m.filename;
        select.appendChild(opt);
      });
      if (current) select.value = current;

      // Also refresh the PDF selector grid if it's visible
      const pdfSelect = $('#chat-pdf-select');
      if (pdfSelect && pdfSelect.style.display !== 'none') {
        this.renderPdfSelector();
      }
    } catch (err) {
      // Silently fail
    }
  }

  // ── Messaging ─────────────────────────────────────────────────────────

  async sendMessage() {
    const textarea = $('#chat-textarea');
    if (!textarea || !textarea.value.trim() || this.isStreaming) return;

    // Ensure a manual is selected
    if (!this.selectedManualId) {
      showToast('warning', 'No Manual Selected', 'Please select a PDF manual before querying.');
      return;
    }

    const query = textarea.value.trim();
    textarea.value = '';
    autoResize(textarea);
    this.updateSendButton();

    // Force the manual filter to the selected manual
    const topK = parseInt($('#chat-topk')?.value || '5', 10);

    // Hide welcome, show messages area
    this.hideWelcome();

    // Add user message
    this.addMessage('user', query);

    // Create assistant message placeholder
    const assistantMsgId = this.addMessage('assistant', null, true);

    // Send query — single streaming call with SSE events
    this.isStreaming = true;
    this.updateSendButton();

    const request = {
      query,
      manual_filter: this.selectedManualId,
      top_k: topK,
    };

    let streamedText = '';
    this.abortController = new AbortController();

    try {
      await api.queryStream(
        request,
        // onSources — render source chips immediately
        (sources) => {
          if (sources && sources.length > 0) {
            this.renderStreamSources(assistantMsgId, sources);
          }
        },
        // onToken — accumulate and update the streaming message
        (token) => {
          streamedText += token;
          this.updateStreamingMessage(assistantMsgId, streamedText);
        },
        // onDone — finalize with processing time
        (doneData) => {
          this.finalizeStreamedMessage(assistantMsgId, streamedText, doneData?.processing_time_seconds);
        },
        // onError
        (err) => {
          this.showMessageError(assistantMsgId, err.message);
        },
        this.abortController.signal,
      );

      // If stream ended without a done event (edge case), finalize anyway
      if (streamedText && this.isStreaming) {
        this.finalizeStreamedMessage(assistantMsgId, streamedText);
      }
    } catch (err) {
      this.showMessageError(assistantMsgId, err.message);
    } finally {
      this.isStreaming = false;
      this.abortController = null;
      this.updateSendButton();
    }
  }

  hideWelcome() {
    const pdfSelect = $('#chat-pdf-select');
    const welcome = $('#chat-welcome');
    const messages = $('#chat-messages');
    if (pdfSelect) pdfSelect.style.display = 'none';
    if (welcome) welcome.style.display = 'none';
    if (messages) messages.style.display = 'flex';
  }

  addMessage(role, content, isPlaceholder = false) {
    const id = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const messagesInner = $('#chat-messages-inner');
    if (!messagesInner) return id;

    const avatarChar = role === 'user' ? 'U' : '⚡';

    const messageEl = createElement('div', {
      id,
      className: `message message-${role}`,
    });

    if (role === 'user') {
      messageEl.innerHTML = `
        <div class="message-avatar">${avatarChar}</div>
        <div class="message-content">
          <div class="message-bubble">${escapeHtml(content)}</div>
          <div class="message-meta">${formatTimestamp(new Date())}</div>
        </div>
      `;
    } else if (isPlaceholder) {
      messageEl.innerHTML = `
        <div class="message-avatar">${avatarChar}</div>
        <div class="message-content">
          <div class="message-bubble">
            <div class="streaming-dots"><span></span><span></span><span></span></div>
          </div>
        </div>
      `;
    }

    messagesInner.appendChild(messageEl);
    this.scrollToBottom();

    return id;
  }

  updateStreamingMessage(msgId, text) {
    const msgEl = document.getElementById(msgId);
    if (!msgEl) return;

    const bubble = msgEl.querySelector('.message-bubble');
    if (!bubble) return;

    bubble.innerHTML = `<div class="streaming-cursor">${renderMarkdown(text)}</div>`;
    this.scrollToBottom();
  }

  finalizeStreamedMessage(msgId, text, processingTime) {
    const msgEl = document.getElementById(msgId);
    if (!msgEl) return;

    const bubble = msgEl.querySelector('.message-bubble');
    if (!bubble) return;

    bubble.innerHTML = `<div class="answer-text">${renderMarkdown(text)}</div>`;
    this.addMeta(msgEl, processingTime);
  }

  /**
   * Render source chips in a message as soon as they arrive from the SSE stream.
   * These appear below the message bubble, before the answer finishes streaming.
   */
  renderStreamSources(msgId, sources) {
    if (!Array.isArray(sources) || sources.length === 0) return;

    const msgEl = document.getElementById(msgId);
    if (!msgEl) return;

    const content = msgEl.querySelector('.message-content');
    if (!content) return;

    // Don't duplicate if sources already rendered
    if (msgEl.querySelector('.response-sources')) return;

    // Store sources for click handling
    const sourceKey = `src-${Date.now()}`;
    this.sourcesMap[sourceKey] = sources;

    const sourcesHtml = `
      <div class="response-sources" style="margin-top: var(--space-3);">
        ${sources.map((s, i) => {
          const shortName = s.source_file.length > 30
            ? s.source_file.substring(0, 27) + '…'
            : s.source_file;
          return `
          <span class="source-chip" onclick="chatInterface.showSourceByIndex('${sourceKey}', ${i})">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
            ${escapeHtml(shortName)} · p.${s.page_number}
          </span>
        `}).join('')}
      </div>
    `;

    // Insert after the bubble
    const sourcesEl = document.createElement('div');
    sourcesEl.innerHTML = sourcesHtml;
    const bubble = msgEl.querySelector('.message-bubble');
    if (bubble) {
      bubble.insertAdjacentElement('afterend', sourcesEl.firstElementChild);
    }

    this.scrollToBottom();
  }

  finalizeMessage(msgId, response) {
    const msgEl = document.getElementById(msgId);
    if (!msgEl) return;

    const bubble = msgEl.querySelector('.message-bubble');
    if (!bubble) return;

    let html = '<div class="structured-response">';

    // Answer text
    html += `<div class="answer-text">${renderMarkdown(response.answer)}</div>`;

    // Possible issues
    if (response.possible_issues && response.possible_issues.length > 0) {
      html += `
        <div class="response-section response-issues">
          <div class="response-section-header">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
            Possible Issues
          </div>
          <div class="response-section-list">
            ${response.possible_issues.map(i => `<div class="response-section-item">${escapeHtml(i)}</div>`).join('')}
          </div>
        </div>
      `;
    }

    // Solutions
    if (response.recommended_solutions && response.recommended_solutions.length > 0) {
      html += `
        <div class="response-section response-solutions">
          <div class="response-section-header">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="m9 12 2 2 4-4"/></svg>
            Recommended Solutions
          </div>
          <div class="response-section-list">
            ${response.recommended_solutions.map(s => `<div class="response-section-item">${escapeHtml(s)}</div>`).join('')}
          </div>
        </div>
      `;
    }

    // Safety warnings
    if (response.safety_warnings && response.safety_warnings.length > 0) {
      html += `
        <div class="response-section response-warnings">
          <div class="response-section-header">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4"/><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636-2.871L13.637 3.591a1.914 1.914 0 0 0-3.274 0z"/><path d="M12 17h.01"/></svg>
            ⚠️ Safety Warnings
          </div>
          <div class="response-section-list">
            ${response.safety_warnings.map(w => `<div class="response-section-item">${escapeHtml(w)}</div>`).join('')}
          </div>
        </div>
      `;
    }

    // Sources — store in map so we reference by index (avoids inline JSON issues with special chars)
    if (response.sources && response.sources.length > 0) {
      const sourceKey = `src-${Date.now()}`;
      this.sourcesMap[sourceKey] = response.sources;

      html += `
        <div class="response-sources">
          ${response.sources.map((s, i) => {
            const shortName = s.source_file.length > 30
              ? s.source_file.substring(0, 27) + '…'
              : s.source_file;
            return `
            <span class="source-chip" onclick="chatInterface.showSourceByIndex('${sourceKey}', ${i})">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
              ${escapeHtml(shortName)} · p.${s.page_number}
            </span>
          `}).join('')}
        </div>
      `;
    }

    html += '</div>';
    bubble.innerHTML = html;

    // Processing time
    this.addMeta(msgEl, response.processing_time_seconds);
    this.scrollToBottom();
  }

  addMeta(msgEl, processingTime) {
    const content = msgEl.querySelector('.message-content');
    if (!content) return;

    let meta = msgEl.querySelector('.message-meta');
    if (!meta) {
      meta = createElement('div', { className: 'message-meta' });
      content.appendChild(meta);
    }

    let text = formatTimestamp(new Date());
    if (processingTime) {
      text += ` • ${formatDuration(processingTime)}`;
    }
    meta.textContent = text;
  }

  showMessageError(msgId, message) {
    const msgEl = document.getElementById(msgId);
    if (!msgEl) return;

    const bubble = msgEl.querySelector('.message-bubble');
    if (!bubble) return;

    bubble.innerHTML = `
      <div style="display: flex; align-items: flex-start; gap: var(--space-3); color: var(--color-danger);">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink: 0; margin-top: 2px;">
          <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
        </svg>
        <div>
          <div style="font-weight: var(--weight-semibold); margin-bottom: var(--space-1);">Error</div>
          <div style="font-size: var(--text-sm); color: var(--text-secondary);">${escapeHtml(message)}</div>
        </div>
      </div>
    `;
  }

  showSourceByIndex(sourceKey, index) {
    const sources = this.sourcesMap[sourceKey];
    if (!sources || !sources[index]) return;
    this.showSource(sources[index]);
  }

  showSource(source) {
    const panel = $('#source-panel-body');
    if (!panel) return;

    // Open source panel
    document.querySelector('.app-layout')?.classList.add('source-panel-open');

    // Build the page image section if available
    const pageImageHtml = source.page_image_path ? `
      <div class="card card-compact">
        <div style="font-size: var(--text-xs); font-weight: var(--weight-semibold); color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: var(--space-3);">Page Image</div>
        <div style="border-radius: var(--radius-md); overflow: hidden; border: 1px solid var(--surface-glass-border); background: var(--bg-primary);">
          <img src="${api.baseUrl}/${source.page_image_path}" alt="Page ${source.page_number}" style="width: 100%; height: auto; display: block;" onerror="this.parentElement.innerHTML='<div style=padding:var(--space-6);text-align:center;color:var(--text-tertiary);font-size:var(--text-sm)>Image not available</div>'" />
        </div>
      </div>
    ` : '';

    panel.innerHTML = `
      <div class="stagger-children" style="display: flex; flex-direction: column; gap: var(--space-4);">
        <div class="card card-compact">
          <div class="card-title" style="font-size: var(--text-base); margin-bottom: var(--space-3); word-break: break-word;">${escapeHtml(source.source_file)}</div>
          <div style="display: flex; flex-wrap: wrap; gap: var(--space-2);">
            <span class="badge badge-info">Page ${source.page_number}</span>
            <span class="badge badge-secondary">${escapeHtml(source.content_type)}</span>
            <span class="badge badge-primary">Relevance: ${source.relevance_score.toFixed(4)}</span>
          </div>
          ${source.section ? `<div style="margin-top: var(--space-3); font-size: var(--text-sm); color: var(--text-secondary);"><strong>Section:</strong> ${escapeHtml(source.section)}</div>` : ''}
        </div>
        ${source.snippet ? `
          <div class="card card-compact">
            <div style="font-size: var(--text-xs); font-weight: var(--weight-semibold); color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: var(--space-2);">Matched Content</div>
            <div style="font-size: var(--text-sm); color: var(--text-secondary); line-height: var(--leading-normal); font-family: var(--font-mono); white-space: pre-wrap; word-break: break-word;">${escapeHtml(source.snippet)}</div>
          </div>
        ` : ''}
        ${pageImageHtml}
      </div>
    `;
  }

  scrollToBottom() {
    const container = $('#chat-messages');
    if (container) {
      requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
      });
    }
  }
}

const chatInterface = new ChatInterface();
