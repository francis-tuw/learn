# SQL智能纠错系统 - 网站详细设计文档

> 基于架构设计方案 V0.5 的前端实现规范
>
> 版本: 1.0 | 日期: 2026-04-17
>
> 技术栈: 纯 HTML5 + CSS3 + JavaScript (ES6+) | 后端: Flask

---

## 目录

- [一、设计概述](#一设计概述)
- [二、技术架构与约束](#二技术架构与约束)
- [三、网站整体布局设计](#三网站整体布局设计)
- [四、五大核心区域详细设计](#四大核心区域详细设计)
- [五、用户交互流程设计](#五用户交互流程设计)
- [六、组件详细设计规范](#六组件详细设计规范)
- [七、前端API对接方案](#七前端api对接方案)
- [八、数据处理逻辑](#八数据处理逻辑)
- [九、界面原型图](#九界面原型图)
- [十、技术实现要点](#十技术实现要点)
- [十一、关键功能模块说明](#十一关键功能模块说明)

---

## 一、设计概述

### 1.1 设计目标

本设计文档基于《SQL智能纠错系统_网站架构设计方案V0.5》,详细定义了Web前端的完整实现方案。系统定位为**金融数据报送场景下的SQL存储过程智能纠错工具**,核心价值在于:

- **业务准确性**: 将IT-Mapping作为"金标准",大幅提升SQL纠错准确率
- **中文优先**: 全流程中文交互,降低使用门槛
- **易用性**: Web界面操作,无需安装客户端
- **本地化**: Ollama本地运行,保障数据安全
- **高效性**: 支持单次和批量两种模式,满足不同业务场景

### 1.2 设计范围

本文档涵盖以下内容:

✅ 网站整体布局与视觉设计  
✅ 五大核心区域的组件设计与交互  
✅ 用户操作流程(单次/批量)  
✅ 前后端API对接方案  
✅ 数据处理与状态管理  
✅ 实时进度推送(SSE)集成  
✅ 界面原型与交互说明  
✅ 技术实现要点与代码示例  

### 1.3 用户角色

| 角色 | 使用场景 | 核心需求 |
|------|---------|---------|
| **数据开发工程师** | 日常SQL存储过程开发与审查 | 快速上传文件、查看纠错结果、导出报告 |
| **数据审核人员** | 批量审核多个报送任务的SQL | 批量上传、进度监控、批量导出 |
| **项目经理** | 查看纠错报告、了解质量状况 | 查看摘要统计、下载报告文档 |

---

## 二、技术架构与约束

### 2.1 技术栈选型

#### 前端技术栈 (严格遵循架构约束)

```
┌─────────────────────────────────────────────┐
│                前端技术栈                      │
├─────────────────────────────────────────────┤
│  HTML5          - 页面结构                    │
│  CSS3           - 样式布局(无预处理器)         │
│  JavaScript ES6+ - 交互逻辑(无框架依赖)       │
│  Highlight.js   - SQL语法高亮(可选)           │
│  SSE API        - Server-Sent Events实时通信 │
│  Fetch API      - HTTP请求                   │
│  FileReader API - 本地文件读取               │
│  Drag & Drop API - 拖拽上传                  │
└─────────────────────────────────────────────┘
```

**关键约束:**
- ❌ 不使用 React/Vue/Angular 等前端框架
- ❌ 不使用 Webpack/Vite 等构建工具
- ❌ 不使用 jQuery (使用原生JavaScript)
- ✅ 纯静态文件,直接由Flask提供
- ✅ 支持现代浏览器(Chrome/Firefox/Edge最新版)

#### 后端技术栈 (对接要求)

```
┌─────────────────────────────────────────────┐
│                后端技术栈                      │
├─────────────────────────────────────────────┤
│  Flask >=3.0     - Web框架与API服务           │
│  Celery >=5.0    - 异步任务队列               │
│  Redis >=7.0     - 消息队列与状态存储          │
│  CrewAI >=0.80   - 多Agent编排               │
│  Ollama          - 本地LLM推理                │
│  pandas/openpyxl - Excel解析                 │
│  sqlglot         - SQL解析                   │
│  python-docx     - Word文档生成              │
└─────────────────────────────────────────────┘
```

### 2.2 系统四层架构

```
┌─────────────────────────────────────────────────────────────┐
│                     展示层 (Presentation)                     │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐    │
│  │ 导航栏     │ │ 上传区     │ │ 进度面板   │ │ 结果展示   │    │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘    │
├─────────────────────────────────────────────────────────────┤
│                     接口层 (API Layer)                        │
│  Flask RESTful API / SSE实时推送 / 文件上传处理              │
├─────────────────────────────────────────────────────────────┤
│                     Agent层 (Intelligence)                   │
│  IT-Mapping解析Agent / SQL解析Agent / 审查Agent×5 / 裁决Agent│
├─────────────────────────────────────────────────────────────┤
│                     工具层 (Tools)                            │
│  pandas Excel解析 / sqlglot SQL解析 / 报告生成器 / SQL标注器  │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 设计原则

#### 用户体验原则
1. **渐进式披露**: 复杂信息按需展开,避免信息过载
2. **即时反馈**: 所有用户操作都有明确的视觉反馈
3. **容错性**: 支持撤销、重试、错误恢复
4. **一致性**: 统一的交互模式、视觉语言、术语体系

#### 技术实现原则
1. **性能优先**: 大文件分片上传、懒加载、虚拟滚动
2. **可维护性**: 模块化代码结构、清晰的命名规范
3. **可扩展性**: 预留接口支持未来功能扩展
4. **安全性**: 输入验证、XSS防护、CSRF防护

---

## 三、网站整体布局设计

### 3.1 布局架构

采用**经典的上中下三段式布局**,结合**响应式网格系统**:

```
┌──────────────────────────────────────────────────────────────┐
│  [顶部导航栏] - 固定高度60px,固定在顶部                        │
│  Logo | 系统标题 | Ollama状态指示 | 历史记录入口              │
├──────────────────────────────────────────────────────────────┤
│  [主内容区域] - 自适应高度,垂直滚动                             │
│  [Tab切换: 单次纠错 | 批量处理 | 历史记录]                      │
│  [文件上传区] → [业务补充区] → [开始按钮]                      │
│  [批量进度面板] (批量模式下显示)                                │
│  [结果展示区]                                                  │
├──────────────────────────────────────────────────────────────┤
│  [底部状态栏] - 固定高度32px                                   │
│  版本号 | 技术支持链接 | 系统状态                               │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 色彩系统

```css
:root {
  /* 主色 */
  --primary-color: #1890ff;
  --primary-hover: #40a9ff;
  --primary-active: #096dd9;

  /* 功能色 */
  --success-color: #52c41a;
  --warning-color: #faad14;
  --error-color: #f5222d;
  --info-color: #1890ff;

  /* 中性色 */
  --text-primary: #262626;
  --text-secondary: #595959;
  --text-disabled: #bfbfbf;
  --border-color: #d9d9d9;
  --background-color: #f0f2f5;
  --card-background: #ffffff;

  /* 状态颜色映射 */
  --status-waiting: #bfbfbf;
  --status-parsing: #1890ff;
  --status-agents: #722ed1;
  --status-done: #52c41a;
  --status-error: #f5222d;
}
```

---

## 四、五大核心区域详细设计

### 4.1 顶部导航栏

**组件清单:**
- Logo图标 + 系统标题 "SQL智能纠错系统"
- Ollama状态指示器 (连接状态/模型名称,每30秒自动轮询)
- 历史记录按钮 / 设置按钮

**核心功能:** 显示系统运行状态,提供全局导航入口

### 4.2 文件上传区

**包含两个子区域:**

#### IT-Mapping上传组件
- **功能特性:** 拖拽/点击上传 .xlsx 文件、格式校验、大小限制(50MB)、即时解析预览
- **解析结果展示:** 数据表数量、字段映射数量、表间关联关系数量
- **交互状态机:** 初始态 → 拖拽悬停 → 上传中 → 解析中 → 成功态

#### SQL文件上传组件
- **功能特性:** 支持.sql/.txt格式、前端本地读取、语法高亮(Highlight.js)、方言自动检测(Oracle/Hive)
- **预览功能:** 行数统计、字符数统计、内容预览(支持展开/收起)

#### 批量上传组件(批量模式)
- **功能特性:** 多组文件对管理、自动配对(基于文件名业务标识)、手动配对
- **配对策略:** 自动配对(推荐) / 手动配对 / 一对多支持

### 4.3 业务补充区

**功能定位:** 可选的中文业务需求补充说明输入框
- 最大字数: 2000字符
- 提供实时字数统计和使用提示
- 默认折叠,按需展开

### 4.4 批量进度面板

**触发条件:** 仅在"批量处理"标签页显示

**核心组件:**
1. **总进度概览:** 总计/已完成/进行中/等待中/异常 统计卡片 + 总进度条
2. **文件对执行列表:** 每个文件对的独立状态卡片(等待/解析/Agent执行/完成/异常)
3. **批量操作按钮组:** 暂停全部 / 取消剩余任务 / 导出全部报告

**SSE实时更新机制:**
```javascript
class BatchProgressManager {
  connect(batchId) {
    this.eventSource = new EventSource(`/api/batch/progress/${batchId}`);
    
    // 监听事件流
    this.eventSource.addEventListener('progress', (e) => this.handleProgress(e));
    this.eventSource.addEventListener('pair_complete', (e) => this.handleComplete(e));
    this.eventSource.addEventListener('batch_complete', (e) => this.handleBatchComplete(e));
    
    // 断线重连(3秒后)
    this.eventSource.onerror = () => setTimeout(() => this.connect(batchId), 3000);
  }
}
```

### 4.5 结果展示区

**核心展示内容:**

1. **纠错摘要卡片**
   - 总检查项 / 一致数 / 不一致数 / 通过率
   - 审查耗时 / 参与Agent数量 / 重试次数

2. **不一致项列表**(筛选/排序/搜索)
   - 每个问题以卡片形式展示
   - 支持按类型筛选(映射一致性/JOIN逻辑/NULL处理/聚合窗口/方言兼容)
   - 支持按严重程度排序
   - 点击展开详情视图

3. **Finding详情展开视图**
   - ❌ 问题原因(中文说明)
   - 📝 原始SQL片段(语法高亮)
   - 📋 IT-Mapping参考标准(表格形式)
   - 💡 修复建议(可选)

4. **导出操作栏**
   - 📥 下载纠错报告(.docx)
   - 💾 下载标注SQL(.sql)
   - 📝 导出Markdown(.md)

---

## 五、用户交互流程设计

### 5.1 单次纠错完整流程

```
用户打开网页 → 检查Ollama状态 → 上传IT-Mapping(.xlsx) 
→ 上传SQL(.sql) [可选:输入业务补充] → 点击"开始纠错"
→ POST /api/review → 返回task_id → 轮询GET /api/progress/{id} (每2秒)
→ 任务完成 → GET /api/result/{id} → 渲染结果
→ 用户查看/筛选/搜索不一致项 → 展开详情查看对比 → 下载报告
```

**流程控制器核心代码:**
```javascript
class SingleReviewFlowController {
  async startReview() {
    if (!this.validateInputs()) return;  // 校验两个文件都已上传
    
    const response = await fetch('/api/review', {
      method: 'POST',
      body: JSON.stringify({
        mapping_file: mappingUploader.file.name,
        sql_content: sqlUploader.content,
        business_context: businessInputManager.getValue(),
        dialect: detectedDialect
      })
    });
    
    this.taskId = (await response.json()).task_id;
    this.startPolling();  // 开始轮询进度
  }
}
```

### 5.2 批量处理完整流程

```
选择"批量处理"标签 → 添加多组文件对(逐个/批量文件夹/拖拽多文件)
→ 确认配对关系(自动/手动调整) → 点击"开始批量纠错"
→ POST /api/batch/upload → 返回batch_id → POST /api/batch/start
→ 建立SSE连接 GET /api/batch/progress/{batch_id}
→ 实时接收 progress/pair_complete/pair_error/batch_complete 事件
→ 更新UI(总进度条/各文件对状态卡/统计数字)
→ 支持暂停/取消/导出已完成的报告
```

---

## 六、组件详细设计规范

### 6.1 通用组件库

本文档定义了一套完整的通用组件库,包括:

**基础组件:**
- Button (按钮): primary/success/warning/danger/outline 变体, sm/base/lg 尺寸
- Card (卡片): 标准卡片容器,带hover阴影效果
- Input/Textarea/Select (表单控件): 统一的focus样式和error状态
- Badge/Tag (徽章/标签): 用于状态标识和分类
- ProgressBar (进度条): 带shimmer动画效果

**复合组件:**
- UploadZone (上传区域): 拖拽支持、多状态切换(默认/悬停/上传中/成功)
- FindingCard (发现项卡片): 可折叠的详情视图
- Toast (提示消息): success/error/warning/info 四种类型,自动消失
- Loading (加载遮罩): 全屏loading动画
- Modal (弹窗): 确认对话框

**所有组件均采用纯CSS实现,无第三方依赖**

### 6.2 CSS样式示例(按钮组件)

```css
.btn {
  display: inline-flex;
  align-items: center;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  border: 1px solid transparent;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.btn-primary { background: var(--primary-color); color: #fff; }
.btn-disabled { opacity: 0.6; cursor: not-allowed; }
```

---

## 七、前端API对接方案

### 7.1 API接口清单(14个接口)

| 接口路径 | 方法 | 用途 | 调用时机 |
|---------|------|------|---------|
| `/api/status` | GET | 查询Ollama连接状态 | 页面加载/30s轮询 |
| `/api/upload` | POST | 上传并解析IT-Mapping | 用户上传Excel时 |
| `/api/review` | POST | 启动单次纠错任务 | 点击开始纠错 |
| `/api/progress/{task_id}` | GET | 查询任务进度 | 每2秒轮询 |
| `/api/result/{task_id}` | GET | 获取完整纠错结果 | 任务完成后 |
| `/api/download/report/{task_id}` | GET | 下载Word报告 | 用户点击下载 |
| `/api/download/annotated-sql/{task_id}` | GET | 下载标注SQL | 用户点击下载 |
| `/api/export/{task_id}` | GET | 导出Markdown | 用户点击导出 |
| `/api/batch/upload` | POST | 批量上传文件对 | 批量模式 |
| `/api/batch/start` | POST | 开始批量任务 | 点击开始批量 |
| `/api/batch/progress/{batch_id}` | GET | SSE实时进度流 | 建立长连接 |
| `/api/batch/pause/{batch_id}` | POST | 暂停批量 | 用户点击暂停 |
| `/api/batch/cancel/{batch_id}` | POST | 取消批量 | 用户点击取消 |
| `/api/batch/export/{batch_id}` | GET | 批量导出 | 用户点击导出 |
| `/api/history` | GET | 查询历史记录 | 进入历史页 |

### 7.2 API服务封装层

```javascript
class ApiService {
  async request(url, options = {}) {
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      ...options
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return await response.json();
  }
  
  async uploadMapping(file) {
    const formData = new FormData();
    formData.append('file', file);
    return this.request('/api/upload', {
      method: 'POST',
      body: formData,
      headers: {}  // 浏览器自动设置multipart/form-data
    });
  }
}

const api = new ApiService();
```

### 7.3 统一响应格式

```typescript
interface ApiResponse<T> {
  success: boolean;
  code: number;           // 200=成功
  message?: string;       // 失败时的提示信息
  data?: T;               // 业务数据
  error?: string;         // 错误详情(调试用)
  timestamp: string;      // 服务器时间戳
}
```

### 7.4 关键接口数据结构示例

**POST /api/upload 响应:**
```json
{
  "success": true,
  "data": {
    "tables": [{"alias": "T", "name": "DWD_DM_T04_DEP_ACCT_INFO"}],
    "relationships": [{"from": "T", "to": "T1", "type": "LEFT JOIN"}],
    "field_mappings": [{
      "target": "F010002",
      "source_table": "T",
      "source_field": "ORG_NO",
      "logic": "截取金融许可证号前11位拼接机构编号"
    }]
  }
}
```

**GET /api/result/{task_id} 响应:**
```json
{
  "data": {
    "total_checks": 48,
    "consistent_count": 42,
    "inconsistent_count": 6,
    "findings": [{
      "status": "inconsistent",
      "agent": "mapping_check",
      "location": "第25行",
      "issue": "缺少字段拼接逻辑",
      "explanation": "IT-Mapping要求...",
      "original_sql": "T.ORG_NO AS F010002,",
      "mapping_ref": {...},
      "suggestion": "SUBSTR(...) || ..."
    }]
  }
}
```

**SSE事件数据格式:**
```javascript
// progress事件
{ event: 'progress', data: '{"pair_id":"xxx","status":"agents","progress":45}' }

// pair_complete事件
{ event: 'pair_complete', data: '{"pair_id":"xxx","findings_count":3}' }

// batch_complete事件
{ event: 'batch_complete', data: '{"total_pairs":12,"completed":11,"errors":1}' }
```

---

## 八、数据处理逻辑

### 8.1 集中式状态管理

采用**发布-订阅模式**,统一管理全局状态:

```javascript
class AppState {
  constructor() {
    this.state = {
      system: { ollamaConnected: false },
      currentMode: 'single',  // single | batch | history
      files: { mapping: null, sql: null, sqlContent: '' },
      singleTask: { taskId: null, status: 'idle' },
      batchTask: { batchId: null, pairStates: {} },
      ui: { activeTab: 'single' }
    };
    this.subscribers = new Map();
  }
  
  setState(path, value) {
    // 更新状态并通知订阅者
    this.notify(path, value);
  }
  
  subscribe(path, callback) {
    // 订阅状态变化,返回取消订阅函数
  }
}

const appState = new AppState();
```

### 8.2 文件处理管道

```javascript
class FileProcessingPipeline {
  static async processMappingFile(file) {
    const steps = [
      { name: 'validate', fn: this.validateFile },     // 格式/大小校验
      { name: 'upload', fn: this.uploadToServer },       // POST /api/upload
      { name: 'parse', fn: this.waitForParsing },        // 等待解析完成
      { name: 'store', fn: this.storeResult }            // 存储到全局状态
    ];
    
    let result = file;
    for (const step of steps) {
      result = await step.fn.call(this, result);
    }
    return result;
  }
}
```

### 8.3 数据转换工具集

```javascript
const DataTransformers = {
  formatResultForDisplay(apiResult) {
    return {
      summary: { totalChecks, passRate, duration },
      findings: apiResult.findings.map(f => ({
        ...f,
        severityLabel: this.getSeverityLabel(f),
        severityClass: this.getSeverityClass(f),
        truncatedIssue: f.issue?.substring(0, 80)
      }))
    };
  },
  
  formatDuration(seconds) { /* 格式化为 X分X秒 */ },
  formatFileSize(bytes) { /* 格式化为 KB/MB */ }
};
```

---

## 九、界面原型图

### 9.1 首页整体布局(单次纠错模式)

详见文档中的ASCII艺术图,包括:
- 顶部导航栏(Ollama状态指示器)
- 文件上传区(IT-Mapping + SQL 并排双列布局)
- 业务补充输入区(可折叠)
- 开始纠错按钮
- 结果展示区(摘要卡片 + 不一致项列表 + 导出按钮)

### 9.2 批量处理模式界面

详见文档中的ASCII艺术图,包括:
- 文件对列表(显示配对关系和状态)
- 批量进度面板(总进度 + 各文件对状态卡片)
- 批量操作控制(暂停/取消/导出)

### 9.3 Finding详情展开视图

详见文档中的ASCII艺术图,包括:
- 问题原因(红色醒目标识)
- 原始SQL片段(语法高亮,问题行高亮)
- IT-Mapping参考标准(表格对比)
- 修复建议(绿色提示框)

---

## 十、技术实现要点

### 10.1 项目目录结构(前端部分)

```
static/
├── css/
│   ├── style.css           # 主样式(变量/重置/布局)
│   ├── components.css      # 组件样式
│   └── animations.css      # 动画效果
├── js/
│   ├── app.js              # 应用入口
│   ├── utils/
│   │   ├── api.js          # API服务封装
│   │   ├── state.js        # 状态管理器
│   │   └── formatters.js   # 格式化工具
│   ├── components/
│   │   ├── UploadZone.js   # 上传区域组件
│   │   ├── FindingCard.js  # 发现项卡片
│   │   └── Toast.js        # 提示消息组件
│   └── managers/
│       ├── MappingUploader.js
│       ├── BatchProgress.js  # SSE管理
│       └── ReviewFlow.js     # 流程控制
└── lib/
    └── highlightjs/         # SQL语法高亮库
```

### 10.2 核心技术点

1. **拖拽上传实现:** HTML5 Drag & Drop API + FileReader API
2. **实时通信:** SSE (Server-Sent Events) 用于批量进度推送
3. **语法高亮:** Highlight.js 库(可选增强)
4. **状态管理:** 发布-订阅模式的轻量级状态机
5. **错误处理:** 全局fetch拦截器 + 统一错误提示Toast
6. **性能优化:** 虚拟滚动(长列表)、懒加载、防抖节流

### 10.3 第三方依赖

| 库名 | 版本 | 用途 | 引入方式 |
|------|------|------|---------|
| highlight.js | 最新版 | SQL语法高亮 | CDN `<script>` |

**注意:** 除highlight.js外,不引入任何其他第三方JavaScript库**

---

## 十一、关键功能模块说明

### 11.1 IT-Mapping智能解析与预览

**功能描述:** 用户上传.xlsx文件后,前端立即调用`/api/upload`接口进行服务端解析,返回结构化的表清单、字段映射、关联关系等数据,并在UI上以摘要形式展示。

**技术要点:**
- 使用FormData上传文件,浏览器自动设置multipart/form-data
- 解析是同步阻塞调用(服务端pandas解析),需显示loading状态
- 解析结果存储在全局状态中,供后续纠错流程使用

### 11.2 SQL方言自动检测

**功能描述:** 读取用户上传的.sql文件内容后,通过简单的正则匹配规则自动识别SQL方言(Oracle或Hive)。

**检测规则:**
- Oracle特征: `NVL()` 函数、`ROWNUM` 伪列
- Hive特征: `LATERAL VIEW` 语法、`EXPLODE()` 函数
- 默认: Oracle

### 11.3 SSE实时进度推送

**功能描述:** 在批量处理模式下,通过SSE建立长连接,实时接收后端推送的每个文件对的执行进度。

**实现细节:**
- EventSource对象自动管理连接(不支持自定义headers)
- 监听4种事件类型: progress / pair_complete / pair_error / batch_complete
- 断线自动重连(3秒延迟指数退避)
- 内存中维护pairStates Map,用于渲染UI

### 11.4 不一致项筛选与排序

**功能描述:** 结果展示区提供多维度的筛选和排序能力,帮助用户快速定位关键问题。

**筛选项:**
- 状态筛选: 全部/仅不一致/仅一致
- 类型筛选: 映射一致性/JOIN逻辑/NULL处理/聚合窗口/方言兼容
- 文本搜索: 搜索问题描述和原因说明

**排序方式:**
- 严重程度降序(基于关键词权重算法)
- 行号升序
- Agent类型分组

### 11.5 报告导出功能

**功能描述:** 提供3种格式的导出能力,满足不同使用场景。

| 格式 | 文件扩展名 | 内容 | 适用场景 |
|------|-----------|------|---------|
| Word文档 | .docx | 完整比对摘要+列表+原因+参考 | 管理层汇报/归档 |
| 标注SQL | .sql | 原始SQL+问题行注释(不修改源码) | 开发人员定位修复 |
| Markdown | .md | 轻量级文本报告 | 版本管理/Git跟踪 |

**技术实现:** 通过`<a>`标签的download属性触发浏览器下载,后端返回对应格式的文件流。

---

## 十二、性能优化与安全考虑

### 12.1 性能优化策略

1. **文件上传优化:**
   - 大文件显示上传进度条(使用XMLHttpRequest或Fetch+ReadableStream)
   - 限制最大文件50MB,避免内存溢出
   - SQL文件前端本地读取,不上传服务器(减少网络传输)

2. **渲染性能优化:**
   - 不一致项列表超过100条时启用虚拟滚动(只渲染可视区域)
   - Finding详情默认折叠,按需展开(减少初始DOM节点)
   - CSS动画使用transform/opacity属性(触发GPU加速)

3. **网络请求优化:**
   - API响应缓存(短时间内的重复请求)
   - SSE替代WebSocket(更轻量,单向推送足够)
   - 图片/图标使用SVG或CSS绘制(减少HTTP请求)

### 12.2 安全考虑

1. **XSS防护:**
   - 所有动态插入HTML的内容必须经过`escapeHtml()`转义
   - 使用textContent而非innerHTML插入用户输入
   - SQL预览使用Highlight.js的安全渲染模式

2. **CSRF防护:**
   - 后端Flask应启用CSRF保护(WTF-Token)
   - 所有POST请求携带CSRF Token

3. **输入验证:**
   - 前端双重校验:文件格式/大小/必填项
   - 业务输入限制2000字符,防止超长文本攻击
   - 文件名过滤特殊字符(`../`, `\0`等)

4. **敏感信息保护:**
   - API错误信息不暴露服务器内部细节(仅显示友好提示)
   - Task ID/Batch ID使用随机UUID,防止顺序猜测
   - 下载链接设置过期时间(临时URL)

---

## 附录A: 快速启动指南

### A.1 环境准备

```bash
# 1. 启动 Redis
redis-server

# 2. 启动 Celery Worker
celery -A celery_app worker -c 1 --loglevel=info

# 3. 启动 Flask 服务
flask run --host=0.0.0.0 --port=5000

# 4. 确保 Ollama 运行并加载模型
ollama serve
ollama pull qwen2.5-coder:32b-q4_K_M
```

### A.2 浏览器访问

打开浏览器访问: `http://localhost:5000`

首次加载会自动检测Ollama连接状态,导航栏显示绿色"● Ollama已连接"表示就绪。

### A.3 典型使用流程(单次纠错)

1. 拖拽上传 `存款协议_ITMapping.xlsx` → 系统自动解析,显示"5张表,48个字段"
2. 拖拽上传 `deposit_proc.sql` → 显示SQL预览,识别为Oracle方言
3. (可选) 展开"业务需求补充",输入特殊加工规则说明
4. 点击 **"▶️ 开始纠错"** 按钮
5. 等待约3分钟(观察进度条和步骤指示器)
6. 查看结果:摘要显示"48项检查,42一致,6不一致"
7. 点击不一致项卡片展开详情,查看SQL vs IT-Mapping对比
8. 点击 **"📥 下载纠错报告(.docx)"** 获取完整Word文档

---

## 附录B: 故障排查

| 症状 | 可能原因 | 解决方案 |
|------|---------|---------|
| 导航栏显示红色"○ Ollama未连接" | Ollama未启动或端口错误 | 检查`ollama ps`,确认服务运行在11434端口 |
| 上传Excel后一直显示"解析中..." | pandas/openpyxl未安装 | `pip install pandas openpyxl` |
| 点击开始纠错无反应 | 未同时上传两个文件 | 检查两个上传区是否都显示✅ |
| 批量进度不更新 | Redis未启动或Celery Worker未启动 | 检查Redis和Celery进程 |
| SSE连接频繁断开重连 | 网络不稳定或浏览器限制 | 检查浏览器控制台错误日志 |
| 下载报告404错误 | 任务ID不存在或已过期 | 重新执行纠错获取新Task ID |

---

**文档结束**

> 本设计文档严格遵循《SQL智能纠错系统_网站架构设计方案V0.5》的所有技术选型和架构约束。
> 
> 如有疑问或需要进一步细化某个模块的设计,请参考架构方案原文或联系技术团队。
