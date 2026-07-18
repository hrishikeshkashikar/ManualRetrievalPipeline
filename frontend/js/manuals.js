/**
 * Manual Management — list, display, and delete indexed manuals.
 */

class ManualManager {
  constructor() {
    this.manuals = [];
  }

  init() {
    this.refresh();
  }

  async refresh() {
    const container = $('#manuals-content');
    if (!container) return;

    container.innerHTML = `
      <div class="empty-state">
        <div class="spinner spinner-lg"></div>
        <p style="margin-top: var(--space-4); color: var(--text-secondary);">Loading manuals...</p>
      </div>
    `;

    try {
      const data = await api.listManuals();
      this.manuals = data.manuals || [];
      this.renderManuals();
    } catch (err) {
      container.innerHTML = `
        <div class="empty-state">
          <svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          <h3 class="empty-state-title">Failed to Load</h3>
          <p class="empty-state-description">${escapeHtml(err.message)}</p>
          <button class="btn btn-primary" onclick="manualManager.refresh()">
            Retry
          </button>
        </div>
      `;
    }
  }

  renderManuals() {
    const container = $('#manuals-content');
    if (!container) return;

    if (this.manuals.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>
          </svg>
          <h3 class="empty-state-title">No Manuals Yet</h3>
          <p class="empty-state-description">Upload a PDF manual to get started. Head over to the Upload tab to ingest your first manual.</p>
          <button class="btn btn-primary" onclick="navigateTo('upload')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            Upload Manual
          </button>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-5);">
        <div style="font-size: var(--text-sm); color: var(--text-secondary);">
          ${this.manuals.length} manual${this.manuals.length !== 1 ? 's' : ''} indexed
        </div>
        <button class="btn btn-ghost btn-sm" onclick="manualManager.refresh()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>
          Refresh
        </button>
      </div>
      <div class="grid-auto stagger-children">
        ${this.manuals.map(m => this.renderManualCard(m)).join('')}
      </div>
    `;
  }

  renderManualCard(manual) {
    return `
      <div class="card hover-lift" style="cursor: default;">
        <div class="card-header">
          <div style="display: flex; align-items: center; gap: var(--space-3); min-width: 0;">
            <div style="width: 40px; height: 40px; border-radius: var(--radius-md); background: var(--color-danger-bg); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-danger)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
            </div>
            <div style="min-width: 0;">
              <div class="card-title truncate" style="font-size: var(--text-base);">${escapeHtml(manual.filename)}</div>
            </div>
          </div>
        </div>
        <div class="card-body">
          <div style="display: flex; gap: var(--space-4); margin-bottom: var(--space-3);">
            <div class="stat-card">
              <div class="stat-value" style="font-size: var(--text-lg);">${formatNumber(manual.total_chunks)}</div>
              <div class="stat-label">Chunks</div>
            </div>
          </div>
          <div class="chip" style="margin-top: var(--space-2);">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>
            ${escapeHtml(manual.manual_id.substring(0, 12))}...
          </div>
        </div>
        <div class="card-footer">
          <button class="btn btn-danger btn-sm" style="margin-left: auto;" onclick="manualManager.confirmDelete('${escapeHtml(manual.manual_id)}', '${escapeHtml(manual.filename)}')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
            Delete
          </button>
        </div>
      </div>
    `;
  }

  confirmDelete(manualId, filename) {
    const overlay = $('#delete-modal');
    const titleEl = $('#delete-modal-filename');
    const confirmBtn = $('#delete-modal-confirm');

    if (titleEl) titleEl.textContent = filename;
    if (overlay) overlay.classList.remove('hidden');

    if (confirmBtn) {
      // Remove old listener by cloning
      const newBtn = confirmBtn.cloneNode(true);
      confirmBtn.parentNode.replaceChild(newBtn, confirmBtn);
      newBtn.id = 'delete-modal-confirm';
      newBtn.addEventListener('click', () => this.executeDelete(manualId));
    }
  }

  closeDeleteModal() {
    const overlay = $('#delete-modal');
    if (overlay) overlay.classList.add('hidden');
  }

  async executeDelete(manualId) {
    this.closeDeleteModal();

    try {
      await api.deleteManual(manualId);
      showToast('success', 'Manual Deleted', 'The manual has been removed from the index.');
      this.refresh();
      // Also refresh the chat manual filter
      if (typeof chatInterface !== 'undefined') {
        chatInterface.loadManualFilter();
      }
    } catch (err) {
      showToast('error', 'Delete Failed', err.message);
    }
  }

  /** Returns the list of manuals (for use by other modules like chat filter). */
  getManuals() {
    return this.manuals;
  }
}

const manualManager = new ManualManager();
