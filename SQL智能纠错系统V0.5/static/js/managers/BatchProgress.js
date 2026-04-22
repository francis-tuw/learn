class BatchProgressManager {
  constructor() {
    this.eventSource = null;
    this.batchId = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectDelay = 3000;

    this.pairListEl = document.getElementById('pairStatusList');
    this.totalEl = document.getElementById('totalPairs');
    this.completedEl = document.getElementById('completedPairs');
    this.runningEl = document.getElementById('runningPairs');
    this.waitingEl = document.getElementById('waitingPairs');
    this.errorEl = document.getElementById('errorPairs');
    this.progressPercentEl = document.getElementById('batchProgressPercent');
    this.progressBarEl = document.getElementById('batchProgressBar');

    appState.subscribe('batchTask.stats', () => this.updateStatsUI());
    appState.subscribe('batchTask.pairStates', () => this.updatePairListUI());
  }

  connect(batchId) {
    this.disconnect();
    this.batchId = batchId;
    this.reconnectAttempts = 0;

    try {
      this.eventSource = new EventSource(`/api/batch/progress/${batchId}`);

      this.eventSource.addEventListener('progress', (e) => this.handleProgress(e));
      this.eventSource.addEventListener('pair_complete', (e) => this.handlePairComplete(e));
      this.eventSource.addEventListener('pair_error', (e) => this.handlePairError(e));
      this.eventSource.addEventListener('batch_complete', (e) => this.handleBatchComplete(e));

      this.eventSource.onerror = (e) => this.handleError(e);

      toast.info(`已连接到批量任务进度流`);
    } catch (error) {
      console.error('SSE connection error:', error);
      toast.error('无法建立实时连接，将使用轮询模式');
      this.startPollingFallback();
    }
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    this.batchId = null;
  }

  handleProgress(event) {
    try {
      const data = JSON.parse(event.data);
      const { pair_id, status, progress } = data;

      appState.updatePairState(pair_id, { status, progress });

      if (status === 'parsing' || status === 'agents') {
        this.reconnectAttempts = 0;
      }
    } catch (e) {
      console.error('Progress event parse error:', e);
    }
  }

  handlePairComplete(event) {
    try {
      const data = JSON.parse(event.data);
      const { pair_id, findings_count } = data;

      appState.updatePairState(pair_id, { status: 'done', findingsCount: findings_count });
      toast.success(`文件对 #${pair_id.slice(0, 8)} 纠错完成，发现 ${findings_count} 个问题`);
    } catch (e) {
      console.error('Pair complete event parse error:', e);
    }
  }

  handlePairError(event) {
    try {
      const data = JSON.parse(event.data);
      const { pair_id, error } = data;

      appState.updatePairState(pair_id, { status: 'error', errorMessage: error });
      toast.error(`文件对执行出错: ${error}`);
    } catch (e) {
      console.error('Pair error event parse error:', e);
    }
  }

  handleBatchComplete(event) {
    try {
      const data = JSON.parse(event.data);
      const { total_pairs, completed, errors } = data;

      toast.success(
        `批量纠错完成！共处理 ${total_pairs} 个文件对，成功 ${completed} 个${errors > 0 ? `，异常 ${errors} 个` : ''}`
      );

      this.disconnect();

      document.getElementById('batchExportBtn').disabled = false;
    } catch (e) {
      console.error('Batch complete event parse error:', e);
    }
  }

  handleError(event) {
    console.warn('SSE connection error:', event);

    if (this.eventSource && this.eventSource.readyState === EventSource.CLOSED) {
      return;
    }

    this.reconnectAttempts++;

    if (this.reconnectAttempts <= this.maxReconnectAttempts && this.batchId) {
      const delay = Math.min(this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1), 30000);
      toast.warning(`连接中断，${Math.round(delay / 1000)}秒后重连... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

      setTimeout(() => {
        if (this.batchId) {
          this.connect(this.batchId);
        }
      }, delay);
    } else {
      toast.error('无法重新连接，请刷新页面或检查网络状态');
      this.disconnect();
    }
  }

  startPollingFallback() {
    if (!this.batchId) return;

    let pollCount = 0;
    const pollInterval = setInterval(async () => {
      if (!this.batchId) {
        clearInterval(pollInterval);
        return;
      }

      try {
        const response = await fetch(`/api/batch/progress/${this.batchId}`);
        if (!response.ok) throw new Error('Poll failed');

        const data = await response.json();

        if (data.pairs) {
          for (const pair of data.pairs) {
            appState.updatePairState(pair.id, {
              status: pair.status,
              progress: pair.progress,
            });
          }
        }

        if (data.status === 'completed') {
          clearInterval(pollInterval);
          this.handleBatchComplete({ data: JSON.stringify(data.summary || {}) });
        }

        pollCount++;
        if (pollCount % 10 === 0) {
          console.log(`Batch polling: ${pollCount} requests sent`);
        }
      } catch (error) {
        console.error('Batch polling error:', error);
      }
    }, 2000);
  }

  updateStatsUI() {
    const stats = appState.getState().batchTask.stats;

    if (this.totalEl) this.totalEl.textContent = stats.total;
    if (this.completedEl) this.completedEl.textContent = stats.completed;
    if (this.runningEl) this.runningEl.textContent = stats.running;
    if (this.waitingEl) this.waitingEl.textContent = stats.waiting;
    if (this.errorEl) this.errorEl.textContent = stats.errors;

    const total = stats.total || 1;
    const completed = stats.completed || 0;
    const percent = Math.round((completed / total) * 100);

    if (this.progressPercentEl) this.progressPercentEl.textContent = `${percent}%`;
    if (this.progressBarEl) this.progressBarEl.style.width = `${percent}%`;

    const exportBtn = document.getElementById('batchExportBtn');
    if (exportBtn) {
      exportBtn.disabled = completed === 0;
    }
  }

  updatePairListUI() {
    if (!this.pairListEl) return;

    const pairStates = Object.values(appState.getState().batchTask.pairStates);

    if (pairStates.length === 0) {
      this.pairListEl.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-disabled);">暂无文件对</div>';
      return;
    }

    this.pairListEl.innerHTML = pairStates
      .map((pair) => {
        const statusClass = DataTransformers.getStatusClass(pair.status);
        const statusLabel = DataTransformers.getStatusLabel(pair.status);
        const progress = pair.progress || 0;

        return `
          <div class="pair-status-card">
            <span class="pair-status-indicator ${statusClass}" title="${statusLabel}"></span>
            <div class="pair-info">
              <div class="pair-filenames">${DataTransformers.escapeHtml(pair.mappingFile || pair.sqlFile || pair.id?.slice(0, 12))}</div>
              <div class="pair-progress-mini">
                <div class="pair-progress-bar" style="width:${progress}%"></div>
              </div>
            </div>
            <span style="font-size:12px;color:var(--text-secondary);min-width:50px;text-align:right;">${statusLabel}</span>
            ${progress > 0 ? `<span style="font-size:12px;color:var(--primary-color);min-width:40px;text-align:right;">${progress}%</span>` : ''}
          </div>
        `;
      })
      .join('');
  }

  showPanel() {
    const panel = document.getElementById('batchProgressPanel');
    if (panel) panel.style.display = '';
  }

  hidePanel() {
    const panel = document.getElementById('batchProgressPanel');
    if (panel) panel.style.display = 'none';
  }

  reset() {
    this.disconnect();
    appState.resetBatchTask();
    this.updateStatsUI();
    this.updatePairListUI();
  }
}

const batchProgressManager = new BatchProgressManager();
