class Modal {
  constructor() {
    this.overlay = document.getElementById('modalOverlay');
    this.modal = document.getElementById('modal');
    this.isOpen = false;
  }

  show(options = {}) {
    const { title = '提示', content, footer, width, onClose } = options;

    this.onCloseCallback = onClose;

    if (width) {
      this.modal.style.minWidth = width;
    }

    let footerHtml = '';
    if (footer === undefined) {
      footerHtml = `
        <div class="modal-footer">
          <button class="btn btn-primary" id="modalConfirmBtn">确定</button>
          <button class="btn btn-outline" id="modalCancelBtn">取消</button>
        </div>
      `;
    } else if (footer) {
      footerHtml = `<div class="modal-footer">${footer}</div>`;
    }

    this.modal.innerHTML = `
      <div class="modal-header">
        <h3 class="modal-title">${DataTransformers.escapeHtml(title)}</h3>
        <button class="modal-close" id="modalCloseBtn">✕</button>
      </div>
      <div class="modal-body">${typeof content === 'string' ? content : ''}</div>
      ${footerHtml}
    `;

    if (typeof content !== 'string' && content instanceof HTMLElement) {
      const body = this.modal.querySelector('.modal-body');
      body.appendChild(content);
    }

    this.overlay.style.display = 'block';
    this.modal.style.display = 'block';
    this.isOpen = true;

    document.body.style.overflow = 'hidden';

    this.bindEvents();
  }

  confirm(message, options = {}) {
    return new Promise((resolve) => {
      this.show({
        title: options.title || '确认操作',
        content: `<p style="font-size:14px;line-height:1.6;">${DataTransformers.escapeHtml(message)}</p>`,
        footer: `
          <div class="modal-footer">
            <button class="btn btn-${options.danger ? 'danger' : 'primary'}" data-action="confirm">${options.confirmText || '确定'}</button>
            <button class="btn btn-outline" data-action="cancel">${options.cancelText || '取消'}</button>
          </div>
        `,
        onClose: (action) => resolve(action === 'confirm'),
      });
    });
  }

  alert(message, options = {}) {
    return new Promise((resolve) => {
      this.show({
        title: options.title || '提示',
        content: `<p style="font-size:14px;line-height:1.6;">${DataTransformers.escapeHtml(message)}</p>`,
        footer: `
          <div class="modal-footer">
            <button class="btn btn-primary" data-action="confirm">确定</button>
          </div>
        `,
        onClose: () => resolve(true),
      });
    });
  }

  bindEvents() {
    const closeBtn = this.modal.querySelector('#modalCloseBtn');
    const cancelBtn = this.modal.querySelector('#modalCancelBtn');
    const confirmBtn = this.modal.querySelector('#modalConfirmBtn');

    if (closeBtn) closeBtn.onclick = () => this.close('cancel');
    if (cancelBtn) cancelBtn.onclick = () => this.close('cancel');
    if (confirmBtn) confirmBtn.onclick = () => this.close('confirm');

    this.modal.querySelectorAll('[data-action]').forEach((btn) => {
      btn.onclick = () => this.close(btn.dataset.action);
    });

    this.overlay.onclick = (e) => {
      if (e.target === this.overlay) this.close('overlay');
    };

    document.addEventListener('keydown', this.handleEsc);
  }

  handleEsc = (e) => {
    if (e.key === 'Escape' && this.isOpen) {
      this.close('esc');
    }
  };

  close(action = 'close') {
    if (!this.isOpen) return;

    this.modal.style.animation = 'modalOut 0.2s ease forwards';
    setTimeout(() => {
      this.overlay.style.display = 'none';
      this.modal.style.display = 'none';
      this.modal.style.animation = '';
      this.modal.innerHTML = '';
      this.isOpen = false;
      document.body.style.overflow = '';
      document.removeEventListener('keydown', this.handleEsc);

      if (this.onCloseCallback) {
        try {
          this.onCloseCallback(action);
        } catch (e) {
          console.error('Modal close callback error:', e);
        }
      }
    }, 200);
  }
}

const modal = new Modal();
window.modal = modal;
