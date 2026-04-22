class UploadZone {
  constructor(options = {}) {
    this.zone = options.zone;
    this.fileInput = options.fileInput;
    this.accept = options.accept || '*';
    this.maxSize = options.maxSize || 50 * 1024 * 1024;
    this.onFileSelected = options.onFileSelected || (() => {});
    this.onDragStateChange = options.onDragStateChange || (() => {});

    this.isDragging = false;
    this.bindEvents();
  }

  bindEvents() {
    if (this.zone) {
      this.zone.addEventListener('dragenter', (e) => this.handleDragEnter(e));
      this.zone.addEventListener('dragover', (e) => this.handleDragOver(e));
      this.zone.addEventListener('dragleave', (e) => this.handleDragLeave(e));
      this.zone.addEventListener('drop', (e) => this.handleDrop(e));
      this.zone.addEventListener('click', () => this.triggerFileInput());
    }

    if (this.fileInput) {
      this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
    }
  }

  triggerFileInput() {
    if (this.fileInput) {
      this.fileInput.click();
    }
  }

  handleDragEnter(e) {
    e.preventDefault();
    e.stopPropagation();
    this.isDragging = true;
    this.zone.classList.add('dragover');
    this.onDragStateChange(true);
  }

  handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = 'copy';
  }

  handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    if (!this.zone.contains(e.relatedTarget)) {
      this.isDragging = false;
      this.zone.classList.remove('dragover');
      this.onDragStateChange(false);
    }
  }

  handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    this.isDragging = false;
    this.zone.classList.remove('dragover');
    this.onDragStateChange(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      this.processFile(files[0]);
    }
  }

  handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
      this.processFile(files[0]);
    }
  }

  processFile(file) {
    const validationError = this.validateFile(file);
    if (validationError) {
      toast.error(validationError);
      return;
    }

    this.onFileSelected(file);
  }

  validateFile(file) {
    if (!file) return '未选择文件';

    if (this.accept !== '*') {
      const acceptedTypes = this.accept.split(',').map((t) => t.trim());
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      if (!acceptedTypes.includes(ext) && !acceptedTypes.includes(file.type)) {
        return `不支持的文件格式，请选择 ${this.accept} 格式的文件`;
      }
    }

    if (file.size > this.maxSize) {
      return `文件大小超过限制（最大 ${DataTransformers.formatFileSize(this.maxSize)}）`;
    }

    const forbiddenChars = ['..', '\\0', '../'];
    for (const char of forbiddenChars) {
      if (file.name.includes(char)) {
        return '文件名包含非法字符';
      }
    }

    return null;
  }

  reset() {
    if (this.fileInput) {
      this.fileInput.value = '';
    }
    this.isDragging = false;
    this.zone?.classList.remove('dragover');
  }

  destroy() {
    if (this.zone) {
      this.zone.removeEventListener('dragenter', this.handleDragEnter);
      this.zone.removeEventListener('dragover', this.handleDragOver);
      this.zone.removeEventListener('dragleave', this.handleDragLeave);
      this.zone.removeEventListener('drop', this.handleDrop);
      this.zone.removeEventListener('click', this.triggerFileInput);
    }

    if (this.fileInput) {
      this.fileInput.removeEventListener('change', this.handleFileSelect);
    }
  }
}
