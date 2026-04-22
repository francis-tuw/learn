class SingleReviewFlowController {
  constructor() {
    this.pollTimer = null;
    this.currentTaskId = null;

    this.startBtn = document.getElementById('startReviewBtn');
    this.progressSection = document.getElementById('progressSection');
    this.resultSection = document.getElementById('resultSection');
    this.progressBar = document.getElementById('progressBar');
    this.progressPercentage = document.getElementById('progressPercentage');
    this.stepIndicator = document.getElementById('stepIndicator');

    if (this.startBtn) {
      this.startBtn.addEventListener('click', () => this.startReview());
    }

    appState.subscribe('files.mapping', () => this.updateButtonState());
    appState.subscribe('files.sql', () => this.updateButtonState());
  }

  validateInputs() {
    const state = appState.getState();

    if (!state.files.mapping) {
      toast.warning('请先上传IT-Mapping文件');
      return false;
    }

    if (!state.files.sql && !state.files.sqlContent) {
      toast.warning('请先上传SQL文件');
      return false;
    }

    return true;
  }

  async startReview() {
    if (!this.validateInputs()) return;

    const state = appState.getState();
    const mappingFile = state.files.mapping.file;
    const sqlContent = state.files.sqlContent || '';
    const businessContext = state.ui.businessContent || '';
    const detectedDialect = DataTransformers.detectSqlDialect(sqlContent);

    try {
      this.setLoading(true);
      this.resetResult();

      toast.info('正在提交纠错任务...');

      const response = await api.startReview({
        mapping_file: mappingFile.name,
        sql_content: sqlContent,
        business_context: businessContext,
        dialect: detectedDialect,
      });

      if (response.success && response.data) {
        this.currentTaskId = response.data.task_id;
        appState.setState('singleTask.taskId', this.currentTaskId);
        appState.setState('singleTask.status', 'running');

        toast.success(`任务已创建，开始执行纠错 (ID: ${this.currentTaskId.slice(0, 8)}...)`);
        this.showProgress();
        this.startPolling();
      } else {
        throw new Error(response.message || '任务创建失败');
      }
    } catch (error) {
      console.error('Start review error:', error);
      toast.error(error.message || '启动纠错失败，请重试');
      this.setLoading(false);
    }
  }

  async startPolling() {
    if (this.pollTimer) clearInterval(this.pollTimer);

    this.pollTimer = setInterval(async () => {
      await this.checkProgress();
    }, 2000);

    await this.checkProgress();
  }

  async checkProgress() {
    if (!this.currentTaskId) return;

    try {
      const result = await api.getProgress(this.currentTaskId);

      if (result.success && result.data) {
        const { status, progress, current_step } = result.data;

        appState.setState('singleTask.status', status);
        appState.setState('singleTask.progress', progress);
        appState.setState('singleTask.currentStep', current_step);

        this.updateProgressUI(progress, current_step);

        if (status === 'completed') {
          this.onComplete();
        } else if (status === 'error') {
          this.onError(result.data.error || '任务执行出错');
        }
      }
    } catch (error) {
      console.error('Poll progress error:', error);
    }
  }

  updateProgressUI(progress, step) {
    if (this.progressBar) this.progressBar.style.width = `${progress}%`;
    if (this.progressPercentage) this.progressPercentage.textContent = `${progress}%`;

    if (this.stepIndicator) {
      const steps = this.stepIndicator.querySelectorAll('.step');
      const stepOrder = ['parsing', 'agents', 'done'];
      const currentIndex = stepOrder.indexOf(step);

      steps.forEach((stepEl, index) => {
        stepEl.classList.remove('active', 'completed');
        if (index < currentIndex) {
          stepEl.classList.add('completed');
        } else if (index === currentIndex) {
          stepEl.classList.add('active');
        }
      });
    }
  }

  onComplete() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }

    toast.success('纠错完成！正在加载结果...');
    this.loadResult();
  }

  async loadResult() {
    if (!this.currentTaskId) return;

    try {
      const result = await api.getResult(this.currentTaskId);

      if (result.success && result.data) {
        const formattedData = DataTransformers.formatResultForDisplay(result.data);
        appState.setState('singleTask.result', formattedData);
        appState.setState('singleTask.status', 'done');

        this.renderResult(formattedData);

        if (window.app && window.app.historyManager) {
          window.app.historyManager.invalidateCache();
          const historyTab = document.getElementById('historyTab') || document.querySelector('[data-tab="history"]');
          if (historyTab && historyTab.classList.contains('active')) {
            window.app.historyManager.forceRefresh();
          }
        }

        this.setLoading(false);
      } else {
        throw new Error(result.message || '获取结果失败');
      }
    } catch (error) {
      console.error('Load result error:', error);
      toast.error(error.message || '加载结果失败');
      this.resultSection.style.display = '';
      document.getElementById('resultSummary').innerHTML = `
        <div style="text-align:center;padding:40px;background:var(--error-bg);border-radius:8px;">
          <div style="font-size:48px;margin-bottom:16px;">⚠️</div>
          <h3 style="color:var(--error-color);">结果加载失败</h3>
          <p style="color:var(--text-secondary);">${error.message}</p>
          <button onclick="app.reviewFlow.loadResult()" style="margin-top:16px;padding:8px 24px;background:var(--primary-color);color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:14px;">
            重试
          </button>
        </div>
      `;
      this.setLoading(false);
    }
  }

  renderResult(data) {
    if (!data) return;

    this.renderQualityWarning(data);
    this.renderSummary(data.summary);
    if (data.raw_response) {
      this.renderRawResponse(data.raw_response);
    }
    this.renderFindings(data.findings);

    const hasFindings = data.findings && data.findings.length > 0;
    const exportToolbar = document.getElementById('exportToolbar');
    if (exportToolbar) {
      exportToolbar.style.display = hasFindings ? 'flex' : 'none';
      this.renderUnannotatedButton(data, exportToolbar);
    }
  }

  renderQualityWarning(data) {
    const resultSection = document.getElementById('resultSection');
    if (!resultSection) return;

    const qualityScore = data.summary?.quality_score;

    if (qualityScore !== undefined && qualityScore > 0 && qualityScore < 60) {
      const warningBanner = `
        <div class="quality-warning-banner" id="qualityWarningBanner" style="background:#fff9c4;color:#f57f17;padding:12px 16px;border-left:4px solid #fbc02d;border-radius:4px;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;">
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:18px;">⚠️</span>
                <span style="font-weight:500;">AI结果质量评分: ${qualityScore}分(满分100),建议重新审查</span>
            </div>
            <button onclick="document.getElementById('qualityWarningBanner').remove()" style="background:none;border:none;color:#f57f17;font-size:18px;cursor:pointer;padding:0 4px;">✕</button>
        </div>
      `;
      resultSection.insertAdjacentHTML('afterbegin', warningBanner);
    }
  }

  renderUnannotatedButton(data, exportToolbar) {
    if (!exportToolbar) return;

    const unannotatedCount = data.unannotated_findings?.length || 0;
    window.currentResultData = data;

    if (unannotatedCount > 0) {
      const unannotatedBtn = `
        <button class="btn btn-warning" id="viewUnannotatedBtn" onclick="showUnannotatedModal()">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
            </svg>
            查看未标注项(${unannotatedCount})
        </button>
      `;
      exportToolbar.insertAdjacentHTML('beforeend', unannotatedBtn);
    }
  }

  renderRawResponse(rawResponse) {
    const summaryEl = document.getElementById('resultSummary');
    if (!summaryEl) return;

    const details = document.createElement('details');
    details.style.cssText = 'margin-top:16px;border:1px dashed var(--border-color);padding:12px;border-radius:4px;';
    details.innerHTML = `
      <summary style="cursor:pointer;color:var(--text-secondary);font-size:14px;">
        📋 查看AI原始响应（调试信息）
      </summary>
      <pre style="margin-top:8px;white-space:pre-wrap;word-break:break-all;font-size:12px;color:var(--text-disabled);background:var(--bg-secondary);padding:12px;border-radius:4px;overflow:auto;max-height:400px;">
        ${DataTransformers.escapeHtml(rawResponse)}
      </pre>
    `;
    summaryEl.appendChild(details);
  }

  renderSummary(summary) {
    const summaryEl = document.getElementById('resultSummary');
    if (!summaryEl) return;

    const avgConfidence = summary.avgConfidence || 0;
    const statusDistribution = summary.statusDistribution || {};
    const strategy = summary.strategy || 'unknown';

    const strategyLabel = strategy === 'triple_agent_voting' ? '三Agent投票策略' : '双Agent模式';
    const confidenceHtml = avgConfidence > 0 ? `
      <div class="summary-stat">
        <span class="summary-stat-value ${avgConfidence >= 0.67 ? 'success' : avgConfidence >= 0.33 ? 'warning' : 'error'}">${DataTransformers.formatConfidence(avgConfidence)}</span>
        <span class="summary-stat-label">平均置信度</span>
      </div>
    ` : '';

    const warningCount = statusDistribution.warning || 0;
    const errorCount = statusDistribution.error || 0;
    const needsReviewHtml = (warningCount > 0 || errorCount > 0) ? `
      <div class="summary-stat">
        <span class="summary-stat-value warning">${warningCount + errorCount}</span>
        <span class="summary-stat-label">需人工复核</span>
      </div>
    ` : '';

    summaryEl.innerHTML = `
      <div class="summary-direction-notice" style="background:#e3f2fd;border-left:4px solid #2196f3;padding:12px;border-radius:4px;color:#1565c0;font-size:14px;margin-bottom:16px;">
        📌 本审查以IT-Mapping定义为基准，检查SQL实现是否符合规范
      </div>
      <div class="summary-header" style="margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;">
        <span style="font-size:14px;color:var(--text-secondary);">检查策略: <strong style="color:var(--primary-color);">${strategyLabel}</strong></span>
      </div>
      <div class="summary-grid">
        <div class="summary-stat">
          <span class="summary-stat-value primary">${DataTransformers.formatNumber(summary.totalChecks)}</span>
          <span class="summary-stat-label">总检查项</span>
        </div>
        <div class="summary-stat">
          <span class="summary-stat-value success">${DataTransformers.formatNumber(summary.consistentCount)}</span>
          <span class="summary-stat-label">一致项</span>
        </div>
        <div class="summary-stat">
          <span class="summary-stat-value error">${DataTransformers.formatNumber(summary.inconsistentCount)}</span>
          <span class="summary-stat-label">不一致项</span>
        </div>
        ${needsReviewHtml}
        <div class="summary-stat" style="display:flex;align-items:center;justify-content:center;">
          <div class="pass-rate-circle" style="--percent:${summary.passRate}">
            <div class="pass-rate-content">
              <span class="pass-rate-value">${summary.passRate}%</span>
              <span class="pass-rate-label">通过率</span>
            </div>
          </div>
        </div>
        ${confidenceHtml}
        <div class="summary-stat">
          <span class="summary-stat-value primary">${DataTransformers.formatDuration(summary.duration)}</span>
          <span class="summary-stat-label">审查耗时</span>
        </div>
      </div>
    `;
  }

  renderFindings(findings) {
    const listEl = document.getElementById('findingsList');
    if (!listEl) return;

    listEl.innerHTML = '';

    if (!findings || findings.length === 0) {
      listEl.innerHTML = `
        <div style="text-align:center;padding:40px;">
          <div style="font-size:48px;margin-bottom:16px;">✅</div>
          <h3 style="color:var(--text-primary);margin-bottom:8px;">AI分析完成</h3>
          <p style="color:var(--text-disabled);">未发现明显的不一致项</p>
          <p style="color:var(--text-secondary);font-size:14px;margin-top:16px;">
            SQL脚本与IT-Mapping规范基本一致
          </p>
        </div>
      `;
      return;
    }

    findings.forEach((finding) => {
      const card = new FindingCard(finding);
      listEl.appendChild(card.getElement());
    });
  }

  showExportToolbar(show) {
    const toolbar = document.getElementById('exportToolbar');
    if (toolbar) toolbar.style.display = show ? '' : 'none';
  }

  onError(errorMessage) {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }

    toast.error(`纠错出错: ${errorMessage}`);
    this.setLoading(false);
  }

  setLoading(loading) {
    if (loading) {
      if (this.startBtn) this.startBtn.disabled = true;
      this.showProgress();
    } else {
      this.updateButtonState();
    }
  }

  showProgress() {
    if (this.progressSection) this.progressSection.style.display = '';
    if (this.resultSection) this.resultSection.style.display = 'none';
  }

  resetResult() {
    if (this.progressSection) this.progressSection.style.display = 'none';
    if (this.resultSection) this.resultSection.style.display = 'none';

    if (this.progressBar) this.progressBar.style.width = '0%';
    if (this.progressPercentage) this.progressPercentage.textContent = '0%';

    if (this.stepIndicator) {
      const steps = this.stepIndicator.querySelectorAll('.step');
      steps.forEach((s) => s.classList.remove('active', 'completed'));
      if (steps[0]) steps[0].classList.add('active');
    }
  }

  updateButtonState() {
    const state = appState.getState();
    const hasMapping = !!state.files.mapping;
    const hasSql = !!(state.files.sql || state.files.sqlContent);
    const isRunning = state.singleTask.status === 'running';

    if (this.startBtn) {
      this.startBtn.disabled = !(hasMapping && hasSql) || isRunning;
    }
  }

  async loadResultById(taskId) {
    try {
      console.log(`[ReviewFlow] 加载历史任务结果: ${taskId}`);
      console.time(`[ReviewFlow] 加载耗时-${taskId}`);

      if (this.resultSection) {
        this.resultSection.style.display = '';
      }

      const summaryEl = document.getElementById('resultSummary');
      if (summaryEl) {
        summaryEl.innerHTML = '<div style="text-align:center;padding:40px;"><div class="loading-spinner"></div><p style="margin-top:16px;color:var(--text-secondary);">正在加载历史记录...</p></div>';
      }

      const findingsList = document.getElementById('findingsList');
      if (findingsList) findingsList.innerHTML = '';

      const exportToolbar = document.getElementById('exportToolbar');
      if (exportToolbar) exportToolbar.style.display = 'none';

      appState.setState('singleTask.taskId', taskId);
      this.currentTaskId = taskId;

      const result = await api.getResult(taskId);

      console.log(`[ReviewFlow] API响应:`, result);

      if (!result.success) {
        throw new Error(result.message || result.error || '获取结果失败');
      }

      const rawData = result.data;

      console.log(`[ReviewFlow] 原始数据:`, rawData);

      if (!rawData) {
        throw new Error('返回数据为空');
      }

      const validatedData = this.validateAndAdaptData(rawData);

      console.log(`[ReviewFlow] 适配后数据:`, validatedData);

      const formattedData = DataTransformers.formatResultForDisplay(validatedData);

      if (!formattedData) {
        throw new Error('数据格式化失败');
      }

      console.log(`[ReviewFlow] 格式化后数据:`, formattedData);

      appState.setState('singleTask.result', formattedData);
      appState.setState('singleTask.status', 'done');

      this.renderResult(formattedData);

      console.timeEnd(`[ReviewFlow] 加载耗时-${taskId}`);
      toast.success('历史记录加载成功');

    } catch (error) {
      console.error('[ReviewFlow] 加载历史结果失败:', error);
      console.error('[ReviewFlow] 错误详情:', {
        message: error.message,
        stack: error.stack,
        taskId: taskId
      });

      const summaryEl = document.getElementById('resultSummary');
      if (summaryEl) {
        const errorMessage = error.message || '未知错误';
        const isNetworkError = errorMessage.includes('网络') || errorMessage.includes('timeout') || errorMessage.includes('Failed to fetch');
        const isDataError = errorMessage.includes('数据') || errorMessage.includes('格式化') || errorMessage.includes('为空');

        let userFriendlyMessage = errorMessage;
        let suggestion = '请检查网络连接后重试';

        if (isDataError) {
          suggestion = '该记录可能已损坏或不完整';
        } else if (errorMessage.includes('任务不存在')) {
          suggestion = '该任务可能已被清理或过期';
        }

        summaryEl.innerHTML = `
          <div style="text-align:center;padding:40px;background:var(--error-bg);border-radius:8px;">
            <div style="font-size:48px;margin-bottom:16px;">⚠️</div>
            <h3 style="color:var(--error-color);">加载失败</h3>
            <p style="color:var(--text-secondary);margin-bottom:8px;">${DataTransformers.escapeHtml(userFriendlyMessage)}</p>
            <p style="color:var(--text-disabled);font-size:13px;margin-bottom:16px;">${suggestion}</p>
            <button onclick="app.reviewFlow.loadResultById('${taskId}')" style="margin-top:16px;padding:8px 24px;background:var(--primary-color);color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:14px;">
              重试
            </button>
          </div>
        `;
      }

      toast.error(`加载失败: ${error.message}`);
    }
  }

  validateAndAdaptData(rawData) {
    console.log('[ReviewFlow] 开始数据验证和适配...');

    const adaptedData = { ...rawData };

    if (typeof adaptedData.findings === 'string') {
      console.log('[ReviewFlow] 检测到 findings 为字符串，尝试解析 JSON...');
      try {
        adaptedData.findings = JSON.parse(adaptedData.findings);
        console.log('[ReviewFlow] findings 解析成功，数量:', adaptedData.findings.length);
      } catch (parseError) {
        console.warn('[ReviewFlow] findings JSON 解析失败:', parseError.message);
        adaptedData.findings = [];
      }
    }

    if (!Array.isArray(adaptedData.findings)) {
      console.warn('[ReviewFlow] findings 不是数组，设置为空数组');
      adaptedData.findings = [];
    }

    adaptedData.findings = adaptedData.findings.map((finding, index) => {
      if (!finding || typeof finding !== 'object') {
        console.warn(`[ReviewFlow] findings[${index}] 无效，跳过`);
        return null;
      }

      const status = finding.status || 'inconsistent';
      let severity = finding.severity || 'low';

      if (status === 'warning') {
        severity = finding.severity || 'medium';
      } else if (status === 'error') {
        severity = finding.severity || 'critical';
      }

      return {
        id: finding.id || `finding_${Date.now()}_${index}`,
        severity: severity,
        type: finding.type || '其他',
        issue: finding.issue || finding.description || '未提供问题描述',
        suggestion: finding.suggestion || finding.recommendation || '',
        location: finding.location || finding.line_number ? `第${finding.line_number}行` : null,
        original_sql: finding.original_sql || finding.sql || '',
        corrected_sql: finding.corrected_sql || '',
        agent_type: finding.agent_type || finding.source || '',
        confidence: finding.confidence || 0.8,
        vote_details: finding.vote_details || null,
        agent_results: finding.agent_results || null,
        status: status,
        ...finding
      };
    }).filter(f => f !== null);

    const summary = adaptedData.summary || {};
    adaptedData.total_checks = parseInt(adaptedData.total_checks || summary.total_checks) || adaptedData.findings.length || 0;
    adaptedData.consistent_count = parseInt(adaptedData.consistent_count || summary.consistent_count) || 0;
    adaptedData.inconsistent_count = parseInt(adaptedData.inconsistent_count || summary.inconsistent_count) || adaptedData.findings.length || 0;
    adaptedData.duration = parseFloat(adaptedData.duration || summary.duration) || 0;
    adaptedData.agents_count = parseInt(adaptedData.agents_count || summary.agent_count) || 7;

    if (summary.avg_confidence !== undefined) {
      adaptedData.avg_confidence = summary.avg_confidence;
    }
    if (summary.status_distribution) {
      adaptedData.status_distribution = summary.status_distribution;
    }
    if (summary.strategy) {
      adaptedData.strategy = summary.strategy;
    }

    if (adaptedData.total_checks === 0 && adaptedData.findings.length > 0) {
      adaptedData.total_checks = adaptedData.findings.length;
      console.log('[ReviewFlow] 自动计算 total_checks:', adaptedData.total_checks);
    }

    if (adaptedData.total_checks > 0 && adaptedData.consistent_count === 0 && adaptedData.inconsistent_count === 0) {
      const statusDist = { consistent: 0, inconsistent: 0, warning: 0, error: 0 };
      adaptedData.findings.forEach(f => {
        const s = f.status || 'inconsistent';
        if (statusDist.hasOwnProperty(s)) {
          statusDist[s]++;
        }
      });
      adaptedData.consistent_count = statusDist.consistent;
      adaptedData.inconsistent_count = statusDist.inconsistent + statusDist.warning + statusDist.error;
      adaptedData.status_distribution = statusDist;
      console.log('[ReviewFlow] 自动拆分统计:', {
        consistent: adaptedData.consistent_count,
        inconsistent: adaptedData.inconsistent_count,
        statusDist
      });
    }

    console.log('[ReviewFlow] 数据验证完成:', {
      hasFindings: adaptedData.findings.length > 0,
      findingsCount: adaptedData.findings.length,
      totalChecks: adaptedData.total_checks,
      consistent: adaptedData.consistent_count,
      inconsistent: adaptedData.inconsistent_count,
      avgConfidence: adaptedData.avg_confidence,
      strategy: adaptedData.strategy
    });

    return adaptedData;
  }

  destroy() {
    if (this.pollTimer) clearInterval(this.pollTimer);
  }
}

