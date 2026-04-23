class App {
  constructor() {
    this.mappingUploader = null;
    this.sqlUploader = null;
    this.reviewFlow = null;
    this.statusPollTimer = null;
    this.historyManager = null;

    this.init();
  }

  init() {
    this.initMappingUploader();
    this.initSqlUploader();
    this.initReviewFlow();
    this.initTabs();
    this.initBusinessInput();
    this.initFilters();
    this.initExportButtons();
    this.initBatchMode();
    this.initHistoryManager();
    this.initOllamaStatusClick();
    this.startStatusPolling();

    console.log('SQL智能纠错系统初始化完成');
  }

  initMappingUploader() {
    this.mappingUploader = new MappingUploader();
  }

  initSqlUploader() {
    const sqlZone = document.getElementById('sqlUploadZone');
    const sqlFileInput = document.getElementById('sqlFileInput');
    const sqlPreview = document.getElementById('sqlPreview');
    const sqlFilename = document.getElementById('sqlFilename');
    const sqlDetails = document.getElementById('sqlDetails');
    const sqlCodePreview = document.getElementById('sqlCodePreview');

    if (!sqlZone || !sqlFileInput) return;

    this.sqlUploadZone = new UploadZone({
      zone: sqlZone,
      fileInput: sqlFileInput,
      accept: '.sql,.txt',
      maxSize: 50 * 1024 * 1024,
      onFileSelected: (file) => this.handleSqlFileSelected(file),
    });

    const removeBtn = document.getElementById('sqlRemoveBtn');
    if (removeBtn) {
      removeBtn.addEventListener('click', () => this.removeSqlFile());
    }
  }

  handleSqlFileSelected(file) {
    const reader = new FileReader();

    reader.onload = (e) => {
      const content = e.target.result;
      const dialect = DataTransformers.detectSqlDialect(content);

      appState.setState('files.sql', file);
      appState.setState('files.sqlContent', content);
      appState.setState('files.sqlFilename', file.name);

      this.showSqlPreview(file.name, content, dialect);
      toast.success(`SQL文件 "${file.name}" 已加载 (${DataTransformers.formatFileSize(file.size)})`);
    };

    reader.onerror = () => {
      toast.error('读取文件失败，请重试');
    };

    reader.readAsText(file, 'UTF-8');
  }

  showSqlPreview(filename, content, dialect) {
    const preview = document.getElementById('sqlPreview');
    const filenameEl = document.getElementById('sqlFilename');
    const detailsEl = document.getElementById('sqlDetails');
    const codeEl = document.getElementById('sqlCodePreview');
    const zone = document.getElementById('sqlUploadZone');

    if (zone) zone.style.display = 'none';
    if (preview) preview.style.display = 'block';

    if (filenameEl) filenameEl.textContent = filename;

    if (detailsEl) {
      const lines = content.split('\n').length;
      const chars = content.length;

      detailsEl.innerHTML = `
        <div class="detail-item">
          <span class="detail-label">方言</span>
          <span class="detail-value">${dialect}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">行数</span>
          <span class="detail-value">${lines} 行</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">字符数</span>
          <span class="detail-value">${chars.toLocaleString()}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">大小</span>
          <span class="detail-value">${DataTransformers.formatFileSize(appState.getState().files.sql?.size || 0)}</span>
        </div>
      `;
    }

    if (codeEl) {
      let highlightedContent;
      try {
        highlightedContent = window.hljs ? hljs.highlight(content, { language: 'sql' }).value : DataTransformers.escapeHtml(content);
      } catch (e) {
        highlightedContent = DataTransformers.escapeHtml(content);
      }

      codeEl.innerHTML = `<pre><code class="language-sql">${highlightedContent}</code></pre>`;
    }
  }

  removeSqlFile() {
    appState.setState('files.sql', null);
    appState.setState('files.sqlContent', '');
    appState.setState('files.sqlFilename', '');

    const preview = document.getElementById('sqlPreview');
    const zone = document.getElementById('sqlUploadZone');

    if (preview) preview.style.display = 'none';
    if (zone) zone.style.display = '';

    if (this.sqlUploadZone) this.sqlUploadZone.reset();
    toast.info('已移除SQL文件');
  }

  initReviewFlow() {
    this.reviewFlow = new SingleReviewFlowController();
  }

  initTabs() {
    const tabNav = document.getElementById('tabNav');
    if (!tabNav) return;

    const tabBtns = tabNav.querySelectorAll('.tab-btn');

    tabBtns.forEach((btn) => {
      btn.addEventListener('click', () => {
        const targetTab = btn.dataset.tab;
        this.switchTab(targetTab);
      });
    });
  }

  switchTab(tabName) {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabBtns.forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    tabPanes.forEach((pane) => {
      pane.style.display = pane.id === `${tabName}Tab` ? '' : 'none';
    });

    appState.setState('ui.activeTab', tabName);
    appState.setState('currentMode', tabName);

    if (tabName === 'history' && this.historyManager) {
      this.historyManager.loadHistory();
    }
  }

  initBusinessInput() {
    const toggle = document.getElementById('businessToggle');
    const wrapper = document.getElementById('businessInputWrapper');
    const textarea = document.getElementById('businessInput');
    const charCount = document.getElementById('charCount');

    if (!toggle || !wrapper) return;

    toggle.addEventListener('click', () => {
      const isExpanded = wrapper.style.display !== 'none';
      wrapper.style.display = isExpanded ? 'none' : '';
      toggle.classList.toggle('expanded', !isExpanded);
      appState.setState('ui.businessExpanded', !isExpanded);
    });

    if (textarea && charCount) {
      textarea.addEventListener('input', () => {
        charCount.textContent = textarea.value.length;
        appState.setState('ui.businessContent', textarea.value);
      });
    }
  }

  initFilters() {
    const typeFilter = document.getElementById('typeFilter');
    const statusFilter = document.getElementById('statusFilter');
    const searchInput = document.getElementById('searchInput');

    if (typeFilter) {
      typeFilter.addEventListener('change', () => this.applyFilters());
    }

    if (statusFilter) {
      statusFilter.addEventListener('change', () => this.applyFilters());
    }

    if (searchInput) {
      let debounceTimer;
      searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => this.applyFilters(), 300);
      });
    }
  }

  applyFilters() {
    const typeFilter = document.getElementById('typeFilter')?.value || 'all';
    const statusFilter = document.getElementById('statusFilter')?.value || 'all';
    const searchText = document.getElementById('searchInput')?.value.toLowerCase() || '';

    appState.setState('ui.findingsFilter.type', typeFilter);
    appState.setState('ui.findingsFilter.status', statusFilter);
    appState.setState('ui.findingsFilter.search', searchText);

    const result = appState.getState().singleTask.result;
    if (!result || !result.findings) return;

    let filteredFindings = result.findings.filter((f) => {
      if (typeFilter !== 'all' && f.typeLabel !== typeFilter) return false;
      if (statusFilter !== 'all' && f.status !== statusFilter) return false;
      if (
        searchText &&
        !(f.issue?.toLowerCase().includes(searchText) ||
          f.explanation?.toLowerCase().includes(searchText))
      ) {
        return false;
      }
      return true;
    });

    this.renderFilteredFindings(filteredFindings);
  }

  renderFilteredFindings(findings) {
    const listEl = document.getElementById('findingsList');
    if (!listEl) return;

    listEl.innerHTML = '';

    if (!findings || findings.length === 0) {
      listEl.innerHTML =
        '<div style="text-align:center;padding:40px;color:var(--text-disabled);">没有匹配的结果</div>';
      return;
    }

    findings.forEach((finding) => {
      const card = new FindingCard(finding);
      listEl.appendChild(card.getElement());
    });
  }

  initExportButtons() {
    const downloadReportBtn = document.getElementById('downloadReportBtn');
    const downloadSqlBtn = document.getElementById('downloadSqlBtn');
    const downloadExcelBtn = document.getElementById('downloadExcelBtn');

    if (downloadReportBtn) {
      downloadReportBtn.addEventListener('click', async () => {
        const taskId = appState.getState().singleTask.taskId;
        if (!taskId) {
          toast.warning('没有可下载的报告');
          return;
        }

        try {
          toast.info('正在生成纠错报告...');
          await api.downloadReport(taskId);
          toast.success('纠错报告下载成功');
        } catch (error) {
          toast.error(error.message || '下载失败');
        }
      });
    }

    if (downloadSqlBtn) {
      downloadSqlBtn.addEventListener('click', async () => {
        const taskId = appState.getState().singleTask.taskId;
        if (!taskId) {
          toast.warning('没有可下载的标注SQL');
          return;
        }

        try {
          toast.info('正在生成标注SQL...');
          await api.downloadAnnotatedSql(taskId);
          toast.success('标注SQL下载成功');
        } catch (error) {
          toast.error(error.message || '下载失败');
        }
      });
    }

    if (downloadExcelBtn) {
      downloadExcelBtn.addEventListener('click', async () => {
        const taskId = appState.getState().singleTask.taskId;
        if (!taskId) {
          toast.warning('没有可下载的Excel结果');
          return;
        }

        try {
          toast.info('正在生成Excel结果...');
          await api.downloadExcelReport(taskId);
          toast.success('Excel结果下载成功');
        } catch (error) {
          toast.error(error.message || '下载失败');
        }
      });
    }
  }

  initHistoryManager() {
    this.historyManager = new HistoryManager();
    console.log('✅ HistoryManager 初始化完成');
  }

  initBatchMode() {
    const batchUploadZone = document.getElementById('batchUploadZone');
    const batchFileInput = document.getElementById('batchFileInput');
    const startBatchBtn = document.getElementById('startBatchBtn');
    const pauseBatchBtn = document.getElementById('pauseBatchBtn');
    const cancelBatchBtn = document.getElementById('cancelBatchBtn');
    const batchExportBtn = document.getElementById('batchExportBtn');

    if (batchUploadZone && batchFileInput) {
      batchUploadZone.addEventListener('click', () => batchFileInput.click());

      batchUploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        batchUploadZone.classList.add('dragover');
      });

      batchUploadZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        batchUploadZone.classList.remove('dragover');
      });

      batchUploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        batchUploadZone.classList.remove('dragover');
        this.handleBatchFilesDrop(e.dataTransfer.files);
      });

      batchFileInput.addEventListener('change', (e) => {
        this.handleBatchFilesSelect(e.target.files);
      });
    }

    if (startBatchBtn) {
      startBatchBtn.addEventListener('click', () => this.handleStartBatch());
    }

    if (pauseBatchBtn) {
      pauseBatchBtn.addEventListener('click', () => this.handlePauseBatch());
    }

    if (cancelBatchBtn) {
      cancelBatchBtn.addEventListener('click', () => this.handleCancelBatch());
    }

    if (batchExportBtn) {
      batchExportBtn.addEventListener('click', () => this.handleBatchExport());
    }

    const autoPairBtn = document.getElementById('autoPairBtn');
    if (autoPairBtn) {
      autoPairBtn.addEventListener('click', () => this.autoPairFiles());
    }

    const clearPairsBtn = document.getElementById('clearPairsBtn');
    if (clearPairsBtn) {
      clearPairsBtn.addEventListener('click', () => this.clearPairsList());
    }
  }

  handleBatchFilesDrop(files) {
    this.processBatchFiles(Array.from(files));
  }

  handleBatchFilesSelect(files) {
    this.processBatchFiles(Array.from(files));
  }

  processBatchFiles(files) {
    const xlsxFiles = files.filter((f) => f.name.endsWith('.xlsx'));
    const sqlFiles = files.filter((f) => f.name.endsWith('.sql') || f.name.endsWith('.txt'));

    if (xlsxFiles.length === 0 && sqlFiles.length === 0) {
      toast.warning('未检测到有效的文件（需要 .xlsx 和 .sql/.txt 文件）');
      return;
    }

    this.batchFiles = this.batchFiles || [];
    this.batchFiles.push(...files);
    this.renderFilePairsList();
    toast.info(`已添加 ${files.length} 个文件`);
  }

  renderFilePairsList() {
    const listContainer = document.getElementById('filePairsList');
    const pairsGrid = document.getElementById('pairsGrid');
    const startBatchBtn = document.getElementById('startBatchBtn');

    if (!listContainer || !pairsGrid) return;

    if (!this.batchFiles || this.batchFiles.length === 0) {
      listContainer.style.display = 'none';
      if (startBatchBtn) startBatchBtn.disabled = true;
      return;
    }

    listContainer.style.display = '';
    if (startBatchBtn) startBatchBtn.disabled = false;

    pairsGrid.innerHTML = this.batchFiles
      .map(
        (file, index) => `
        <div class="file-pair-item" data-index="${index}">
          <div class="file-pair-files">
            <span class="file-pair-label">${file.name.endsWith('.xlsx') ? 'IT-Mapping' : 'SQL'}</span>
            <span class="file-pair-name">${DataTransformers.escapeHtml(file.name)}</span>
            <span style="font-size:12px;color:var(--text-disabled);">${DataTransformers.formatFileSize(file.size)}</span>
          </div>
          <button class="file-pair-remove" data-index="${index}">✕</button>
        </div>
      `
      )
      .join('');

    pairsGrid.querySelectorAll('.file-pair-remove').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const index = parseInt(btn.dataset.index);
        this.batchFiles.splice(index, 1);
        this.renderFilePairsList();
      });
    });
  }

  autoPairFiles() {
    toast.info('自动配对功能待实现');
  }

  clearPairsList() {
    this.batchFiles = [];
    this.renderFilePairsList();
    toast.info('已清空文件列表');
  }

  async handleStartBatch() {
    if (!this.batchFiles || this.batchFiles.length === 0) {
      toast.warning('请先添加文件');
      return;
    }

    try {
      toast.info('正在提交批量任务...');

      const result = await api.batchUpload();

      if (result.success && result.data) {
        const batchId = result.data.batchId || result.data.batch_id;
        appState.setState('batchTask.batchId', batchId);

        await api.startBatch(batchId);

        batchProgressManager.connect(batchId);
        batchProgressManager.showPanel();

        toast.success(`批量任务已启动 (ID: ${batchId.slice(0, 8)}...)`);
      } else {
        throw new Error(result.message || '批量任务创建失败');
      }
    } catch (error) {
      console.error('Batch start error:', error);
      toast.error(error.message || '启动批量任务失败');
    }
  }

  async handlePauseBatch() {
    const batchId = appState.getState().batchTask.batchId;
    if (!batchId) return;

    try {
      await api.pauseBatch(batchId);
      toast.info('批量任务已暂停');
    } catch (error) {
      toast.error(error.message || '暂停失败');
    }
  }

  async handleCancelBatch() {
    const confirmed = await modal.confirm('确定要取消剩余的批量任务吗？已完成的任务不受影响。', {
      title: '确认取消',
      danger: true,
    });

    if (!confirmed) return;

    const batchId = appState.getState().batchTask.batchId;
    if (!batchId) return;

    try {
      await api.cancelBatch(batchId);
      batchProgressManager.reset();
      batchProgressManager.hidePanel();
      toast.warning('剩余任务已取消');
    } catch (error) {
      toast.error(error.message || '取消失败');
    }
  }

  async handleBatchExport() {
    const batchId = appState.getState().batchTask.batchId;
    if (!batchId) return;

    try {
      toast.info('正在打包全部报告...');
      await api.batchExport(batchId);
      toast.success('批量报告下载成功');
    } catch (error) {
      toast.error(error.message || '导出失败');
    }
  }

  async checkOllamaStatus() {
    try {
      const result = await api.getStatus();

      if (result.success && result.data) {
        const isConnected = result.data.ollama_connected;
        const modelName = result.data.model_name;
        const status = result.data.status;

        this.updateOllamaStatusUI(isConnected, modelName, status);

        appState.setState('system.ollamaConnected', isConnected);
        appState.setState('system.modelName', modelName);
        appState.setState('system.status', status);

        console.log(`[Status Check] Ollama ${isConnected ? '已连接' : '未连接'} - Model: ${modelName || 'N/A'}`);
      }
    } catch (error) {
      console.warn('[Status Check] 检查失败:', error);
      this.updateOllamaStatusUI(false, null, 'error');
    }
  }

  updateOllamaStatusUI(isConnected, modelName, status) {
    const indicator = document.getElementById('ollamaStatus');
    if (!indicator) return;

    const dot = indicator.querySelector('.status-dot');
    const text = indicator.querySelector('.status-text');

    if (dot) {
      if (status === 'error') {
        dot.className = 'status-dot status-error';
      } else {
        dot.className = `status-dot ${isConnected ? 'status-online' : 'status-offline'}`;
      }
    }

    if (text) {
      if (isConnected) {
        text.textContent = modelName ? `Ollama已连接 (${modelName})` : 'Ollama已连接';
      } else if (status === 'error') {
        text.textContent = 'Ollama连接异常';
      } else {
        text.textContent = 'Ollama未连接';
      }
    }

    console.log(`[UI Update] Status: ${status}, Connected: ${isConnected}`);
  }

  startStatusPolling() {
    this.checkOllamaStatus();

    this.statusPollTimer = setInterval(() => {
      this.checkOllamaStatus();
    }, 30000);
  }

  initOllamaStatusClick() {
    const statusIndicator = document.getElementById('ollamaStatus');
    if (!statusIndicator) return;

    statusIndicator.style.cursor = 'pointer';
    statusIndicator.addEventListener('click', () => this.openOllamaConfigModal());
  }

  async openOllamaConfigModal() {
    let config;
    try {
      const timestamp = Date.now();
      console.log(`📥 [${new Date().toLocaleTimeString()}] 正在从服务器加载Ollama配置... (t=${timestamp})`);
      const result = await api.get(`/api/ollama/config?t=${timestamp}`);
      config = result.success ? result.data : {};
      console.log('✅ 从服务器加载的配置:', JSON.stringify(config, null, 2));
    } catch (error) {
      console.error('❌ 加载配置失败:', error);
      toast.error('加载配置失败，使用默认值');
      config = {
        host: 'http://localhost:11434',
        model: 'qwen2.5:7b',
        timeout: 30,
        auto_connect: true
      };
    }

    const content = document.createElement('div');
    content.innerHTML = `
      <div class="ollama-config-form">
        <div class="form-group">
          <label class="form-label" for="ollamaHost">
            Ollama服务地址
            <span class="form-hint">Ollama API服务器的URL</span>
          </label>
          <input type="text" id="ollamaHost" class="form-input" value="${DataTransformers.escapeHtml(config.host || 'http://localhost:11434')}" placeholder="http://localhost:11434" />
        </div>

        <div class="form-group">
          <label class="form-label" for="ollamaModel">
            模型名称
            <span class="form-hint">点击"测试连接"后可从可用模型中选择</span>
          </label>
          <select id="ollamaModel" class="form-input form-select-model">
            <option value="${DataTransformers.escapeHtml(config.model || 'qwen2.5:7b')}" selected>
              ${DataTransformers.escapeHtml(config.model || 'qwen2.5:7b')} (当前配置)
            </option>
            <option value="" disabled>━━━ 请先测试连接获取模型列表 ━━━</option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label" for="ollamaTimeout">
            超时时间（秒）
            <span class="form-hint">请求超时时间，建议10-60秒</span>
          </label>
          <input type="number" id="ollamaTimeout" class="form-input" value="${config.timeout || 30}" min="5" max="120" />
        </div>

        <div class="form-group">
          <label class="checkbox-label">
            <input type="checkbox" id="ollamaAutoConnect" ${config.auto_connect !== false ? 'checked' : ''} />
            <span>启动时自动连接Ollama</span>
          </label>
        </div>

        <div class="config-actions">
          <button class="btn btn-outline" id="testConnectionBtn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22,4 12,14.01 9,11.01"/>
            </svg>
            测试连接
          </button>
        </div>

        <div id="connectionTestResult" class="connection-test-result" style="display:none;"></div>
      </div>
    `;

    modal.show({
      title: 'Ollama配置',
      content: content,
      width: '500px',
      footer: `
        <div class="modal-footer">
          <button class="btn btn-outline" data-action="cancel">取消</button>
          <button class="btn btn-primary" data-action="confirm" id="saveOllamaConfigBtn">保存配置</button>
        </div>
      `,
      onClose: async (action) => {
        if (action === 'confirm') {
          await this.saveOllamaConfig();
        }
      }
    });

    this.bindOllamaConfigEvents();
  }

  bindOllamaConfigEvents() {
    const testBtn = document.getElementById('testConnectionBtn');

    if (testBtn) {
      testBtn.addEventListener('click', () => this.testOllamaConnection());
    }

    const saveBtn = document.getElementById('saveOllamaConfigBtn');
    if (saveBtn) {
      saveBtn.addEventListener('click', () => {
        const host = document.getElementById('ollamaHost')?.value || 'http://localhost:11434';
        const model = document.getElementById('ollamaModel')?.value || 'qwen2.5:7b';
        const timeout = parseInt(document.getElementById('ollamaTimeout')?.value || '30');
        const autoConnect = document.getElementById('ollamaAutoConnect')?.checked || false;

        this.pendingConfigData = { host: host.trim(), model, timeout, auto_connect: autoConnect };
        modal.close('confirm');
      });
    }
  }

  updateModelSelect(models) {
    const modelSelect = document.getElementById('ollamaModel');
    if (!modelSelect || !models || models.length === 0) return;

    const currentValue = modelSelect.value;

    modelSelect.innerHTML = '';

    models.forEach((model, index) => {
      const option = document.createElement('option');
      option.value = model;
      option.textContent = model;
      if (model === currentValue || (index === 0 && !models.includes(currentValue))) {
        option.selected = true;
      }
      modelSelect.appendChild(option);
    });

    if (currentValue && !models.includes(currentValue)) {
      const defaultOption = document.createElement('option');
      defaultOption.value = currentValue;
      defaultOption.textContent = `${currentValue} (当前配置，但未在服务器上找到)`;
      defaultOption.style.color = 'var(--warning-color)';
      modelSelect.insertBefore(defaultOption, modelSelect.firstChild);
      defaultOption.selected = true;
    }

    toast.info(`已加载 ${models.length} 个可用模型`);
  }

  async testOllamaConnection() {
    const testBtn = document.getElementById('testConnectionBtn');
    const resultDiv = document.getElementById('connectionTestResult');

    if (!testBtn || !resultDiv) return;

    const host = document.getElementById('ollamaHost')?.value || 'http://localhost:11434';
    const timeout = parseInt(document.getElementById('ollamaTimeout')?.value || '30');

    testBtn.disabled = true;
    testBtn.innerHTML = `
      <div class="loading-spinner" style="width:14px;height:14px;border-width:2px;"></div>
      测试中...
    `;
    resultDiv.style.display = 'block';
    resultDiv.className = 'connection-test-result testing';
    resultDiv.innerHTML = '<span>正在连接到Ollama服务器...</span>';

    try {
      const result = await api.testOllamaConnection({ host, timeout });

      if (result.success) {
        resultDiv.className = 'connection-test-result success';
        const models = result.data?.models || [];
        let modelsList = '';

        if (models.length > 0) {
          this.updateModelSelect(models);
          modelsList = `<div class="available-models"><strong>已加载 ${models.length} 个可用模型，请从下拉列表中选择</strong></div>`;
        }

        resultDiv.innerHTML = `
          <div class="success-icon">✓</div>
          <div>
            <strong>${result.message}</strong>
            ${modelsList}
          </div>
        `;
        toast.success(result.message);
      } else {
        throw new Error(result.message);
      }
    } catch (error) {
      resultDiv.className = 'connection-test-result error';
      resultDiv.innerHTML = `
        <div class="error-icon">✕</div>
        <div><strong>连接失败</strong><br/>${error.message}</div>
      `;
      toast.error(error.message);
    } finally {
      testBtn.disabled = false;
      testBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
          <polyline points="22,4 12,14.01 9,11.01"/>
        </svg>
        测试连接
      `;
    }
  }

  async saveOllamaConfig() {
    const config = this.pendingConfigData || {
      host: document.getElementById('ollamaHost')?.value || 'http://localhost:11434',
      model: document.getElementById('ollamaModel')?.value || 'qwen2.5:7b',
      timeout: parseInt(document.getElementById('ollamaTimeout')?.value || '30'),
      auto_connect: document.getElementById('ollamaAutoConnect')?.checked || false
    };

    if (!config.host.trim()) {
      toast.error('请输入Ollama服务地址');
      return false;
    }

    console.log('📤 准备保存Ollama配置:', JSON.stringify(config, null, 2));

    try {
      toast.info('⏳ 正在保存配置到服务器...');

      const result = await api.updateOllamaConfig(config);

      console.log('📥 服务器响应:', JSON.stringify(result, null, 2));

      if (result.success) {
        toast.success('✅ 配置已成功保存！\n地址: ' + config.host);
        appState.setState('system.ollamaConfig', config);
        this.pendingConfigData = null;
        this.checkOllamaStatus();
        return true;
      } else {
        throw new Error(result.message || '服务器返回失败');
      }
    } catch (error) {
      console.error('❌ 保存配置失败详情:', error);
      toast.error('❌ 保存失败: ' + (error.message || '网络错误或服务器无响应'));
      return false;
    }
  }

  destroy() {
    if (this.statusPollTimer) clearInterval(this.statusPollTimer);
    if (this.mappingUploader) this.mappingUploader.destroy();
    if (this.reviewFlow) this.reviewFlow.destroy();
    if (this.sqlUploadZone) this.sqlUploadZone.destroy();
    batchProgressManager.disconnect();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.app = new App();
});
