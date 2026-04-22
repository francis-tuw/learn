class HistoryManager {
  constructor() {
    this.emptyEl = document.getElementById('historyEmpty');
    this.listEl = document.getElementById('historyList');
    this.loaded = false;
    this.selectedIds = new Set();
    this.activeDropdown = null;
  }

  async loadHistory() {
    if (this.loaded) return;

    try {
      toast.info('正在加载历史记录...');
      const result = await api.getHistory();

      if (result.success && result.data && result.data.length > 0) {
        this.renderHistoryList(result.data);
      } else {
        this.renderEmptyState();
      }

      this.loaded = true;
    } catch (error) {
      console.error('加载历史记录失败:', error);
      toast.error('加载历史记录失败: ' + (error.message || '未知错误'));
      if (!this.listEl.innerHTML || this.listEl.children.length === 0) {
        this.renderEmptyState();
      }
    }
  }

  renderHistoryList(records) {
    if (!this.listEl) return;

    if (this.emptyEl) this.emptyEl.style.display = 'none';
    if (this.listEl) this.listEl.style.display = '';

    let html = `
      <div class="history-list-container">
        <div class="history-toolbar">
          <label class="select-all-wrapper">
            <input type="checkbox" id="selectAllHistory" />
            <span>全选</span>
          </label>
          <span class="selected-count" id="selectedCount" style="display:none;">
            已选择 <strong>0</strong> 条记录
          </span>
          <button class="btn btn-primary btn-sm" id="batchDownloadBtn" style="display:none;">
            📦 批量下载选中项
          </button>
          <button class="btn btn-outline btn-sm" id="refreshHistoryBtn">
            🔄 刷新
          </button>
        </div>

        <div class="history-list-header">
          <div class="col-checkbox"><input type="checkbox" id="headerCheckbox" /></div>
          <div class="col-file">文件名</div>
          <div class="col-time">执行时间</div>
          <div class="col-stat col-total">总检查</div>
          <div class="col-stat col-consistent">一致</div>
          <div class="col-stat col-inconsistent">不一致</div>
          <div class="col-actions">操作</div>
        </div>

        <div class="history-list-body">
    `;

    records.forEach((record) => {
      try {
        const fileName = record.mapping_file || '未知文件';
        const displayName = fileName.length > 35 ? fileName.substring(0, 35) + '...' : fileName;
        const formattedTime = DataTransformers.formatDate ? DataTransformers.formatDate(record.created_at) : record.created_at;
        const total = record.total_checks || 0;
        const consistent = record.consistent_count || 0;
        const inconsistent = record.inconsistent_count || 0;
        const inconsistentClass = inconsistent > 0 ? 'text-danger' : '';

        html += `
          <div class="history-row" data-id="${record.id}">
            <div class="col-checkbox">
              <input type="checkbox" class="row-checkbox" data-id="${record.id}" />
            </div>
            <div class="col-file">
              <span class="file-name" title="${DataTransformers.escapeHtml(fileName)}">📄 ${DataTransformers.escapeHtml(displayName)}</span>
            </div>
            <div class="col-time">🕐 ${DataTransformers.escapeHtml(formattedTime)}</div>
            <div class="col-stat col-total">${total}</div>
            <div class="col-stat col-consistent">${consistent}</div>
            <div class="col-stat col-inconsistent ${inconsistentClass}">${inconsistent}</div>
            <div class="col-actions">
              <div class="download-dropdown">
                <button class="btn btn-text btn-sm download-toggle" data-id="${record.id}">
                  ⬇️ 下载 ▾
                </button>
                <div class="download-menu" id="downloadMenu-${record.id}">
                  <button class="download-menu-item" data-id="${record.id}" data-type="sql">
                    📝 下载标注SQL (.sql)
                  </button>
                  <button class="download-menu-item" data-id="${record.id}" data-type="report">
                    📊 下载纠错报告
                  </button>
                </div>
              </div>
              <button class="btn btn-text btn-sm view-btn" data-id="${record.id}">📋 查看详情</button>
              <button class="btn btn-text btn-sm delete-btn text-danger" data-id="${record.id}">删除</button>
            </div>
          </div>
        `;
      } catch (e) {
        console.warn('渲染历史记录行异常:', e, record);
      }
    });

    html += `
        </div>
      </div>

      <style>
        .history-list-container { width: 100%; }
        .history-toolbar {
          display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
          padding: 12px 16px; background: var(--bg-secondary, #f5f5f5);
          border-radius: 8px; margin-bottom: 12px;
        }
        .select-all-wrapper { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 14px; color: var(--text-secondary); }
        .select-all-wrapper:hover { color: var(--text-primary); }
        .selected-count { color: var(--primary-color, #1890ff); font-size: 14px; }
        .history-list-header {
          display: grid; grid-template-columns: 40px 2fr 180px 80px minmax(70px,1fr) minmax(80px,1fr) 180px;
          gap: 8px; padding: 10px 16px; background: var(--bg-secondary);
          font-weight: 600; font-size: 13px; color: var(--text-secondary);
          border-radius: 6px 6px 0 0; border-bottom: 2px solid var(--border-color);
        }
        .history-row {
          display: grid; grid-template-columns: 40px 2fr 180px 80px minmax(70px,1fr) minmax(80px,1fr) 180px;
          gap: 8px; padding: 12px 16px; align-items: center;
          border-bottom: 1px solid var(--border-color);
          transition: background 0.2s;
        }
        .history-row:hover { background: var(--hover-bg, #fafafa); }
        .col-stat { text-align: center; font-weight: 600; font-size: 14px; }
        .col-total { color: var(--primary-color, #1890ff); }
        .col-consistent { color: var(--success-color, #52c41a); }
        .col-inconsistent {
          color: var(--error-color, #ff4d4f);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          min-width: 0;
        }
        .col-actions {
          display: flex; gap: 8px; justify-content: flex-end;
          white-space: nowrap;
          min-width: 0;
          position: relative;
        }
        .file-name {
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
          display: block; max-width: 100%; color: var(--text-primary);
          font-size: 14px;
        }
        .btn-text { background: none; border: none; padding: 4px 12px; cursor: pointer; font-size: 13px; border-radius: 4px; transition: all 0.2s; }
        .btn-text:hover { background: rgba(24,144,255,0.08); color: var(--primary-color); }
        .text-danger { color: var(--error-color, #ff4d4f); }
        .text-danger:hover { background: rgba(255,77,79,0.08); }
        .download-toggle:hover { background: rgba(82,196,26,0.08); color: var(--success-color, #52c41a); }
        .col-time { font-size: 13px; color: var(--text-secondary); }
        
        .download-dropdown { position: relative; }
        .download-menu {
          position: absolute;
          top: 100%;
          right: 0;
          background: var(--bg-primary, #fff);
          border: 1px solid var(--border-color, #e8e8e8);
          border-radius: 6px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
          min-width: 160px;
          z-index: 1000;
          display: none;
          padding: 4px 0;
        }
        .download-menu.show { display: block; }
        .download-menu-item {
          display: block;
          width: 100%;
          padding: 8px 16px;
          text-align: left;
          background: none;
          border: none;
          cursor: pointer;
          font-size: 13px;
          color: var(--text-primary);
          transition: background 0.2s;
        }
        .download-menu-item:hover {
          background: var(--hover-bg, #f5f5f5);
        }
      </style>
    `;

    this.listEl.innerHTML = html;

    this.bindEvents();
  }

  bindEvents() {
    const selectAllCb = document.getElementById('selectAllHistory');
    const headerCb = document.getElementById('headerCheckbox');

    if (selectAllCb) {
      selectAllCb.addEventListener('change', () => this.selectAll(selectAllCb.checked));
    }

    if (headerCb) {
      headerCb.addEventListener('change', () => this.selectAll(headerCb.checked));
    }

    this.listEl.querySelectorAll('.row-checkbox').forEach(cb => {
      cb.addEventListener('change', () => {
        this.toggleSelect(cb.dataset.id, cb.checked);
      });
    });

    this.listEl.querySelectorAll('.download-toggle').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleDownloadMenu(btn.dataset.id);
      });
    });

    this.listEl.querySelectorAll('.download-menu-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = item.dataset.id;
        const type = item.dataset.type;
        this.closeAllDropdowns();
        if (type === 'sql') {
          this.downloadAnnotatedSql(id);
        } else {
          this.downloadReport(id);
        }
      });
    });

    this.listEl.querySelectorAll('.view-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.viewResult(btn.dataset.id);
      });
    });

    this.listEl.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const row = btn.closest('.history-row');
        this.deleteRecord(btn.dataset.id, row);
      });
    });

    const batchBtn = document.getElementById('batchDownloadBtn');
    if (batchBtn) {
      batchBtn.addEventListener('click', () => this.batchDownload());
    }

    const refreshBtn = document.getElementById('refreshHistoryBtn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => this.refresh());
    }

    document.addEventListener('click', (e) => {
      if (!e.target.closest('.download-dropdown')) {
        this.closeAllDropdowns();
      }
    });
  }

  toggleDownloadMenu(id) {
    const menu = document.getElementById(`downloadMenu-${id}`);
    if (!menu) return;

    const isOpen = menu.classList.contains('show');
    this.closeAllDropdowns();

    if (!isOpen) {
      menu.classList.add('show');
      this.activeDropdown = id;
    }
  }

  closeAllDropdowns() {
    this.listEl.querySelectorAll('.download-menu').forEach(menu => {
      menu.classList.remove('show');
    });
    this.activeDropdown = null;
  }

  toggleSelect(id, isChecked) {
    if (isChecked) {
      this.selectedIds.add(id);
    } else {
      this.selectedIds.delete(id);
    }
    this.updateSelectionUI();
  }

  selectAll(checked) {
    const checkboxes = this.listEl.querySelectorAll('.row-checkbox');
    checkboxes.forEach((cb) => {
      cb.checked = checked;
      if (checked) {
        this.selectedIds.add(cb.dataset.id);
      } else {
        this.selectedIds.delete(cb.dataset.id);
      }
    });
    this.updateSelectionUI();
  }

  updateSelectionUI() {
    const count = this.selectedIds.size;
    const countEl = document.getElementById('selectedCount');
    const batchBtn = document.getElementById('batchDownloadBtn');

    if (count > 0) {
      if (countEl) {
        countEl.style.display = '';
        countEl.querySelector('strong').textContent = count;
      }
      if (batchBtn) {
        batchBtn.style.display = '';
        batchBtn.disabled = false;
      }
    } else {
      if (countEl) countEl.style.display = 'none';
      if (batchBtn) {
        batchBtn.style.display = 'none';
        batchBtn.disabled = true;
      }
    }

    const totalRows = this.listEl.querySelectorAll('.row-checkbox').length;
    const headerCb = document.getElementById('headerCheckbox');
    if (headerCb) {
      headerCb.checked = totalRows > 0 && count === totalRows;
      headerCb.indeterminate = count > 0 && count < totalRows;
    }
  }

  async batchDownload() {
    if (this.selectedIds.size === 0) {
      toast.warning('请先选择要下载的记录');
      return;
    }

    try {
      toast.info(`正在打包 ${this.selectedIds.size} 条记录...`);

      const ids = Array.from(this.selectedIds).join(',');
      await api.batchDownloadHistory(ids);

      toast.success('批量下载成功');
      this.clearSelection();

    } catch (error) {
      toast.error('批量下载失败: ' + error.message);
    }
  }

  clearSelection() {
    this.selectedIds.clear();
    this.listEl.querySelectorAll('.row-checkbox').forEach(cb => cb.checked = false);
    const headerCb = document.getElementById('headerCheckbox');
    if (headerCb) headerCb.checked = false;
    this.updateSelectionUI();
  }

  renderEmptyState() {
    if (this.emptyEl) this.emptyEl.style.display = '';
    if (this.listEl) this.listEl.style.display = 'none';
    this.loaded = false;
  }

  async downloadAnnotatedSql(id) {
    try {
      toast.info('正在准备下载标注SQL...');
      await api.downloadAnnotatedSql(id);
      toast.success('标注SQL下载成功');
    } catch (error) {
      console.error('下载标注SQL失败:', error);
      toast.error('下载失败: ' + error.message);
    }
  }

  async downloadReport(id) {
    try {
      toast.info('正在准备下载纠错报告...');
      await api.exportMarkdown(id);
      toast.success('纠错报告下载成功');
    } catch (error) {
      console.error('下载报告失败:', error);
      toast.error('下载失败: ' + error.message);
    }
  }

  async deleteRecord(id, rowEl) {
    const confirmed = await modal.confirm('确定要删除这条历史记录吗？删除后无法恢复。', {
      title: '确认删除',
      danger: true,
    });

    if (!confirmed) return;

    try {
      rowEl.style.opacity = '0.5';
      rowEl.style.pointerEvents = 'none';

      const result = await api.deleteHistory(id);

      if (result.success) {
        rowEl.remove();
        toast.success('记录已删除');

        this.invalidateCache();

        const remainingRows = this.listEl.querySelectorAll('.history-row');
        if (remainingRows.length === 0) {
          this.renderEmptyState();
        }
      } else {
        throw new Error(result.message || '删除失败');
      }
    } catch (error) {
      rowEl.style.opacity = '1';
      rowEl.style.pointerEvents = '';
      toast.error('删除失败: ' + error.message);
    }
  }

  async viewResult(id) {
    try {
      if (window.excelDetailModal) {
        await window.excelDetailModal.show(id);
      } else {
        toast.error('详情展示组件未加载');
      }
    } catch (error) {
      console.error('查看详情失败:', error);
      toast.error('加载详情失败: ' + error.message);
    }
  }

  invalidateCache() {
    this.loaded = false;
    this.selectedIds.clear();
  }

  async forceRefresh() {
    this.invalidateCache();
    await this.loadHistory();
  }

  refresh() {
    this.loaded = false;
    this.selectedIds.clear();
    this.loadHistory();
  }
}
