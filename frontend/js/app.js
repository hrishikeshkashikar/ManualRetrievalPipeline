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

  async checkMountStatus() {
    try {
      const config = await api.getMountConfig();
      if (config.status === 'mounted') {
        this.isMounted = true;
        this.currentPath = config.path;
        this.hideModal();
        return true;
      } else {
        this.isMounted = false;
        this.currentPath = null;
        this.showModal(false); // No cancel button allowed
        return false;
      }
    } catch (err) {
      this.isMounted = false;
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
      input.focus();
    }
  },

  hideModal() {
    const modal = $('#mount-modal');
    modal?.classList.add('hidden');
  },

  async mount() {
    const input = $('#mount-path-input');
    if (!input || !input.value.trim()) {
      showToast('warning', 'Invalid Path', 'Please enter a valid absolute directory path.');
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
        showToast('success', 'Path Mounted', `Successfully mounted data path to: ${res.path}`);
        this.hideModal();
        
        // Refresh application state
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
