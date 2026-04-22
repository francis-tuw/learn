const DataTransformers = {
  formatResultForDisplay(apiResult) {
    if (!apiResult) return null;

    const { total_checks, consistent_count, inconsistent_count, duration, agents_count, findings, summary } = apiResult;
    const totalChecks = total_checks || summary?.total_checks || 0;
    const consistentCount = consistent_count || summary?.consistent_count || 0;
    const inconsistentCount = inconsistent_count || summary?.inconsistent_count || 0;
    const passRate = totalChecks > 0 ? ((consistentCount / totalChecks) * 100).toFixed(1) : 0;

    return {
      summary: {
        totalChecks: totalChecks,
        consistentCount: consistentCount,
        inconsistentCount: inconsistentCount,
        passRate: parseFloat(passRate),
        duration: duration || 0,
        agentsCount: agents_count || 0,
        avgConfidence: summary?.avg_confidence || 0,
        statusDistribution: summary?.status_distribution || {},
        strategy: summary?.strategy || 'unknown',
      },
      findings: (findings || []).map((f) => ({
        ...f,
        severityLabel: this.getSeverityLabel(f.severity),
        severityClass: this.getSeverityClass(f.severity),
        truncatedIssue: f.issue?.substring(0, 80),
        typeLabel: f.type || '其他',
      })),
    };
  },

  formatVoteDetails(voteDetails) {
    if (!voteDetails || typeof voteDetails !== 'object') return null;

    const { consistent, inconsistent, warning, error } = voteDetails;
    const total = (consistent || 0) + (inconsistent || 0) + (warning || 0) + (error || 0);

    if (total === 0) return null;

    const parts = [];
    if (consistent > 0) parts.push(`${consistent}一致`);
    if (inconsistent > 0) parts.push(`${inconsistent}不一致`);
    if (warning > 0) parts.push(`${warning}警告`);
    if (error > 0) parts.push(`${error}失败`);

    return {
      total,
      consistent: consistent || 0,
      inconsistent: inconsistent || 0,
      warning: warning || 0,
      error: error || 0,
      summary: parts.join(' / '),
      ratio: this.formatVoteRatio(voteDetails),
    };
  },

  formatVoteRatio(voteDetails) {
    if (!voteDetails) return '-';

    const consistent = voteDetails.consistent || 0;
    const inconsistent = voteDetails.inconsistent || 0;

    if (consistent === 0 && inconsistent === 0) return '-';

    return `${Math.max(consistent, inconsistent)}:${Math.min(consistent, inconsistent)}`;
  },

  formatConfidence(confidence) {
    if (confidence === undefined || confidence === null) return '-';
    const num = parseFloat(confidence);
    if (isNaN(num)) return '-';
    return `${Math.round(num * 100)}%`;
  },

  getConfidenceLevel(confidence) {
    if (confidence === undefined || confidence === null) return 'unknown';
    const num = parseFloat(confidence);
    if (isNaN(num)) return 'unknown';
    if (num >= 0.9) return 'high';
    if (num >= 0.67) return 'medium';
    if (num >= 0.33) return 'low';
    return 'very-low';
  },

  formatAgentResult(agentResult) {
    if (!agentResult || typeof agentResult !== 'object') return null;

    return {
      agentId: agentResult.agent_id || '?',
      status: agentResult.status || 'unknown',
      statusLabel: this.getAgentStatusLabel(agentResult.status),
      issue: agentResult.issue || '',
      explanation: agentResult.explanation || '',
      suggestion: agentResult.suggestion || '',
      confidence: agentResult.confidence || 0,
      success: agentResult.success !== false,
    };
  },

  getAgentStatusLabel(status) {
    const labels = {
      consistent: '一致',
      inconsistent: '不一致',
      warning: '警告',
      error: '错误',
      timeout: '超时',
      parse_error: '解析失败',
      unknown: '未知',
    };
    return labels[status] || status;
  },

  getSeverityLabel(severity) {
    const map = {
      critical: '严重',
      high: '高',
      medium: '中',
      low: '低',
    };
    return map[severity] || '未知';
  },

  getSeverityClass(severity) {
    return `severity-${severity || 'low'}`;
  },

  formatDuration(seconds) {
    if (!seconds || seconds < 0) return '-';
    if (seconds < 60) return `${Math.round(seconds)}秒`;
    const minutes = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    if (minutes < 60) return `${minutes}分${secs > 0 ? secs + '秒' : ''}`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}小时${mins > 0 ? mins + '分' : ''}`;
  },

  formatDate(isoString) {
    if (!isoString) return '-';

    try {
      let date;

      if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(isoString)) {
        date = new Date(isoString + 'Z');
        if (isNaN(date.getTime())) return isoString;
      } else {
        date = new Date(isoString);
        if (isNaN(date.getTime())) return isoString;
      }

      const pad = (n) => String(n).padStart(2, '0');
      return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
    } catch (e) {
      console.warn('Date format error:', e);
      return isoString || '-';
    }
  },

  formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let i = 0;
    while (bytes >= 1024 && i < units.length - 1) {
      bytes /= 1024;
      i++;
    }
    return `${bytes.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  },

  formatNumber(num) {
    if (num === null || num === undefined) return '0';
    return num.toLocaleString('zh-CN');
  },

  escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  },

  truncateText(text, maxLength = 100) {
    if (!text) return '';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  },

  detectSqlDialect(sqlContent) {
    if (!sqlContent) return 'Oracle';

    const upperSql = sqlContent.toUpperCase();

    const oraclePatterns = ['NVL(', 'ROWNUM', 'DUAL', 'SYSDATE', 'TO_DATE(', 'TO_CHAR('];
    const hivePatterns = [
      'LATERAL VIEW',
      'EXPLODE(',
      'COLLECT_LIST(',
      'SIZE(',
      'GET_JSON_OBJECT(',
      'FROM_UNIXTIME(',
    ];

    let oracleScore = 0;
    let hiveScore = 0;

    oraclePatterns.forEach((p) => {
      if (upperSql.includes(p)) oracleScore++;
    });

    hivePatterns.forEach((p) => {
      if (upperSql.includes(p)) hiveScore++;
    });

    if (hiveScore > oracleScore) return 'Hive';
    return 'Oracle';
  },

  getStepLabel(step) {
    const labels = {
      idle: '准备中',
      parsing: '解析文件',
      agents: 'Agent审查中',
      done: '已完成',
      error: '执行出错',
    };
    return labels[step] || step;
  },

  getStatusLabel(status) {
    const labels = {
      waiting: '等待中',
      parsing: '解析中',
      agents: '审查中',
      done: '已完成',
      error: '异常',
      paused: '已暂停',
    };
    return labels[status] || status;
  },

  getStatusClass(status) {
    return `status-${status || 'waiting'}`;
  },
};
