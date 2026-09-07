/**
 * Theme + offline auth overlay (login / create-account).
 */

const THEME_KEY = 'mr-theme';

function getStoredTheme() {
  try {
    return localStorage.getItem(THEME_KEY) === 'light' ? 'light' : 'dark';
  } catch {
    return 'dark';
  }
}

function applyTheme(theme) {
  const next = theme === 'light' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch {
    /* ignore quota / private mode */
  }
  $$('.theme-icon-dark').forEach((el) => {
    el.style.display = next === 'dark' ? '' : 'none';
  });
  $$('.theme-icon-light').forEach((el) => {
    el.style.display = next === 'light' ? '' : 'none';
  });
}

function toggleTheme() {
  applyTheme(getStoredTheme() === 'dark' ? 'light' : 'dark');
}

const authManager = {
  user: null,
  allowRegister: false,

  show(allowRegister) {
    this.allowRegister = !!allowRegister;
    const overlay = $('#auth-overlay');
    const switchEl = $('#login-switch');
    overlay?.classList.remove('hidden');
    if (switchEl) switchEl.classList.toggle('hidden', !this.allowRegister);
    this.showLogin();
    $('#login-username')?.focus();
  },

  hide() {
    $('#auth-overlay')?.classList.add('hidden');
  },

  showLogin() {
    $('#auth-login-panel')?.classList.remove('hidden');
    $('#auth-register-panel')?.classList.add('hidden');
    const err = $('#login-error');
    if (err) err.textContent = '';
  },

  showRegister() {
    if (!this.allowRegister) return;
    $('#auth-login-panel')?.classList.add('hidden');
    $('#auth-register-panel')?.classList.remove('hidden');
    const err = $('#register-error');
    if (err) err.textContent = '';
    $('#register-username')?.focus();
  },

  renderUser() {
    const row = $('#sidebar-user');
    const name = $('#sidebar-user-name');
    if (!row) return;
    if (this.user && this.user.username && this.user.username !== 'anonymous') {
      row.classList.remove('hidden');
      if (name) name.textContent = this.user.username;
    } else {
      row.classList.add('hidden');
    }
  },

  async boot() {
    try {
      const status = await api.getAuthStatus();
      window.__AUTH_ENABLED__ = !!status.enabled;
      this.allowRegister = !!status.allow_register;
      if (!status.enabled) {
        this.hide();
        this.user = null;
        this.renderUser();
        return true;
      }
      if (api.token) {
        try {
          this.user = await api.getMe();
          this.hide();
          this.renderUser();
          return true;
        } catch {
          api.setToken('');
        }
      }
      this.show(status.allow_register);
      this.renderUser();
      return false;
    } catch {
      this.hide();
      return true;
    }
  },

  async login(username, password) {
    const err = $('#login-error');
    if (err) err.textContent = '';
    const res = await api.login(username, password);
    api.setToken(res.access_token);
    this.user = res.user;
    this.hide();
    this.renderUser();
    return res.user;
  },

  async register(username, password) {
    const err = $('#register-error');
    if (err) err.textContent = '';
    const res = await api.register(username, password);
    api.setToken(res.access_token);
    this.user = res.user;
    this.hide();
    this.renderUser();
    return res.user;
  },

  logout() {
    api.setToken('');
    this.user = null;
    this.renderUser();
    this.boot();
  },

  bind() {
    $('#theme-toggle-btn')?.addEventListener('click', toggleTheme);
    $('#auth-theme-toggle-btn')?.addEventListener('click', toggleTheme);
    applyTheme(getStoredTheme());

    $('#show-register-btn')?.addEventListener('click', () => this.showRegister());
    $('#show-login-btn')?.addEventListener('click', () => this.showLogin());
    $('#logout-btn')?.addEventListener('click', () => this.logout());

    $('#login-form')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = $('#login-username')?.value.trim();
      const password = $('#login-password')?.value;
      const btn = $('#login-submit');
      if (btn) btn.disabled = true;
      try {
        await this.login(username, password);
        document.dispatchEvent(new CustomEvent('auth-ready'));
      } catch (err) {
        const box = $('#login-error');
        if (box) box.textContent = err.message || 'Sign in failed';
      } finally {
        if (btn) btn.disabled = false;
      }
    });

    $('#register-form')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const username = $('#register-username')?.value.trim();
      const password = $('#register-password')?.value;
      const btn = $('#register-submit');
      if (btn) btn.disabled = true;
      try {
        await this.register(username, password);
        document.dispatchEvent(new CustomEvent('auth-ready'));
      } catch (err) {
        const box = $('#register-error');
        if (box) box.textContent = err.message || 'Could not create account';
      } finally {
        if (btn) btn.disabled = false;
      }
    });

    document.addEventListener('auth-required', () => {
      api.setToken('');
      this.user = null;
      this.renderUser();
      this.show(this.allowRegister);
    });
  },
};

const lightbox = {
  open(src) {
    const overlay = $('#image-lightbox');
    const img = $('#lightbox-img');
    if (!overlay || !img || !src) return;
    img.src = src;
    overlay.classList.remove('hidden');
  },
  close() {
    const overlay = $('#image-lightbox');
    const img = $('#lightbox-img');
    overlay?.classList.add('hidden');
    if (img) img.removeAttribute('src');
  },
  bind() {
    const overlay = $('#image-lightbox');
    overlay?.addEventListener('click', (e) => {
      if (e.target === overlay) this.close();
    });
    $('#lightbox-close-btn')?.addEventListener('click', () => this.close());
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && overlay && !overlay.classList.contains('hidden')) {
        this.close();
      }
    });
  },
};
