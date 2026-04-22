class FindingCard {
  constructor(finding, options = {}) {
    this.finding = finding;
    this.options = options;
    this.isExpanded = false;
    this.element = this.render();
  }

  getSeverityIcon(severity) {
    const icons = {
      critical: '🔴',
      high: '🟠',
      medium: '🟡',
      low: '🔵',
    };
    return icons[severity] || '⚪';
  }

  getSeverityText(severity) {
    const labels = {
      critical: '严重',
      high: '高',
      medium: '中',
      low: '低',
    };
    return labels[severity] || '未知';
  }

  getStatusBadge(finding) {
    const status = finding.status || 'inconsistent';
    const statusConfig = {
      consistent: { icon: '✅', text: '一致', bg: '#e8f5e9', color: '#2e7d32', border: '#a5d6a7' },
      inconsistent: { icon: '❌', text: '不一致', bg: '#ffebee', color: '#c62828', border: '#ef9a9a' },
      warning: { icon: '⚠️', text: '需人工复核', bg: '#fff8e1', color: '#f57f17', border: '#ffe082' },
      error: { icon: '🔴', text: '检查失败', bg: '#fce4ec', color: '#c62828', border: '#f48fb1' },
    };
    return statusConfig[status] || statusConfig.inconsistent;
  }

  getTypeLabelStyle(type) {
    /* 支持11种typeLabel样式（原5种，差异补充文档新增6种）：映射检查/JOIN逻辑/NULL处理/数据转换/聚合窗口/方言兼容/业务规则/注释规范/映射一致性/解析异常/非标准格式 */
    const styleMap = {
      '映射检查': { bg: '#e3f2fd', color: '#1565c0', border: '#90caf9' },
      'JOIN逻辑': { bg: '#f3e5f5', color: '#6a1b9a', border: '#ce93d8' },
      'NULL处理': { bg: '#fff3e0', color: '#e65100', border: '#ffcc80' },
      '数据转换': { bg: '#fce4ec', color: '#c62828', border: '#f48fb1' },
      '聚合窗口': { bg: '#e8f5e9', color: '#2e7d32', border: '#a5d6a7' },
      '方言兼容': { bg: '#f5f5f5', color: '#616161', border: '#bdbdbd' },
      '业务规则': { bg: '#fff8e1', color: '#f57f17', border: '#ffe082' },
      '注释规范': { bg: '#e0f7fa', color: '#00838f', border: '#80deea' },
      '映射一致性': { bg: '#e3f2fd', color: '#1565c0', border: '#90caf9' },
      '解析异常': { bg: '#fbe9e7', color: '#bf360c', border: '#ffab91' },
      '非标准格式': { bg: '#f3e5f5', color: '#6a1b9a', border: '#ce93d8' },
    };
    return styleMap[type] || { bg: '#fafafa', color: '#424242', border: '#e0e0e0' };
  }

  checkLanguageWarning() {
    const issue = this.finding.issue || '';
    if (!issue) return false;

    const englishChars = issue.replace(/[^a-zA-Z]/g, '').length;
    const totalChars = issue.replace(/\s/g, '').length;

    if (totalChars === 0) return false;

    const englishRatio = (englishChars / totalChars) * 100;
    return englishRatio > 70;
  }

  highlightLineNumber(location) {
    if (!location) return '';

    const patterns = [
      /第\s*(\d+)\s*行/g,
      /Line\s+(\d+)/gi,
      /L(\d+)/gi
    ];

    let highlighted = location;
    for (const pattern of patterns) {
      highlighted = highlighted.replace(pattern, '<strong style="color:#d32f2f;font-weight:bold;">$&</strong>');
    }

    return highlighted;
  }

  render() {
    const card = document.createElement('div');
    const statusClass = this.finding.status || 'inconsistent';
    card.className = `finding-card ${statusClass} finding-card-enter`;
    card.dataset.findingId = this.finding.id;

    const severityClass = DataTransformers.getSeverityClass(this.finding.severity);
    const severityIcon = this.getSeverityIcon(this.finding.severity);
    const severityText = this.getSeverityText(this.finding.severity);
    const typeLabel = this.finding.typeLabel || this.finding.type || '其他';
    const typeStyle = this.getTypeLabelStyle(typeLabel);
    const statusBadge = this.getStatusBadge(this.finding);

    const voteDetailsHtml = this.renderVoteDetailsBadge();
    const confidenceHtml = this.renderConfidenceBadge();

    card.innerHTML = `
      <div class="finding-card-header" role="button" tabindex="0" aria-expanded="false">
        <div class="finding-header-left">
          <span class="finding-severity-badge ${severityClass}" style="display:inline-flex;align-items:center;gap:4px;">
            <span>${severityIcon}</span>
            <span>${severityText}</span>
          </span>
          <span class="finding-status-badge" style="background:${statusBadge.bg};color:${statusBadge.color};border:1px solid ${statusBadge.border};padding:2px 10px;border-radius:12px;font-size:12px;font-weight:500;margin-left:8px;">
            ${statusBadge.icon} ${statusBadge.text}
          </span>
          ${confidenceHtml}
          ${voteDetailsHtml}
          ${this.checkLanguageWarning() ? `
<span class="language-warning-badge" style="background:#fff3e0;color:#e65100;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:500;margin-left:8px;display:inline-flex;align-items:center;gap:4px;">
    <span>⚠️</span>
    <span>非中文结果</span>
</span>
` : ''}
          <span class="finding-type-badge" style="background:${typeStyle.bg};color:${typeStyle.color};border:1px solid ${typeStyle.border};padding:2px 10px;border-radius:12px;font-size:12px;font-weight:500;margin-left:8px;">
            ${DataTransformers.escapeHtml(typeLabel)}
          </span>
        </div>
        <div class="finding-main-info">
          <div class="finding-issue">${DataTransformers.escapeHtml(this.finding.issue || '未描述问题')}</div>
          <div class="finding-location">${this.highlightLineNumber(this.finding.location || '')}</div>
        </div>
        <svg class="finding-expand-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6,9 12,15 18,9"/>
        </svg>
      </div>
      <div class="finding-card-body"></div>
    `;

    const header = card.querySelector('.finding-card-header');
    const body = card.querySelector('.finding-card-body');

    header.addEventListener('click', () => this.toggle());
    header.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        this.toggle();
      }
    });

    return card;
  }

  renderVoteDetailsBadge() {
    const voteDetails = this.finding.vote_details;
    if (!voteDetails) return '';

    const formatted = DataTransformers.formatVoteDetails(voteDetails);
    if (!formatted) return '';

    const { consistent, inconsistent, warning, error, ratio } = formatted;
    const maxCount = Math.max(consistent, inconsistent, warning, error);

    return `
      <span class="vote-details-badge" style="background:#f3e5f5;color:#6a1b9a;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:500;margin-left:8px;display:inline-flex;align-items:center;gap:4px;" title="投票详情: ${formatted.summary}">
        <span>🗳️</span>
        <span>${ratio}</span>
      </span>
    `;
  }

  renderConfidenceBadge() {
    const confidence = this.finding.confidence;
    if (confidence === undefined || confidence === null) return '';

    const level = DataTransformers.getConfidenceLevel(confidence);
    const levelConfig = {
      high: { bg: '#e8f5e9', color: '#2e7d32', icon: '💪' },
      medium: { bg: '#e3f2fd', color: '#1565c0', icon: '👍' },
      low: { bg: '#fff8e1', color: '#f57f17', icon: '🤔' },
      'very-low': { bg: '#ffebee', color: '#c62828', icon: '⚠️' },
      unknown: { bg: '#f5f5f5', color: '#616161', icon: '❓' },
    };
    const config = levelConfig[level] || levelConfig.unknown;
    const percentage = DataTransformers.formatConfidence(confidence);

    return `
      <span class="confidence-badge confidence-${level}" style="background:${config.bg};color:${config.color};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:500;margin-left:8px;display:inline-flex;align-items:center;gap:4px;" title="置信度: ${percentage}">
        <span>${config.icon}</span>
        <span>${percentage}</span>
      </span>
    `;
  }

  toggle() {
    this.isExpanded = !this.isExpanded;
    const card = this.element;
    const header = card.querySelector('.finding-card-header');
    const body = card.querySelector('.finding-card-body');

    if (this.isExpanded) {
      card.classList.add('expanded');
      header.setAttribute('aria-expanded', 'true');
      body.innerHTML = this.renderBody();
    } else {
      card.classList.remove('expanded');
      header.setAttribute('aria-expanded', 'false');
      body.innerHTML = '';
    }

    if (this.options.onToggle) {
      this.options.onToggle(this.isExpanded, this.finding.id);
    }
  }

  renderBody() {
    const f = this.finding;
    let html = '';

    html += this.renderAgentResultsSection();

    if (f.mapping_ref && Object.keys(f.mapping_ref).length > 0) {
      /* IT-Mapping参考区块：显示source/target/logic/sheet等映射信息，支持动态扩展字段以表格形式渲染 */
      const source = f.mapping_ref.source || '';
      const target = f.mapping_ref.target || '';
      const logic = f.mapping_ref.logic || '';
      const otherEntries = Object.entries(f.mapping_ref).filter(([key]) => !['source', 'target', 'logic'].includes(key));

      html += `
        <div class="finding-detail-section" style="background:#e3f2fd;border-radius:8px;padding:12px;margin:8px 0;border:2px solid #1976d2;">
          <details open>
            <summary style="cursor:pointer;font-weight:600;color:#1565c0;padding:4px 0;display:flex;align-items:center;gap:6px;">
              <span>📋</span>
              <span>IT-Mapping定义</span>
              <span style="background:#1976d2;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;margin-left:6px;">基准</span>
              <span style="font-size:11px;color:#64b5f6;font-weight:normal;margin-left:auto;">点击折叠/展开</span>
            </summary>
            <div style="margin-top:10px;">
              ${source ? `
                <div style="margin-bottom:8px;">
                  <div style="font-size:12px;color:#1976d2;font-weight:500;margin-bottom:4px;">源表字段 (Source)</div>
                  <div style="background:#fff;padding:8px;border-radius:4px;border-left:3px solid #4caf50;font-size:13px;color:#424242;">
                    ${DataTransformers.escapeHtml(source)}
                  </div>
                </div>
              ` : ''}
              ${target ? `
                <div style="margin-bottom:8px;">
                  <div style="font-size:12px;color:#1976d2;font-weight:500;margin-bottom:4px;">目标字段 (Target)</div>
                  <div style="background:#fff;padding:8px;border-radius:4px;border-left:3px solid #2196f3;font-size:13px;color:#424242;">
                    ${DataTransformers.escapeHtml(target)}
                  </div>
                </div>
              ` : ''}
              ${logic ? `
                <div style="margin-bottom:8px;">
                  <div style="font-size:12px;color:#1976d2;font-weight:500;margin-bottom:4px;">映射逻辑 (Logic)</div>
                  <div style="background:#fff;padding:8px;border-radius:4px;border-left:3px solid #2196f3;font-size:13px;color:#424242;white-space:pre-wrap;">
                    ${DataTransformers.escapeHtml(logic)}
                  </div>
                </div>
              ` : ''}
              ${otherEntries.length > 0 ? `
                <table class="mapping-ref-table" style="margin-top:8px;width:100%;border-collapse:collapse;">
                  <thead>
                    <tr style="background:#bbdefb;">
                      <th style="padding:6px 10px;text-align:left;font-size:12px;color:#0d47a1;border:1px solid #90caf9;">属性</th>
                      <th style="padding:6px 10px;text-align:left;font-size:12px;color:#0d47a1;border:1px solid #90caf9;">值</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${otherEntries.map(
                      ([key, val]) =>
                        `<tr><td style="padding:6px 10px;font-size:12px;border:1px solid #e3f2fd;color:#1565c0;font-weight:500;">${DataTransformers.escapeHtml(key)}</td><td style="padding:6px 10px;font-size:12px;border:1px solid #e3f2fd;color:#424242;">${DataTransformers.escapeHtml(String(val))}</td></tr>`
                    ).join('')}
                  </tbody>
                </table>
              ` : ''}
            </div>
          </details>
        </div>
      `;
    }

    if (f.original_sql) {
      const highlightedSql = this.highlightSql(f.original_sql);
      html += `
        <div class="finding-detail-section">
          <div class="finding-detail-title">📝 SQL实现<span style="font-size:11px;color:#757575;font-weight:normal;margin-left:4px;">（待检查）</span></div>
          <div class="finding-sql-block"><pre><code class="language-sql">${highlightedSql}</code></pre></div>
        </div>
      `;
    }

    if (f.explanation) {
      html += `
        <div class="finding-detail-section">
          <div class="finding-detail-title">❌ 差异说明</div>
          <div class="finding-reason">${DataTransformers.escapeHtml(f.explanation)}</div>
        </div>
      `;
    }

    if (f.suggestion) {
      const highlightedSuggestion = this.highlightSql(f.suggestion);
      html += `
        <div class="finding-detail-section">
          <div class="finding-detail-title" style="color:#2e7d32;">✅ 建议修改：</div>
          <div style="background:#e8f5e9;border-radius:6px;padding:12px;border-left:4px solid #4caf50;">
            <pre style="margin:0;"><code class="language-sql" style="color:#1b5e20;font-size:13px;background:transparent;">${highlightedSuggestion}</code></pre>
          </div>
        </div>
      `;
    }

    return html;
  }

  renderAgentResultsSection() {
    const agentResults = this.finding.agent_results;
    if (!agentResults || !Array.isArray(agentResults) || agentResults.length === 0) {
      return '';
    }

    const voteDetails = this.finding.vote_details;
    const formattedVote = voteDetails ? DataTransformers.formatVoteDetails(voteDetails) : null;

    let voteSummaryHtml = '';
    if (formattedVote) {
      voteSummaryHtml = `
        <div class="vote-summary-bar" style="display:flex;gap:4px;margin-bottom:12px;height:24px;border-radius:4px;overflow:hidden;">
          ${this.renderVoteBarSegment('一致', formattedVote.consistent, '#4caf50', formattedVote.total)}
          ${this.renderVoteBarSegment('不一致', formattedVote.inconsistent, '#f44336', formattedVote.total)}
          ${this.renderVoteBarSegment('警告', formattedVote.warning, '#ff9800', formattedVote.total)}
          ${this.renderVoteBarSegment('失败', formattedVote.error, '#9e9e9e', formattedVote.total)}
        </div>
      `;
    }

    const agentCardsHtml = agentResults.map((result, index) => {
      const formatted = DataTransformers.formatAgentResult(result);
      if (!formatted) return '';

      const statusColors = {
        consistent: { bg: '#e8f5e9', border: '#4caf50', icon: '✅' },
        inconsistent: { bg: '#ffebee', border: '#f44336', icon: '❌' },
        warning: { bg: '#fff8e1', border: '#ff9800', icon: '⚠️' },
        error: { bg: '#fce4ec', border: '#9e9e9e', icon: '🔴' },
        timeout: { bg: '#f3e5f5', border: '#9c27b0', icon: '⏱️' },
        parse_error: { bg: '#efebe9', border: '#795548', icon: '📝' },
      };
      const colors = statusColors[formatted.status] || statusColors.error;

      return `
        <div class="agent-result-card" style="background:${colors.bg};border-left:3px solid ${colors.border};padding:10px 12px;border-radius:4px;margin-bottom:8px;">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
            <span style="font-weight:600;font-size:13px;color:#424242;">
              ${colors.icon} Agent-${formatted.agentId}
            </span>
            <span style="font-size:12px;padding:2px 8px;border-radius:10px;background:rgba(0,0,0,0.05);color:#616161;">
              ${formatted.statusLabel}
            </span>
          </div>
          ${formatted.issue ? `<div style="font-size:13px;color:#424242;margin-bottom:4px;">${DataTransformers.escapeHtml(formatted.issue)}</div>` : ''}
          ${formatted.explanation ? `<div style="font-size:12px;color:#757575;margin-bottom:4px;">${DataTransformers.escapeHtml(formatted.explanation.substring(0, 150))}${formatted.explanation.length > 150 ? '...' : ''}</div>` : ''}
          <div style="font-size:11px;color:#9e9e9e;">
            置信度: ${DataTransformers.formatConfidence(formatted.confidence)}
          </div>
        </div>
      `;
    }).join('');

    return `
      <div class="finding-detail-section agent-results-section">
        <details open>
          <summary style="cursor:pointer;font-weight:600;color:#6a1b9a;padding:4px 0;display:flex;align-items:center;gap:6px;margin-bottom:8px;">
            <span>🗳️</span>
            <span>三Agent投票详情</span>
            <span style="font-size:11px;color:#9e9e9e;font-weight:normal;margin-left:auto;">点击折叠/展开</span>
          </summary>
          ${voteSummaryHtml}
          <div class="agent-results-list">
            ${agentCardsHtml}
          </div>
        </details>
      </div>
    `;
  }

  renderVoteBarSegment(label, count, color, total) {
    if (!count || count === 0) return '';
    const width = (count / total) * 100;
    return `
      <div style="width:${width}%;background:${color};display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;font-weight:500;" title="${label}: ${count}">
        ${count}
      </div>
    `;
  }

  highlightSql(sql) {
    try {
      if (window.hljs) {
        return hljs.highlight(sql, { language: 'sql' }).value;
      }
    } catch (e) {
      console.warn('SQL highlighting failed:', e);
    }
    return DataTransformers.escapeHtml(sql);
  }

  getElement() {
    return this.element;
  }

  destroy() {
    if (this.element && this.element.parentNode) {
      this.element.parentNode.removeChild(this.element);
    }
  }
}
