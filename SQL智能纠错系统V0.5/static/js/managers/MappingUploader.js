class MappingUploader {
  constructor() {
    this.zone = document.getElementById('mappingUploadZone');
    this.fileInput = document.getElementById('mappingFileInput');
    this.preview = document.getElementById('mappingPreview');
    this.loading = document.getElementById('mappingLoading');
    this.filenameEl = document.getElementById('mappingFilename');
    this.statsEl = document.getElementById('mappingStats');

    this.uploadZone = new UploadZone({
      zone: this.zone,
      fileInput: this.fileInput,
      accept: '.xlsx',
      maxSize: 50 * 1024 * 1024,
      onFileSelected: (file) => this.handleFileSelected(file),
    });

    const removeBtn = document.getElementById('mappingRemoveBtn');
    if (removeBtn) {
      removeBtn.addEventListener('click', () => this.remove());
    }
  }

  async handleFileSelected(file) {
    this.showLoading();

    try {
      const result = await api.uploadMapping(file);

      if (result.success && result.data) {
        this.setFile(file, result.data);
        appState.setState('files.mapping', { file, data: result.data });
        toast.success(`IT-Mapping文件 "${file.name}" 上传成功`);
      } else {
        throw new Error(result.message || '文件解析失败');
      }
    } catch (error) {
      console.error('Upload error:', error);
      toast.error(error.message || '上传失败，请重试');
      this.reset();
    }
  }

  showLoading() {
    if (this.zone) this.zone.style.display = 'none';
    if (this.preview) this.preview.style.display = 'none';
    if (this.loading) this.loading.style.display = 'flex';
  }

  setFile(file, data) {
    if (this.loading) this.loading.style.display = 'none';
    if (this.zone) this.zone.style.display = 'none';
    if (this.preview) this.preview.style.display = 'block';

    if (this.filenameEl) {
      this.filenameEl.textContent = file.name;
    }

    if (this.statsEl && data) {
      const tables = data.tables?.length || 0;
      const fields = data.field_mappings?.length || 0;
      const relationships = data.relationships?.length || 0;

      this.statsEl.innerHTML = `
        <span class="preview-stat-item">
          <span>数据表</span>
          <span class="preview-stat-value">${tables} 张</span>
        </span>
        <span class="preview-stat-item">
          <span>字段映射</span>
          <span class="preview-stat-value">${fields} 个</span>
        </span>
        <span class="preview-stat-item">
          <span>关联关系</span>
          <span class="preview-stat-value">${relationships} 个</span>
        </span>
      `;
    }
  }

  remove() {
    appState.setState('files.mapping', null);
    this.reset();
    toast.info('已移除IT-Mapping文件');
  }

  reset() {
    if (this.zone) this.zone.style.display = '';
    if (this.preview) this.preview.style.display = 'none';
    if (this.loading) this.loading.style.display = 'none';
    if (this.filenameEl) this.filenameEl.textContent = '';
    if (this.statsEl) this.statsEl.innerHTML = '';
    this.uploadZone.reset();
  }

  hasFile() {
    return !!appState.getState().files.mapping;
  }

  getFile() {
    return appState.getState().files.mapping;
  }

  destroy() {
    this.uploadZone.destroy();
  }
}
