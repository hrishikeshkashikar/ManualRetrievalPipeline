/**
 * PDF Upload — drag-and-drop upload with processing status display.
 */

class IngestManager {
  constructor() {
    this.isUploading = false;
  }

  init() {
    this.render();
    this.bindEvents();
  }

  render() {
    const container = $('#upload-content');
    if (!container) return;

    container.innerHTML = `
      <!-- Drop Zone -->
      <div id="upload-dropzone" class="upload-dropzone">
        <div class="upload-dropzone-inner">
          <div class="upload-icon">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          </div>
          <h3 class="upload-title">Drop your PDF manual here</h3>
          <p class="upload-subtitle">or click to browse files</p>
          <p class="upload-hint">Supports PDF files • Text, diagrams, and images will be extracted</p>
          <input type="file" id="upload-file-input" accept=".pdf" style="display: none;" />
        </div>
      </div>

      <!-- Upload Progress (hidden by default) -->
      <div id="upload-progress" style="display: none;">
        <div class="card" style="margin-top: var(--space-6);">
          <div style="display: flex; align-items: center; gap: var(--space-4); margin-bottom: var(--space-4);">
            <div class="spinner"></div>
            <div>
              <div style="font-weight: var(--weight-semibold);" id="upload-progress-filename">Processing...</div>
              <div style="font-size: var(--text-xs); color: var(--text-tertiary);" id="upload-progress-status">Extracting text, images, and generating embeddings</div>
            </div>
          </div>
          <div class="progress-bar progress-bar-indeterminate">
            <div class="progress-bar-fill"></div>
          </div>
        </div>
      </div>

      <!-- Upload Result (hidden by default) -->
      <div id="upload-result" style="display: none; margin-top: var(--space-6);"></div>
    `;
  }

  bindEvents() {
    const dropzone = $('#upload-dropzone');
    const fileInput = $('#upload-file-input');
    if (!dropzone || !fileInput) return;

    // Click to browse
    dropzone.addEventListener('click', () => {
      if (!this.isUploading) fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) this.uploadFile(file);
      fileInput.value = '';
    });

    // Drag events
    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      const file = e.dataTransfer.files[0];
      if (file) this.uploadFile(file);
    });
  }

  async uploadFile(file) {
    if (this.isUploading) return;

    // Validate
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      showToast('error', 'Invalid File', 'Only PDF files are supported.');
      return;
    }

    this.isUploading = true;
    this.showProgress(file.name);

    try {
      const result = await api.ingestManual(file);
      this.showResult(result);
      showToast('success', 'Manual Ingested', result.message);

      // Refresh manuals list
      if (typeof manualManager !== 'undefined') {
        manualManager.refresh();
      }
      if (typeof chatInterface !== 'undefined') {
        chatInterface.loadManualFilter();
      }
    } catch (err) {
      this.showError(err.message);
      showToast('error', 'Upload Failed', err.message);
    } finally {
      this.isUploading = false;
    }
  }

  showProgress(filename) {
    const dropzone = $('#upload-dropzone');
    const progress = $('#upload-progress');
    const result = $('#upload-result');
    const nameEl = $('#upload-progress-filename');

    if (dropzone) dropzone.style.display = 'none';
    if (progress) progress.style.display = 'block';
    if (result) result.style.display = 'none';
    if (nameEl) nameEl.textContent = filename;
  }

  showResult(result) {
    const dropzone = $('#upload-dropzone');
    const progress = $('#upload-progress');
    const resultEl = $('#upload-result');

    if (progress) progress.style.display = 'none';
    if (dropzone) dropzone.style.display = 'block';
    if (!resultEl) return;

    resultEl.style.display = 'block';

    const isSuccess = result.status === 'success';
    const statusBadge = isSuccess
      ? '<span class="badge badge-success">Success</span>'
      : result.status === 'partial'
        ? '<span class="badge badge-warning">Partial</span>'
        : '<span class="badge badge-danger">Failed</span>';

    resultEl.innerHTML = `
      <div class="card animate-fade-in-up" style="border-color: ${isSuccess ? 'var(--color-success-border)' : 'var(--color-warning-border)'};">
        <div class="card-header">
          <div>
            <div class="card-title" style="display: flex; align-items: center; gap: var(--space-3);">
              Ingestion Complete ${statusBadge}
            </div>
            <div class="card-subtitle">${escapeHtml(result.filename)}</div>
          </div>
        </div>
        <div class="card-body">
          <div class="grid-4" style="margin-bottom: var(--space-4);">
            <div class="stat-card">
              <div class="stat-value" style="font-size: var(--text-xl);">${result.total_pages}</div>
              <div class="stat-label">Pages</div>
            </div>
            <div class="stat-card">
              <div class="stat-value" style="font-size: var(--text-xl);">${result.text_chunks}</div>
              <div class="stat-label">Text Chunks</div>
            </div>
            <div class="stat-card">
              <div class="stat-value" style="font-size: var(--text-xl);">${result.images_extracted}</div>
              <div class="stat-label">Images</div>
            </div>
            <div class="stat-card">
              <div class="stat-value" style="font-size: var(--text-xl);">${result.captions_generated}</div>
              <div class="stat-label">Captions</div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: var(--space-3); font-size: var(--text-sm); color: var(--text-secondary);">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            Processed in ${formatDuration(result.processing_time_seconds)}
          </div>
          ${result.message ? `<p style="margin-top: var(--space-3); font-size: var(--text-sm); color: var(--text-secondary);">${escapeHtml(result.message)}</p>` : ''}
        </div>
      </div>
    `;
  }

  showError(message) {
    const dropzone = $('#upload-dropzone');
    const progress = $('#upload-progress');
    const resultEl = $('#upload-result');

    if (progress) progress.style.display = 'none';
    if (dropzone) dropzone.style.display = 'block';
    if (!resultEl) return;

    resultEl.style.display = 'block';
    resultEl.innerHTML = `
      <div class="card animate-fade-in-up" style="border-color: var(--color-danger-border);">
        <div style="display: flex; align-items: center; gap: var(--space-3);">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--color-danger)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          <div>
            <div style="font-weight: var(--weight-semibold); color: var(--color-danger);">Upload Failed</div>
            <div style="font-size: var(--text-sm); color: var(--text-secondary); margin-top: var(--space-1);">${escapeHtml(message)}</div>
          </div>
        </div>
      </div>
    `;
  }
}

const ingestManager = new IngestManager();
