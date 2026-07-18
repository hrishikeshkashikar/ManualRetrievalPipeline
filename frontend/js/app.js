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

// ── Initialization ──────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  // Bind nav clicks
  $$('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
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
  if (statusBar) statusBar.addEventListener('click', () => navigateTo('health'));

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

  // Initial boot: check health once for the sidebar dot, then show chat
  healthDashboard.refresh();
  navigateTo('chat');
});
