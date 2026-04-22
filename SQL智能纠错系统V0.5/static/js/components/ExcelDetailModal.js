class ExcelDetailModal {
  constructor() {
    this.currentTaskId = null;
    this.data = null;
  }

  async show(taskId) {
    this.currentTaskId = taskId;
    
    try {
      toast.info('正在加载详情数据...');
      const result = await api.getExcelData(taskId);
      
      if (!result.success) {
        throw new Error(result.message || '获取数据失败');
      }
      
      this.data = result.data;
      this.render();
      toast.success('详情数据加载成功');
    } catch (error) {
      console.error('加载Excel详情失败:', error);
      toast.error('加载详情失败: ' + error.message);
    }
  }

  render() {
    const { task_id, mapping_file, dataset, datamap, statistics } = this.data;
    
    const stats = statistics || {};
    const totalChecks = stats.total_checks || 0;
    const datasetInconsistent = stats.dataset_inconsistent || 0;
    const datamapInconsistent = stats.datamap_inconsistent || 0;
    const totalInconsistent = stats.total_inconsistent || 0;
    const consistentCount = totalChecks - totalInconsistent;
    
    const content = `
      <div class="excel-detail-container">
        <div class="excel-detail-header">
          <div class="detail-info">
            <span class="info-label">任务ID:</span>
            <span class="info-value">${DataTransformers.escapeHtml(task_id || '')}</span>
          </div>
          <div class="detail-info">
            <span class="info-label">Mapping文件:</span>
            <span class="info-value">${DataTransformers.escapeHtml(mapping_file || '未知')}</span>
          </div>
        </div>
        
        <div class="excel-statistics-bar">
          <div class="stat-item">
            <span class="stat-label">总检查项:</span>
            <span class="stat-value">${totalChecks}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">一致:</span>
            <span class="stat-value stat-consistent">${consistentCount}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">不一致:</span>
            <span class="stat-value stat-inconsistent">${totalInconsistent}</span>
          </div>
          <div class="stat-item stat-detail">
            <span class="stat-label">(数据源: ${datasetInconsistent}, 数据映射: ${datamapInconsistent})</span>
          </div>
        </div>
        
        <div class="excel-tabs">
          <button class="excel-tab active" data-tab="dataset">📊 数据源 (DataSet) ${datasetInconsistent > 0 ? `<span class="tab-badge">${datasetInconsistent}</span>` : ''}</button>
          <button class="excel-tab" data-tab="datamap">📋 数据映射 (DataMap) ${datamapInconsistent > 0 ? `<span class="tab-badge">${datamapInconsistent}</span>` : ''}</button>
        </div>
        
        <div class="excel-content">
          <div class="excel-panel active" id="datasetPanel">
            ${this.renderDatasetTable(dataset)}
          </div>
          <div class="excel-panel" id="datamapPanel">
            ${this.renderDatamapTable(datamap)}
          </div>
        </div>
        
        <div class="excel-detail-footer">
          <button class="btn btn-primary" id="exportExcelBtn">
            📥 导出Excel
          </button>
          <button class="btn btn-outline" id="closeDetailBtn">
            关闭
          </button>
        </div>
      </div>
      
      <style>
        .excel-detail-container {
          display: flex;
          flex-direction: column;
          height: 70vh;
          min-height: 500px;
        }
        
        .excel-detail-header {
          display: flex;
          gap: 24px;
          padding: 12px 16px;
          background: var(--bg-secondary, #f5f5f5);
          border-radius: 8px;
          margin-bottom: 16px;
          flex-wrap: wrap;
        }
        
        .detail-info {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        
        .info-label {
          color: var(--text-secondary, #666);
          font-size: 13px;
        }
        
        .info-value {
          font-weight: 500;
          color: var(--text-primary, #333);
          font-size: 13px;
        }
        
        .excel-statistics-bar {
          display: flex;
          gap: 20px;
          padding: 12px 16px;
          background: linear-gradient(135deg, #f0f5ff 0%, #e6f7ff 100%);
          border-radius: 8px;
          margin-bottom: 16px;
          align-items: center;
          flex-wrap: wrap;
        }
        
        .stat-item {
          display: flex;
          align-items: center;
          gap: 6px;
        }
        
        .stat-label {
          color: var(--text-secondary, #666);
          font-size: 13px;
        }
        
        .stat-value {
          font-weight: 600;
          font-size: 15px;
          color: var(--text-primary, #333);
        }
        
        .stat-consistent {
          color: var(--success-color, #52c41a);
        }
        
        .stat-inconsistent {
          color: var(--error-color, #ff4d4f);
        }
        
        .stat-detail {
          color: var(--text-secondary, #999);
          font-size: 12px;
          margin-left: 8px;
        }
        
        .tab-badge {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 18px;
          height: 18px;
          padding: 0 6px;
          background: var(--error-color, #ff4d4f);
          color: white;
          font-size: 11px;
          font-weight: 600;
          border-radius: 9px;
          margin-left: 6px;
        }
        
        .excel-tabs {
          display: flex;
          gap: 8px;
          margin-bottom: 16px;
          border-bottom: 1px solid var(--border-color, #e8e8e8);
          padding-bottom: 8px;
        }
        
        .excel-tab {
          padding: 8px 20px;
          border: none;
          background: transparent;
          cursor: pointer;
          font-size: 14px;
          color: var(--text-secondary, #666);
          border-radius: 6px 6px 0 0;
          transition: all 0.2s;
          position: relative;
        }
        
        .excel-tab:hover {
          color: var(--primary-color, #1890ff);
          background: rgba(24, 144, 255, 0.08);
        }
        
        .excel-tab.active {
          color: var(--primary-color, #1890ff);
          font-weight: 500;
          background: var(--bg-primary, #fff);
        }
        
        .excel-tab.active::after {
          content: '';
          position: absolute;
          bottom: -9px;
          left: 0;
          right: 0;
          height: 2px;
          background: var(--primary-color, #1890ff);
        }
        
        .excel-content {
          flex: 1;
          overflow: hidden;
          position: relative;
        }
        
        .excel-panel {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          overflow: auto;
          display: none;
        }
        
        .excel-panel.active {
          display: block;
        }
        
        .excel-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }
        
        .excel-table th {
          position: sticky;
          top: 0;
          background: #D9E1F2;
          color: var(--text-primary, #333);
          font-weight: 600;
          padding: 10px 12px;
          text-align: left;
          border: 1px solid #B4C6E7;
          white-space: nowrap;
          z-index: 10;
        }
        
        .excel-table td {
          padding: 8px 12px;
          border: 1px solid var(--border-color, #e8e8e8);
          vertical-align: top;
          max-width: 300px;
          word-break: break-word;
        }
        
        .excel-table tr:hover {
          background: var(--hover-bg, #fafafa);
        }
        
        .status-yes {
          background: #C6EFCE !important;
          color: #006100;
          font-weight: 500;
          text-align: center;
        }
        
        .status-no {
          background: #FFC7CE !important;
          color: #9C0006;
          font-weight: 500;
          text-align: center;
        }
        
        .excel-detail-footer {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
          padding-top: 16px;
          border-top: 1px solid var(--border-color, #e8e8e8);
          margin-top: 16px;
        }
        
        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 200px;
          color: var(--text-secondary, #999);
        }
        
        .empty-state-icon {
          font-size: 48px;
          margin-bottom: 16px;
        }
        
        .cell-content {
          white-space: pre-wrap;
          line-height: 1.5;
        }
      </style>
    `;

    modal.show({
      title: '📋 Excel详情查看',
      content: content,
      width: '90vw',
      footer: false
    });

    this.bindEvents();
  }

  renderDatasetTable(dataset) {
    const { headers, groups } = dataset;
    
    if (!groups || groups.length === 0) {
      return `
        <div class="empty-state">
          <div class="empty-state-icon">📭</div>
          <div>暂无数据源对比结果</div>
        </div>
      `;
    }

    let rows = [];
    for (const group of groups) {
      const relations = group.relations || [];
      if (relations.length === 0) {
        rows.push(`
          <tr>
            <td>${DataTransformers.escapeHtml(group.group_id || '')}</td>
            <td>${DataTransformers.escapeHtml(group.source_tables || '')}</td>
            <td>-</td>
            <td>-</td>
            <td>-</td>
            <td class="status-yes">是</td>
            <td>-</td>
          </tr>
        `);
      } else {
        for (const relation of relations) {
          const isConsistent = relation.is_consistent === '是';
          rows.push(`
            <tr>
              <td>${DataTransformers.escapeHtml(group.group_id || '')}</td>
              <td><div class="cell-content">${DataTransformers.escapeHtml(group.source_tables || '')}</div></td>
              <td>${DataTransformers.escapeHtml(relation.compare_module || '')}</td>
              <td><div class="cell-content">${DataTransformers.escapeHtml(relation.content || '')}</div></td>
              <td><div class="cell-content">${DataTransformers.escapeHtml(relation.sql_content || '')}</div></td>
              <td class="${isConsistent ? 'status-yes' : 'status-no'}">${DataTransformers.escapeHtml(relation.is_consistent || '是')}</td>
              <td><div class="cell-content">${DataTransformers.escapeHtml(relation.remark || '')}</div></td>
            </tr>
          `);
        }
      }
    }

    return `
      <table class="excel-table">
        <thead>
          <tr>
            ${headers.map(h => `<th>${DataTransformers.escapeHtml(h)}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${rows.join('')}
        </tbody>
      </table>
    `;
  }

  renderDatamapTable(datamap) {
    const { headers, rows } = datamap;
    
    if (!rows || rows.length === 0) {
      return `
        <div class="empty-state">
          <div class="empty-state-icon">📭</div>
          <div>暂无数据映射对比结果</div>
        </div>
      `;
    }

    const tableRows = rows.map(row => {
      const isConsistent = row.is_consistent === '是';
      return `
        <tr>
          <td>${DataTransformers.escapeHtml(row.group_id || '')}</td>
          <td>${row.field_seq || 0}</td>
          <td>${DataTransformers.escapeHtml(row.target_field_cn || '')}</td>
          <td>${DataTransformers.escapeHtml(row.target_field_en || '')}</td>
          <td>${DataTransformers.escapeHtml(row.extract_method || '')}</td>
          <td>${DataTransformers.escapeHtml(row.source_table || '')}</td>
          <td>${DataTransformers.escapeHtml(row.source_field_en || '')}</td>
          <td>${DataTransformers.escapeHtml(row.source_field_cn || '')}</td>
          <td>${DataTransformers.escapeHtml(row.default_value || '')}</td>
          <td><div class="cell-content">${DataTransformers.escapeHtml(row.transform_logic || '')}</div></td>
          <td><div class="cell-content">${DataTransformers.escapeHtml(row.sql_expression || '')}</div></td>
          <td class="${isConsistent ? 'status-yes' : 'status-no'}">${DataTransformers.escapeHtml(row.is_consistent || '是')}</td>
          <td><div class="cell-content">${DataTransformers.escapeHtml(row.remark || '')}</div></td>
        </tr>
      `;
    }).join('');

    return `
      <table class="excel-table">
        <thead>
          <tr>
            ${headers.map(h => `<th>${DataTransformers.escapeHtml(h)}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${tableRows}
        </tbody>
      </table>
    `;
  }

  bindEvents() {
    const tabs = document.querySelectorAll('.excel-tab');
    const panels = document.querySelectorAll('.excel-panel');

    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        panels.forEach(p => p.classList.remove('active'));
        
        tab.classList.add('active');
        const targetPanel = document.getElementById(tab.dataset.tab + 'Panel');
        if (targetPanel) {
          targetPanel.classList.add('active');
        }
      });
    });

    const exportBtn = document.getElementById('exportExcelBtn');
    if (exportBtn) {
      exportBtn.addEventListener('click', async () => {
        try {
          toast.info('正在导出Excel...');
          await api.downloadReport(this.currentTaskId);
          toast.success('Excel导出成功');
        } catch (error) {
          toast.error('导出失败: ' + error.message);
        }
      });
    }

    const closeBtn = document.getElementById('closeDetailBtn');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        modal.close();
      });
    }
  }
}

const excelDetailModal = new ExcelDetailModal();
window.excelDetailModal = excelDetailModal;
