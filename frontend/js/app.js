/**
 * App Shell — view routing, sidebar navigation, initialization.
 */

// ── View Router ─────────────────────────────────────────────────────────

let currentView = 'chat';

function navigateTo(view) {
  currentView = view;

  // Update nav items
  $$('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.view === view);
  });

  // Switch view panels
  $$('.view-panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === `view-${view}`);
  });

  // View-specific init
  switch (view) {
    case 'chat':
      chatInterface.init();
      break;
    case 'manuals':
      manualManager.refresh();
      break;
    case 'upload':
      ingestManager.init();
      break;
    case 'health':
      healthDashboard.startPolling();
      break;
  }

  // Stop health polling when not on health view
  if (view !== 'health') {
    healthDashboard.stopPolling();
  }
}

// ── Sidebar Toggle ──────────────────────────────────────────────────────

function toggleSidebar() {
  document.querySelector('.app-layout')?.classList.toggle('sidebar-collapsed');
}

// ── Source Panel ─────────────────────────────────────────────────────────

function closeSourcePanel() {
  document.querySelector('.app-layout')?.classList.remove('source-panel-open');
}

// ── Mount Manager ──────────────────────────────────────────────────────────

const mountManager = {
  currentPath: null,
  isMounted: false,
  browsePath: '/',
  browseParent: null,

  updateSidebarLabel() {
    const label = $('#sidebar-mount-label');
    if (!label) return;
    if (this.currentPath) {
      const short = this.currentPath.length > 28
        ? '…' + this.currentPath.slice(-27)
        : this.currentPath;
      label.textContent = short;
      label.title = this.currentPath;
    } else {
      label.textContent = 'Change Data Path';
      label.title = 'Mount a knowledge-base folder';
    }
  },

  async checkMountStatus() {
    try {
      const config = await api.getMountConfig();
      if (config.status === 'mounted') {
        this.isMounted = true;
        this.currentPath = config.path;
        this.updateSidebarLabel();
        this.hideModal();
        return true;
      } else {
        this.isMounted = false;
        this.currentPath = null;
        this.updateSidebarLabel();
        this.showModal(false);
        return false;
      }
    } catch (err) {
      this.isMounted = false;
      this.updateSidebarLabel();
      this.showModal(false);
      return false;
    }
  },

  showModal(allowCancel = false) {
    const modal = $('#mount-modal');
    if (!modal) return;
    modal.classList.remove('hidden');

    const cancelBtn = $('#mount-modal-cancel');
    if (cancelBtn) {
      cancelBtn.classList.toggle('hidden', !allowCancel);
    }

    const input = $('#mount-path-input');
    if (input) {
      input.value = this.currentPath || '';
    }

    // Start browser at current path's parent, or roots
    const start = this.currentPath || '/';
    this.loadBrowse(start).catch(() => this.loadBrowse('/'));
  },

  hideModal() {
    const modal = $('#mount-modal');
    modal?.classList.add('hidden');
  },

  async loadBrowse(path) {
    const listing = $('#browse-listing');
    const pathLabel = $('#browse-current-path');
    const rootsEl = $('#browse-roots');
    if (listing) {
      listing.innerHTML = `<div style="padding: var(--space-4); color: var(--text-tertiary); font-size: var(--text-sm);">Loading…</div>`;
    }

    try {
      const data = await api.browseHostPath(path);
      this.browsePath = data.path;
      this.browseParent = data.parent;

      if (pathLabel) pathLabel.textContent = data.path === '/' ? 'This machine' : data.path;

      if (rootsEl) {
        rootsEl.innerHTML = (data.roots || []).map((r) => `
          <button type="button" class="btn btn-secondary btn-xs browse-root-btn" data-path="${escapeHtml(r.path)}">${escapeHtml(r.label)}</button>
        `).join('');
        rootsEl.querySelectorAll('.browse-root-btn').forEach((btn) => {
          btn.addEventListener('click', () => this.loadBrowse(btn.dataset.path));
        });
      }

      if (!listing) return;

      if (!data.entries || data.entries.length === 0) {
        listing.innerHTML = `<div style="padding: var(--space-4); color: var(--text-tertiary); font-size: var(--text-sm);">No subfolders here. You can still use this folder.</div>`;
      } else {
        listing.innerHTML = data.entries.map((e) => `
          <button type="button" class="browse-entry" data-path="${escapeHtml(e.path)}" style="display: flex; width: 100%; align-items: center; gap: 10px; padding: 10px 12px; border: 0; border-bottom: 1px solid var(--surface-glass-border); background: transparent; color: var(--text-primary); text-align: left; cursor: pointer;">
            <span style="opacity: 0.7;">📁</span>
            <span style="flex: 1; font-size: var(--text-sm);">${escapeHtml(e.name)}</span>
            ${e.looks_like_kb ? '<span class="badge badge-success" style="font-size: 10px;">data</span>' : ''}
          </button>
        `).join('');

        listing.querySelectorAll('.browse-entry').forEach((btn) => {
          btn.addEventListener('click', () => {
            const p = btn.dataset.path;
            const input = $('#mount-path-input');
            if (input) input.value = p;
            this.loadBrowse(p);
          });
          btn.addEventListener('dblclick', () => {
            const p = btn.dataset.path;
            const input = $('#mount-path-input');
            if (input) input.value = p;
            this.mount();
          });
        });
      }

      // Selecting current browse folder
      const input = $('#mount-path-input');
      if (input && data.path && data.path !== '/') {
        input.value = data.path;
      }
    } catch (err) {
      if (listing) {
        listing.innerHTML = `<div style="padding: var(--space-4); color: var(--color-danger); font-size: var(--text-sm);">${escapeHtml(err.message || 'Failed to browse')}</div>`;
      }
    }
  },

  async mount() {
    const input = $('#mount-path-input');
    if (!input || !input.value.trim()) {
      showToast('warning', 'Invalid Path', 'Select a folder from the browser or paste an absolute path.');
      return;
    }

    const path = input.value.trim();
    const confirmBtn = $('#mount-modal-confirm');
    const spinner = $('#mount-modal-spinner');

    if (confirmBtn) confirmBtn.disabled = true;
    spinner?.classList.remove('hidden');

    try {
      const res = await api.mountDataDirectory(path);
      if (res.status === 'mounted') {
        this.isMounted = true;
        this.currentPath = res.path;
        this.updateSidebarLabel();
        showToast('success', 'Path Mounted', res.message || `Mounted: ${res.path}`);
        this.hideModal();

        healthDashboard.refresh();
        if (currentView === 'chat') {
          chatInterface.init();
        } else if (currentView === 'manuals') {
          manualManager.refresh();
        }
      } else {
        showToast('error', 'Mount Failed', res.message || 'Unknown error.');
      }
    } catch (err) {
      showToast('error', 'Mount Failed', err.message);
    } finally {
      if (confirmBtn) confirmBtn.disabled = false;
      spinner?.classList.add('hidden');
    }
  }
};