window.showUnannotatedModal = function() {
  const unannotatedFindings = window.currentResultData?.unannotated_findings || [];

  if (unannotatedFindings.length === 0) {
    Toast.show('info', '所有项均已成功标注');
    return;
  }

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  let tableRows = unannotatedFindings.map(f => `
    <tr>
      <td style="padding:8px 12px;border:1px solid #e3f2fd;color:#1565c0;font-weight:500;">#${f.id}</td>
      <td style="padding:8px 12px;border:1px solid #e3f2fd;color:#424242;">${escapeHtml(f.issue || '未指定')}</td>
      <td style="padding:8px 12px;border:1px solid #e3f2fd;color:#424242;font-family:monospace;font-size:12px;">${escapeHtml((f.original_sql || '无').substring(0, 80))}</td>
      <td style="padding:8px 12px;border:1px solid #e3f2fd;color:#424242;">${escapeHtml(f.location || '未知')}</td>
    </tr>
  `).join('');

  const modalContent = `
    <div style="margin-bottom:16px;">
      <h3 style="margin:0 0 12px 0;color:#d32f2f;">⚠️ 未成功标注项列表（共${unannotatedFindings.length}项）</h3>
      <p style="color:#666;font-size:13px;margin:0 0 16px 0;">以下finding无法自动定位到具体SQL代码行，建议人工检查</p>
    </div>
    <table style="width:100%;border-collapse:collapse;border:1px solid #bbdefb;border-radius:6px;overflow:hidden;">
      <thead>
        <tr style="background:#bbdefb;">
          <th style="padding:10px 12px;text-align:left;font-size:13px;color:#0d47a1;border:1px solid #90caf9;">ID</th>
          <th style="padding:10px 12px;text-align:left;font-size:13px;color:#0d47a1;border:1px solid #90caf9;">问题描述</th>
          <th style="padding:10px 12px;text-align:left;font-size:13px;color:#0d47a1;border:1px solid #90caf9;">原始SQL片段</th>
          <th style="padding:10px 12px;text-align:left;font-size:13px;color:#0d47a1;border:1px solid #90caf9;">声明位置</th>
        </tr>
      </thead>
      <tbody>
        ${tableRows}
      </tbody>
    </table>
  `;

  modal.show('未标注项详情', modalContent, { width: '800px' });
};
