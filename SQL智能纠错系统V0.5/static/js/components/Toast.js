class Toast {
  constructor() {
    this.container = document.getElementById('toastContainer');
    this.toasts = new Map();
    this.maxToasts = 5;
  }

  show(message, options = {}) {
    const { type = 'info', title, duration = 4000, closable = true } = options;

    if (this.toasts.size >= this.maxToasts) {
      const oldestKey = this.toasts.keys().next().value;
      this.dismiss(oldestKey);
    }

    const id = Date.now() + Math.random();
    const icons = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'ℹ',
    };

    const toastEl = document.createElement('div');
    toastEl.className = `toast toast-${type}`;
    toastEl.dataset.toastId = id;
    toastEl.innerHTML = `
      <span class="toast-icon">${icons[type] || icons.info}</span>
      <div class="toast-content">
        ${title ? `<div class="toast-title">${DataTransformers.escapeHtml(title)}</div>` : ''}
        <div class="toast-message">${DataTransformers.escapeHtml(message)}</div>
      </div>
      ${closable ? '<button class="toast-close" onclick="toast.dismiss(this.closest(\'.toast\').dataset.toastId)">✕</button>' : ''}
    `;

    this.container.appendChild(toastEl);
    this.toasts.set(id, { element: toastEl, timer: null });

    if (duration > 0) {
      const timer = setTimeout(() => this.dismiss(id), duration);
      this.toasts.get(id).timer = timer;
    }

    return id;
  }

  success(message, options = {}) {
    return this.show(message, { ...options, type: 'success' });
  }

  error(message, options = {}) {
    return this.show(message, { ...options, type: 'error', duration: 6000 });
  }

  warning(message, options = {}) {
    return this.show(message, { ...options, type: 'warning' });
  }

  info(message, options = {}) {
    return this.show(message, { ...options, type: 'info' });
  }

  dismiss(id) {
    const toastData = this.toasts.get(id);
    if (!toastData) return;

    if (toastData.timer) clearTimeout(toastData.timer);

    const el = toastData.element;
    el.classList.add('toast-exit');

    setTimeout(() => {
      if (el.parentNode) el.parentNode.removeChild(el);
      this.toasts.delete(id);
    }, 300);
  }

  clear() {
    for (const [id] of this.toasts) {
      this.dismiss(id);
    }
  }
}

const toast = new Toast();
window.toast = toast;