// ── Initialization ──────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  // Bind nav clicks
  $$('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
      // Don't navigate if unmounted
      if (!mountManager.isMounted) {
        showToast('warning', 'Action Required', 'Please mount a data directory first.');
        return;
      }
      const view = item.dataset.view;
      if (view) navigateTo(view);
    });
  });

  // Sidebar toggle
  const toggleBtn = $('#sidebar-toggle-btn');
  if (toggleBtn) toggleBtn.addEventListener('click', toggleSidebar);

  // Source panel close
  const closeSrcBtn = $('#source-panel-close-btn');
  if (closeSrcBtn) closeSrcBtn.addEventListener('click', closeSourcePanel);

  // Sidebar status click → navigate to health
  const statusBar = $('#sidebar-status-bar');
  if (statusBar) statusBar.addEventListener('click', () => {
    if (mountManager.isMounted) navigateTo('health');
  });

  // Delete modal cancel
  const cancelDeleteBtn = $('#delete-modal-cancel');
  if (cancelDeleteBtn) cancelDeleteBtn.addEventListener('click', () => manualManager.closeDeleteModal());

  // Close delete modal on overlay click
  const deleteOverlay = $('#delete-modal');
  if (deleteOverlay) {
    deleteOverlay.addEventListener('click', (e) => {
      if (e.target === deleteOverlay) manualManager.closeDeleteModal();
    });
  }

  // Mount modal actions
  const mountConfirmBtn = $('#mount-modal-confirm');
  if (mountConfirmBtn) mountConfirmBtn.addEventListener('click', () => mountManager.mount());

  const browseUpBtn = $('#browse-up-btn');
  if (browseUpBtn) {
    browseUpBtn.addEventListener('click', () => {
      const parent = mountManager.browseParent || '/';
      mountManager.loadBrowse(parent);
    });
  }

  const mountInput = $('#mount-path-input');
  if (mountInput) {
    mountInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') mountManager.mount();
    });
  }

  const mountCancelBtn = $('#mount-modal-cancel');
  if (mountCancelBtn) mountCancelBtn.addEventListener('click', () => mountManager.hideModal());

  // Sidebar change mount button
  const changeMountBtn = $('#sidebar-change-mount-btn');
  if (changeMountBtn) {
    changeMountBtn.addEventListener('click', () => {
      mountManager.showModal(true); // Allow cancel when manually changing
    });
  }

  // Handle global unmounted state trigger from api.js
  document.addEventListener('unmounted-state', () => {
    mountManager.isMounted = false;
    mountManager.showModal(false);
  });

  // Initial boot: check mount status first
  mountManager.checkMountStatus().then((mounted) => {
    if (mounted) {
      healthDashboard.refresh();
      navigateTo('chat');
    }
  });
});
