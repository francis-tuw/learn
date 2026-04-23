class ApiService {
  constructor() {
    this.baseURL = '';
  }

  async request(url, options = {}) {
    const response = await fetch(this.baseURL + url, {
      headers: {
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
      },
      cache: 'no-store',
      ...options,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `HTTP ${response.status}`);
    }

    return await response.json();
  }

  async get(url) {
    return this.request(url, { method: 'GET' });
  }

  async post(url, data) {
    return this.request(url, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async uploadFile(url, file) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(this.baseURL + url, {
      method: 'POST',
      body: formData,
      headers: {},
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || `上传失败 (${response.status})`);
    }

    return await response.json();
  }

  async downloadFile(url, filename) {
    const response = await fetch(this.baseURL + url);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.message || '下载失败');
    }

    const contentType = response.headers.get('Content-Type') || '';
    if (contentType.includes('application/json')) {
      const data = await response.json();
      if (!data.success) {
        throw new Error(data.message || '下载失败');
      }
      throw new Error('服务器返回了意外的响应格式');
    }

    const blob = await response.blob();
    if (blob.size === 0) {
      throw new Error('下载的文件为空');
    }

    const downloadUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => {
      URL.revokeObjectURL(downloadUrl);
    }, 100);
  }

  getStatus() {
    return this.get('/api/status');
  }

  uploadMapping(file) {
    return this.uploadFile('/api/upload', file);
  }

  startReview(data) {
    return this.post('/api/review', data);
  }

  getProgress(taskId) {
    return this.get(`/api/progress/${taskId}`);
  }

  getResult(taskId) {
    return this.get(`/api/result/${taskId}`);
  }

  downloadReport(taskId) {
    return this.downloadFile(`/api/download/report/${taskId}`, `纠错报告_${taskId}.xlsx`);
  }

  getExcelData(taskId) {
    return this.get(`/api/excel-data/${taskId}`);
  }

  downloadAnnotatedSql(taskId) {
    return this.downloadFile(
      `/api/download/annotated-sql/${taskId}`,
      `标注SQL_${taskId}.sql`
    );
  }

  downloadExcelReport(taskId) {
    return this.downloadFile(
      `/api/export/excel/${taskId}`,
      `SQL检查结果_${taskId}.xlsx`
    );
  }

  exportMarkdown(taskId) {
    return this.downloadFile(
      `/api/download/report/${taskId}`,
      `纠错报告_${taskId}.xlsx`
    );
  }

  batchUpload() {
    return this.post('/api/batch/upload', {});
  }

  startBatch(batchId) {
    return this.post('/api/batch/start', { batch_id: batchId });
  }

  pauseBatch(batchId) {
    return this.post(`/api/batch/pause/${batchId}`, {});
  }

  cancelBatch(batchId) {
    return this.post(`/api/batch/cancel/${batchId}`, {});
  }

  batchExport(batchId) {
    return this.downloadFile(
      `/api/batch/export/${batchId}`,
      `批量报告_${batchId}.zip`
    );
  }

  getHistory() {
    return this.get('/api/history');
  }

  deleteHistory(taskId) {
    return this.request(`/api/history/${taskId}`, { method: 'DELETE' });
  }

  batchDownloadHistory(ids) {
    return this.downloadFile(
      `/api/batch-download?ids=${encodeURIComponent(ids)}`,
      `SQL纠错报告批量下载_${Date.now()}.xlsx`
    );
  }

  getOllamaConfig() {
    return this.get('/api/ollama/config');
  }

  updateOllamaConfig(config) {
    return this.post('/api/ollama/config', config);
  }

  testOllamaConnection(config) {
    return this.post('/api/ollama/test-connection', config);
  }
}

const api = new ApiService();
