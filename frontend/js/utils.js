/**
 * Utility functions — markdown rendering, formatters, toasts, helpers.
 */

// ── Simple Markdown → HTML ──────────────────────────────────────────────

function renderMarkdown(text) {
  if (!text) return '';

  // 1. Escape HTML
  let escaped = escapeHtml(text);

  // 2. Code blocks (```)
  escaped = escaped.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `\nBLOCK_CODE_START_${lang}\n${code.trim()}\nBLOCK_CODE_END\n`;
  });

  // 3. Inline formatting
  escaped = escaped.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
  escaped = escaped.replace(/\*([^*]+?)\*/g, '<em>$1</em>');
  escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Split into lines
  const lines = escaped.split('\n');
  const html = [];
  let currentList = null; // 'ul' | 'ol' | null
  let inCodeBlock = false;
  let codeBlockContent = [];
  let codeBlockLang = '';

  function closeList() {
    if (currentList) {
      html.push(`</${currentList}>`);
      currentList = null;
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    // Code block toggle handling
    if (trimmed.startsWith('BLOCK_CODE_START_')) {
      closeList();
      inCodeBlock = true;
      codeBlockLang = trimmed.replace('BLOCK_CODE_START_', '');
      codeBlockContent = [];
      continue;
    }
    if (trimmed === 'BLOCK_CODE_END') {
      inCodeBlock = false;
      html.push(`<pre><code class="lang-${codeBlockLang}">${codeBlockContent.join('\n')}</code></pre>`);
      continue;
    }

    if (inCodeBlock) {
      codeBlockContent.push(rawLine);
      continue;
    }

    if (trimmed === '') {
      closeList();
      continue;
    }

    // Headers
    if (trimmed.startsWith('### ')) {
      closeList();
      html.push(`<h4>${trimmed.slice(4)}</h4>`);
    } else if (trimmed.startsWith('## ')) {
      closeList();
      html.push(`<h3>${trimmed.slice(3)}</h3>`);
    } else if (trimmed.startsWith('# ')) {
      closeList();
      html.push(`<h2>${trimmed.slice(2)}</h2>`);
    }
    // Unordered lists
    else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (currentList !== 'ul') {
        closeList();
        html.push('<ul>');
        currentList = 'ul';
      }
      html.push(`<li>${trimmed.slice(2)}</li>`);
    }
    // Numbered lists
    else if (/^\d+\.\s+/.test(trimmed)) {
      if (currentList !== 'ol') {
        closeList();
        html.push('<ol>');
        currentList = 'ol';
      }
      const match = trimmed.match(/^\d+\.\s+(.+)$/);
      if (match) {
        html.push(`<li>${match[1]}</li>`);
      } else {
        html.push(`<li>${trimmed}</li>`);
      }
    }
    // Regular paragraphs
    else {
      closeList();
      html.push(`<p>${trimmed}</p>`);
    }
  }

  closeList();
  return html.join('\n');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ── Time Formatters ─────────────────────────────────────────────────────

function formatDuration(seconds) {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

function formatTimestamp(date) {
  return new Intl.DateTimeFormat('en', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  }).format(date);
}

// ── Number Formatters ───────────────────────────────────────────────────

function formatNumber(num) {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toString();
}

// ── Toast Notification System ───────────────────────────────────────────

const toastContainer = (() => {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  return container;
})();

function showToast(type, title, message, duration = 5000) {
  const icons = {
    success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
    error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
    warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
    info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
  };

  const colorClasses = {
    success: 'toast-success',
    error: 'toast-error',
    warning: 'toast-warning',
    info: 'toast-info',
  };

  const colorVars = {
    success: 'var(--color-success)',
    error: 'var(--color-danger)',
    warning: 'var(--color-warning)',
    info: 'var(--color-info)',
  };

  const toast = document.createElement('div');
  toast.className = `toast ${colorClasses[type] || 'toast-info'}`;
  toast.innerHTML = `
    <div class="toast-icon" style="color: ${colorVars[type] || colorVars.info}">
      ${icons[type] || icons.info}
    </div>
    <div class="toast-content">
      <div class="toast-title">${escapeHtml(title)}</div>
      ${message ? `<div class="toast-message">${escapeHtml(message)}</div>` : ''}
    </div>
    <button class="toast-close" onclick="this.closest('.toast').remove()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
    </button>
  `;

  toastContainer.appendChild(toast);

  if (duration > 0) {
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(20px)';
      toast.style.transition = 'all 300ms ease-out';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  return toast;
}

// ── Debounce / Throttle ─────────────────────────────────────────────────

function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

function throttle(fn, ms) {
  let last = 0;
  return (...args) => {
    const now = Date.now();
    if (now - last >= ms) {
      last = now;
      fn(...args);
    }
  };
}

// ── DOM Helpers ─────────────────────────────────────────────────────────

function $(selector, context = document) {
  return context.querySelector(selector);
}

function $$(selector, context = document) {
  return [...context.querySelectorAll(selector)];
}

function createElement(tag, attrs = {}, children = []) {
  const el = document.createElement(tag);
  for (const [key, val] of Object.entries(attrs)) {
    if (key === 'className') el.className = val;
    else if (key === 'innerHTML') el.innerHTML = val;
    else if (key === 'textContent') el.textContent = val;
    else if (key.startsWith('on')) el.addEventListener(key.slice(2).toLowerCase(), val);
    else el.setAttribute(key, val);
  }
  for (const child of children) {
    if (typeof child === 'string') el.appendChild(document.createTextNode(child));
    else if (child) el.appendChild(child);
  }
  return el;
}

// ── Auto-resize textarea ────────────────────────────────────────────────

function autoResize(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 160) + 'px';
}
