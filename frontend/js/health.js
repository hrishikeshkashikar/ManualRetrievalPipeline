/**
 * Health Dashboard — polls /health and displays component status.
 */

class HealthDashboard {
  constructor() {
    this.pollInterval = null;
    this.lastHealth = null;
  }

  init() {
    this.render();
    this.refresh();
  }

  destroy() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }

  startPolling() {
    this.stopPolling();
    this.refresh();
    this.pollInterval = setInterval(() => this.refresh(), 30000);
  }

  stopPolling() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }

  async refresh() {
    const container = $('#health-content');
    if (!container) return;

    try {
      const health = await api.getHealth();
      this.lastHealth = health;
      this.renderHealth(health);
      this.updateSidebarStatus(health.status);
    } catch (err) {
      this.renderError(err.message);
      this.updateSidebarStatus('unknown');
    }
  }

  updateSidebarStatus(status) {
    const dot = $('#sidebar-status-dot');
    const label = $('#sidebar-status-label');
    if (dot) {
      dot.className = `status-dot ${status}`;
    }
    if (label) {
      label.textContent = status === 'unknown' ? 'Disconnected' :
                          status.charAt(0).toUpperCase() + status.slice(1);
    }
  }

  render() {
    const container = $('#health-content');
    if (!container) return;
    container.innerHTML = `
      <div class="empty-state">
        <div class="spinner spinner-lg"></div>
        <p style="margin-top: var(--space-4); color: var(--text-secondary);">Checking system health...</p>
      </div>
    `;
  }

  renderHealth(health) {
    const container = $('#health-content');
    if (!container) return;

    const statusConfig = {
      healthy:   { color: 'var(--color-success)',  bg: 'var(--color-success-bg)', label: 'All Systems Operational' },
      degraded:  { color: 'var(--color-warning)',  bg: 'var(--color-warning-bg)', label: 'Degraded Performance' },
      unhealthy: { color: 'var(--color-danger)',   bg: 'var(--color-danger-bg)',  label: 'System Issues Detected' },
    };

    const config = statusConfig[health.status] || statusConfig.unhealthy;

    const components = [
      {
        name: 'Ollama Connection',
        ok: health.ollama_connected,
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a10 10 0 1 0 10 10H12V2Z"/><path d="M12 2a10 10 0 0 1 10 10"/><circle cx="12" cy="12" r="6"/></svg>`,
      },
      {
        name: 'Vision Model',
        ok: health.ollama_model_available,
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>`,
      },
      {
        name: 'Embedding Model',
        ok: health.embedding_model_loaded,
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>`,
      },
      {
        name: 'Reranker Model',
        ok: health.reranker_loaded,
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M7 12h10"/><path d="M10 18h4"/></svg>`,
      },
      {
        name: 'Vector Store',
        ok: health.vector_store_ready,
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/></svg>`,
      },
    ];

    container.innerHTML = `
      <!-- Overall Status Banner -->
      <div class="card" style="border-color: ${config.color}30; background: ${config.bg}; margin-bottom: var(--space-6);">
        <div style="display: flex; align-items: center; gap: var(--space-4);">
          <div class="status-dot ${health.status}" style="width: 14px; height: 14px;"></div>
          <div>
            <div style="font-size: var(--text-lg); font-weight: var(--weight-semibold); color: ${config.color};">
              ${config.label}
            </div>
            <div style="font-size: var(--text-sm); color: var(--text-secondary); margin-top: var(--space-1);">
              Status: <span style="font-family: var(--font-mono);">${health.status}</span>
            </div>
          </div>
          <button class="btn btn-ghost btn-sm" style="margin-left: auto;" onclick="healthDashboard.refresh()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>
            Refresh
          </button>
        </div>
      </div>

      <!-- Stats -->
      <div class="grid-2" style="margin-bottom: var(--space-6);">
        <div class="card card-compact">
          <div class="stat-card">
            <div class="stat-value">${health.manuals_indexed}</div>
            <div class="stat-label">Manuals Indexed</div>
          </div>
        </div>
        <div class="card card-compact">
          <div class="stat-card">
            <div class="stat-value">${formatNumber(health.total_chunks)}</div>
            <div class="stat-label">Total Chunks</div>
          </div>
        </div>
      </div>

      <!-- Components -->
      <h3 style="font-size: var(--text-base); font-weight: var(--weight-semibold); margin-bottom: var(--space-4); color: var(--text-secondary);">Components</h3>
      <div class="stagger-children" style="display: flex; flex-direction: column; gap: var(--space-3);">
        ${components.map(c => `
          <div class="card card-compact" style="border-color: ${c.ok ? 'var(--color-success-border)' : 'var(--color-danger-border)'};">
            <div style="display: flex; align-items: center; gap: var(--space-3);">
              <div style="width: 36px; height: 36px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; background: ${c.ok ? 'var(--color-success-bg)' : 'var(--color-danger-bg)'}; color: ${c.ok ? 'var(--color-success)' : 'var(--color-danger)'};">
                ${c.icon}
              </div>
              <div style="flex: 1;">
                <div style="font-size: var(--text-sm); font-weight: var(--weight-medium);">${c.name}</div>
              </div>
              <span class="badge ${c.ok ? 'badge-success' : 'badge-danger'}">${c.ok ? 'Online' : 'Offline'}</span>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  renderError(message) {
    const container = $('#health-content');
    if (!container) return;
    container.innerHTML = `
      <div class="empty-state">
        <svg class="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/>
          <line x1="15" y1="9" x2="9" y2="15"/>
          <line x1="9" y1="9" x2="15" y2="15"/>
        </svg>
        <h3 class="empty-state-title">Cannot Connect</h3>
        <p class="empty-state-description">${escapeHtml(message)}</p>
        <button class="btn btn-primary" onclick="healthDashboard.refresh()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/></svg>
          Retry
        </button>
      </div>
    `;
  }
}

const healthDashboard = new HealthDashboard();
