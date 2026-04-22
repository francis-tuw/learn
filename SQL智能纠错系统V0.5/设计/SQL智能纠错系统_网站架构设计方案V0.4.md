**SQL智能纠错系统**

网站架构设计方案

基于 CrewAI + Ollama 的多 Agent 协作 Web 应用

支持 IT-Mapping 上传 + SQL 存储过程纠错

前端：纯 HTML/CSS/JS \| 后端：Flask \| 大模型：Ollama

2026年4月

**一、项目概述与设计目标**

**1.1 项目背景**

在金融数据报送场景中，存储过程（ETL SQL）负责将源系统数据按照 IT-Mapping 规则加工后加载到目标报送表。这些 SQL 存储过程的逻辑正确性直接影响报送数据的准确性。然而，存储过程通常涉及多表 JOIN、复杂的字段加工逻辑、码值转换等，人工审查效率低且容易遗漏。

本方案设计一个 Web 应用系统------"SQL智能纠错系统"，用户可以上传 IT-Mapping Excel 文件和 SQL 存储过程，系统自动解析 IT-Mapping 中的表结构、字段映射、表间关联关系等信息，结合多个 AI Agent 的协作审查，对 SQL 存储过程进行智能纠错。

**1.2 IT-Mapping 文件结构分析**

通过分析实际的 IT-Mapping Excel 文件（以《存款协议》为例），其结构如下：

**Sheet 1：数据源（DataSet）**

包含源数据表清单和表间关联关系：

-   数据表清单：包含序号、所属系统、数据表名、表别名、中文名称

-   表间关联关系：明确定义了各表之间的 JOIN 条件（如「【T】存款账户信息.ORG\_NO 等值关联 【T1】机构信息.ORG\_NO」）

-   筛选条件：包含数据日期等过滤规则

**Sheet 2：数据映射（DataMap）**

定义目标表的字段映射规则，共 18 列，核心字段包括：

  --------------------- -------------------------------------------------- -------------------------------------
  **列名**              **内容说明**                                       **纠错价值**
  字段中文名称          目标表字段的业务含义                               验证 SQL 字段映射是否与业务含义匹配
  字段英文名            目标表字段的技术名称                               验证 SQL 中字段名是否正确
  数据类型              如 VARCHAR2(60)、CHAR(2)、DECIMAL                  验证 SQL 中的类型转换是否正确
  值域参考              如 YYYY-MM-DD、码值字典                            验证数据格式和码值映射
  取数方式              字段直取 / 逻辑加工 / 默认值                       判断 SQL 加工逻辑的复杂度
  数据表（源）          源数据表名称（如 DWD\_DM\_T04\_DEP\_ACCT\_INFO）   验证 SQL 中的表名引用
  字段名（英文/中文）   源表的字段名称                                     验证 SQL 中的源字段引用
  字段加工逻辑          如"截取金融许可证号前11位拼接机构编号"             验证 SQL 加工逻辑与映射规则是否一致
  --------------------- -------------------------------------------------- -------------------------------------

**1.3 设计目标**

-   **业务价值：**将 IT-Mapping 中的表结构、字段映射、表间关联关系作为 SQL 纠错的"金标准"，大幅提升纠错的准确性

-   **中文优先：**全流程中文交互，包括业务需求描述、纠错报告、修复建议

-   **易用性：**通过 Web 界面上传文件，无需安装任何客户端

-   **本地化：**全部大模型通过 Ollama 本地运行，保障数据安全

-   **可扩展：**支持多种 IT-Mapping 模板，可根据不同业务场景扩展

**1.4 设计约束**

-   前端：纯 HTML/CSS/JS，不使用前端框架

-   后端：Flask 框架

-   Agent 编排：CrewAI

-   大模型：Ollama 本地部署

-   SQL 方言：Oracle / Inceptor（Hive）

-   纠错范围：以逻辑错误为主

**二、系统整体架构**

**2.1 架构总览**

系统采用前后端分离架构，分为四层：

  ---------- --------------- ------------------ ---------------------------------------
  **层级**   **组件**        **技术选型**       **职责**
  展示层     Web 前端        纯 HTML/CSS/JS     文件上传、结果展示、用户交互
  接口层     API 服务        Flask              文件解析、任务调度、状态管理
  Agent 层   多 Agent 协作   CrewAI + Ollama    IT-Mapping 解析、SQL 审查、裁决、报告
  工具层     解析工具        pandas / sqlglot   Excel 解析、SQL 结构化解析
  ---------- --------------- ------------------ ---------------------------------------

**2.2 数据流向**

用户操作流程如下：

**Step 1：**用户上传 IT-Mapping Excel 文件（包含数据源和数据映射两个 Sheet）

**Step 2：**用户上传待审查的 SQL 存储过程文件（.sql）

**Step 3：**可选：输入中文业务需求补充说明

**Step 4：**点击"开始纠错"，系统自动执行多 Agent 审查流程

**Step 5：**查看纠错报告，包含错误列表、修复建议、修复前后 SQL 对比

后台数据处理流向：

**1. Excel 解析 →** 提取表清单、表间关联关系、字段映射规则，生成结构化 JSON

**2. SQL 解析 →** 提取 SQL 结构、表引用、字段引用、JOIN 条件等

**3. 交叉比对 →** 将 SQL 实际写法与 IT-Mapping 规则进行交叉验证

**4. 多维审查 →** 4 个专业 Agent 并行审查（JOIN / NULL / 聚合 / 方言）

**5. 裁决汇总 →** 裁决 Agent 综合所有审查结果，生成统一建议

**6. 报告生成 →** 生成中文纠错报告，返回前端展示

**三、Agent 角色设计（升级版）**

**3.1 与原方案的关键差异**

相比之前的纯 SQL 纠错方案，新方案因为引入了 IT-Mapping，产生了以下关键变化：

  -------------- ---------------------------- -------------------------------------------------------
  **维度**       **原方案**                   **新方案（引入 IT-Mapping）**
  上下文来源     仅依赖用户的中文描述         IT-Mapping 提供精确的表结构、字段映射、表间关联关系
  JOIN 验证      基于经验推断 JOIN 是否合理   直接对比 IT-Mapping 中定义的表间关联关系，精确验证
  字段映射验证   无法验证                     对比 SQL 中的字段引用与 IT-Mapping 的映射规则是否一致
  加工逻辑验证   无法验证                     对比 SQL 加工逻辑与 IT-Mapping 的字段加工逻辑描述
  数据类型验证   基于经验推断                 直接对比 IT-Mapping 中定义的数据类型
  码值验证       无法验证                     利用 IT-Mapping 中的值域参考和码值字典验证
  -------------- ---------------------------- -------------------------------------------------------

**3.2 Agent 角色总览（共 9 个）**

  ----------------------- ---------------------------------------------- ------------------- ------------------
  **Agent 角色**          **职责定位**                                   **绑定模型**        **核心输入**
  IT-Mapping 解析 Agent   解析 Excel 中的表结构、字段映射、表间关联      Qwen2.5-Coder 32B   Excel 结构化数据
  中文理解 Agent          理解用户中文业务需求补充说明                   Qwen2.5-Coder 32B   用户输入文本
  SQL 解析 Agent          结构化解析 SQL 存储过程                        Qwen2.5-Coder 32B   SQL 文件
  映射一致性审查 Agent    对比 SQL 与 IT-Mapping 的字段映射是否一致      Qwen2.5-Coder 32B   SQL + IT-Mapping
  JOIN 审查 Agent         审查 JOIN 逻辑与 IT-Mapping 表间关联是否一致   Qwen2.5-Coder 32B   SQL + 表关联关系
  NULL 处理审查 Agent     审查 NULL 值处理逻辑                           Qwen2.5-Coder 32B   SQL + 字段属性
  聚合与窗口审查 Agent    审查 GROUP BY、窗口函数逻辑                    Qwen2.5-Coder 32B   SQL
  方言兼容审查 Agent      审查 Oracle/Hive 语法兼容性                    Qwen2.5-Coder 32B   SQL
  裁决 Agent              综合审查结果，生成统一建议                     Qwen2.5-Coder 32B   所有审查结果
  报告 Agent              生成中文纠错报告                               Qwen2.5-Coder 32B   裁决结果
  ----------------------- ---------------------------------------------- ------------------- ------------------

**3.3 新增 Agent 详细设计**

**3.3.1 IT-Mapping 解析 Agent（新增）**

**角色定位：**数据映射解析专家

负责将 Excel 解析后的结构化数据进一步整理，生成可供其他 Agent 直接使用的上下文。

**核心能力：**

-   解析"数据源"Sheet：提取表清单、表别名、表间关联关系（JOIN 条件）、筛选条件

-   解析"数据映射"Sheet：提取目标表字段列表、源表字段映射、加工逻辑、数据类型、值域约束

-   构建表关联图：将表间关联关系转化为结构化的图数据（节点、边、关联类型）

-   识别分组结构：如 MP1 组别对应的字段范围

**输出格式：**

> {
>
> \"tables\": \[{\"alias\": \"T\", \"name\": \"DWD\_DM\_T04\_DEP\_ACCT\_INFO\", \"cn\_name\": \"存款账户信息\"}\],
>
> \"relationships\": \[{\"from\": \"T\", \"to\": \"T1\", \"type\": \"LEFT JOIN\", \"condition\": \"T.ORG\_NO = T1.ORG\_NO\"}\],
>
> \"filters\": \[\"数据日期 = 跑批基准日期\"\],
>
> \"field\_mappings\": \[{\"target\": \"F010002\", \"source\_table\": \"T\", \"source\_field\": \"ORG\_NO\", \"logic\": \"截取金融许可证号前11位拼接机构编号\"}\]
>
> }

**3.3.2 映射一致性审查 Agent（新增）**

**角色定位：**IT-Mapping 与 SQL 一致性审查专家

这是新方案中最核心的新增 Agent，负责将 SQL 存储过程的实际写法与 IT-Mapping 定义的规则进行逐项比对验证。

**审查维度：**

-   表引用一致性：SQL 中引用的表是否与 IT-Mapping 数据源一致

-   字段映射一致性：SQL 中的 SELECT 字段是否与 IT-Mapping 的目标字段一致

-   源字段引用一致性：SQL 中引用的源表字段是否与 IT-Mapping 的源字段匹配

-   加工逻辑一致性：SQL 中的加工逻辑（如 SUBSTR、CONCAT）是否与 IT-Mapping 的字段加工逻辑描述匹配

-   数据类型一致性：SQL 中的类型转换（CAST）是否与 IT-Mapping 定义的目标类型一致

-   码值映射一致性：SQL 中的 CASE WHEN 码值转换是否与 IT-Mapping 的值域参考匹配

-   缺失字段检测：IT-Mapping 中定义但 SQL 中未包含的字段

-   多余字段检测：SQL 中包含但 IT-Mapping 中未定义的字段

**四、工作流程设计（升级版）**

**4.1 完整工作流**

  ---------- ---------------------- ----------------------- --------------
  **步骤**   **任务名称**           **执行 Agent**          **执行方式**
  Step 1     IT-Mapping 解析        IT-Mapping 解析 Agent   同步
  Step 2     中文输入解析（可选）   中文理解 Agent          同步
  Step 3     SQL 结构解析           SQL 解析 Agent          同步
  Step 4a    映射一致性审查         映射一致性审查 Agent    异步并行
  Step 4b    JOIN 逻辑审查          JOIN 审查 Agent         异步并行
  Step 4c    NULL 处理审查          NULL 处理审查 Agent     异步并行
  Step 4d    聚合窗口审查           聚合与窗口审查 Agent    异步并行
  Step 4e    方言兼容审查           方言兼容审查 Agent      异步并行
  Step 5     综合裁决               裁决 Agent              同步
  Step 6     报告生成               报告 Agent              同步
  ---------- ---------------------- ----------------------- --------------

**4.2 关键步骤说明**

**Step 1：IT-Mapping 解析（新增）**

这是新方案的核心新增步骤。系统首先通过 pandas 解析 Excel 文件，提取结构化数据，然后由 IT-Mapping 解析 Agent 进一步整理和补充。

**pandas 解析层（自动化）：**

-   读取"数据源"Sheet，提取表清单和表间关联关系

-   读取"数据映射"Sheet，提取每个字段的映射规则

-   解析表间关联关系中的 JOIN 类型、关联字段、筛选条件

**LLM 补充层（智能化）：**

-   将表间关联关系的自然语言描述转化为结构化的 JOIN 条件

-   识别复杂的加工逻辑描述（如"截取前11位拼接"转化为 SUBSTR+CONCAT）

-   构建完整的业务上下文

**Step 4a：映射一致性审查（新增）**

这是新方案中最具业务价值的审查步骤，将 SQL 存储过程与 IT-Mapping 规则逐项比对：

**典型发现示例：**

-   "IT-Mapping 要求机构ID = 金融许可证号前11位 + 机构编号，但 SQL 中直接取了 ORG\_NO，缺少拼接逻辑"

-   "IT-Mapping 定义了 48 个目标字段，但 SQL 中只有 45 个，缺少 F010041、F010042、F010043"

-   "IT-Mapping 要求客户类型为 CHAR(2)，但 SQL 中未做类型转换，可能导致长度不匹配"

-   "IT-Mapping 定义存款账户类型的码值映射为 01-10，但 SQL 中的 CASE WHEN 缺少 08、09、10 的分支"

**4.3 闭环验证机制设计**

为确保每个 Agent 的输出质量，系统在"提取"和"检查"两个关键阶段均引入闭环验证机制。每次 Agent 输出后，系统自动进行格式校验和内容校验，不符合要求则附带反馈信息重新执行，直至输出达标或达到最大重试次数。同时，验证状态通过 SSE 实时推送到前端，让用户可见整个验证过程。

**4.3.1 闭环验证流程图**

  ---------- ---------------------- ----------------------------------------------
  **步骤**   **操作**               **说明**
  1          Agent 执行任务         Agent 根据提示词生成输出
  2          格式校验（程序化）     检查输出是否为合法 JSON，必填字段是否完整
  3          内容校骏（LLM 辅助）   检查输出内容是否与输入一致、是否存在逻辑错误
  4          校验通过？             是 → 输出结果；否 → 生成反馈并重试
  5          达到最大重试次数？     是 → 记录警告，使用最佳可用输出继续流程
  6          输出结果               将验证通过的输出传递给下一个 Agent
  ---------- ---------------------- ----------------------------------------------

**4.3.2 提取阶段的闭环验证**

提取阶段包括 IT-Mapping 解析 Agent（Step 1）、中文理解 Agent（Step 2）和 SQL 解析 Agent（Step 3），其输出是后续所有审查 Agent 的基础，必须确保准确性。

**格式校骏规则：**

-   IT-Mapping 解析 Agent：输出必须是合法 JSON，包含 tables、relationships、filters、field\_mappings 字段

-   中文理解 Agent：输出必须是合法 JSON，包含 business\_domain、key\_rules、table\_relationships 字段

-   SQL 解析 Agent：输出必须是合法 JSON，包含 tables、joins、functions、subqueries、dialect 字段

-   所有字段值不能为空字符串或 null

**内容校骏规则（通过 LLM 辅助验证）：**

-   IT-Mapping 解析：提取的表数量是否与 Excel 中的表数量一致（无遍漏）

-   IT-Mapping 解析：字段映射数量是否与 Excel "数据映射"Sheet 的行数一致

-   中文理解：提取的业务规则是否与用户输入内容一致（无遍漏、无编造）

-   SQL 解析：提取的表名、字段名是否与原始 SQL 一致（无遍漏、无多余）

-   表关联关系是否与 SQL 中的 JOIN 语句一一对应

**反馈与重试机制：**

-   格式校验失败：直接向 Agent 返回"输出格式不符合要求，请严格按照 JSON 格式输出"的反馈

-   内容校骏失败：向 Agent 返回具体的问题描述（如"Excel 中有 48 个字段映射，但你只提取了 45 个，请检查"）

-   最大重试次数：3 次（提取阶段），超过后记录警告日志并使用最佳可用输出

**4.3.3 检查阶段的闭环验证**

检查阶段包括 5 个并行审查 Agent（Step 4a-4e）和裁决 Agent（Step 5），其输出直接决定纠错质量。

**格式校骏规则：**

-   审查 Agent 输出必须是合法 JSON，包含 agent、findings 数组

-   每个 finding 必须包含 severity、location、issue、original\_sql、suggested\_fix、explanation

-   severity 必须是以下枚举值之一：致命、严重、一般、建议

-   location 必须包含 SQL 行号信息

-   suggested\_fix 不能为空，必须提供具体的修复 SQL 片段

**内容校骏规则（通过 LLM 辅助验证）：**

-   报告的错误位置是否与原始 SQL 实际内容匹配（防止行号编造）

-   suggested\_fix 是否真正解决了报告的问题（防止修复方案无效）

-   映射一致性审查：报告的缺失/多余字段是否与 IT-Mapping 实际内容一致

-   是否存在重复报告（同一个问题被多次报告）

-   是否存在明显的误报（报告的错误实际上不是问题）

**反馈与重试机制：**

-   格式错误：返回缺失字段清单和正确格式示例，要求 Agent 补全

-   内容错误：返回具体的问题列表（如"第 3 条 finding 的 suggested\_fix 未解决报告的问题，请修改"）

-   最大重试次数：2 次（检查阶段），超过后记录警告并使用最佳可用输出

**4.3.4 闭环验证参数配置**

  -------------- ------------------------- ------------------------- --------------------------------------------
  **参数**       **提取阶段**              **检查阶段**              **说明**
  最大重试次数   3                         2                         防止无限循环，提取阶段允许更多重试
  格式校骏方式   程序化（JSON Schema）     程序化（JSON Schema）     使用 Pydantic 模型进行结构化校验
  内容校骏方式   LLM 辅助验证              LLM 辅助验证              使用轻量级 LLM 或同一模型进行内容审核
  重试等待时间   1s                        2s                        重试前的短暂等待，避免立即重试导致相同错误
  失败处理策略   使用最佳可用输出 + 警告   使用最佳可用输出 + 警告   不会中断整个流程，保证系统鲁棒性
  前端实时推送   SSE 事件                  SSE 事件                  验证状态变化实时推送到前端展示
  -------------- ------------------------- ------------------------- --------------------------------------------

**五、前端设计**

**5.1 页面结构**

系统采用单页应用（SPA）模式，共设计 4 个核心页面区域：

  ------------ ----------------------------- ----------------------------------------
  **区域**     **功能**                      **核心交互**
  顶部导航栏   系统标题、状态指示            Ollama 连接状态、模型加载状态
  文件上传区   上传 IT-Mapping 和 SQL 文件   拖拽上传、文件预览、表结构预览
  业务补充区   输入中文业务需求补充说明      多行文本输入框
  结果展示区   展示纠错报告                  错误列表、修复建议、SQL 对比、导出报告
  ------------ ----------------------------- ----------------------------------------

**5.2 文件上传区设计**

**IT-Mapping 上传：**

-   支持拖拽上传或点击选择文件（.xlsx 格式）

-   上传后自动解析并预览：显示识别到的数据表数量、字段映射数量、表间关联数量

-   显示表关联图的简化视图（可选）

**SQL 文件上传：**

-   支持 .sql / .txt 格式

-   上传后显示 SQL 内容预览，支持语法高亮

-   自动识别 SQL 方言（Oracle / Hive）

**5.3 结果展示区设计**

**纠错摘要卡片：**

-   顶部显示纠错统计：总错误数、致命数、严重数、一般数、建议数

**错误列表：**

-   每个错误显示为一张卡片，包含：严重程度标签、错误类型、错误描述、位置标注

-   支持按严重程度、错误类型筛选和排序

-   点击卡片展开详情：原始 SQL 片段 vs 建议修复后的 SQL 片段（并排对比）

**导出功能：**

-   导出为 Markdown 报告

-   导出为 Word 文档（.docx）

-   复制修复后的完整 SQL

**六、后端设计**

**6.1 Flask API 接口设计**

  ---------- ---------------------------------------------- ---------------------------------------------
  **接口**   **方法**                                       **功能说明**
  文件上传   POST /api/upload                               上传 IT-Mapping 和 SQL 文件，返回解析预览
  开始纠错   POST /api/review                               触发多 Agent 审查流程，返回任务 ID
  查询进度   GET /api/progress/\<task\_id\>                 查询审查任务的当前进度（百分比 + 当前步骤）
  获取结果   GET /api/result/\<task\_id\>                   获取完整的纠错报告
  导出报告   GET /api/export/\<task\_id\>?format=md\|docx   导出纠错报告为指定格式
  系统状态   GET /api/status                                查询 Ollama 连接状态、模型加载情况
  历史记录   GET /api/history                               查询历史纠错记录列表
  ---------- ---------------------------------------------- ---------------------------------------------

**6.2 后端项目结构**

> sql-review-web/
>
> ├── app.py \# Flask 主应用（路由、会话管理）
>
> ├── config.py \# 配置文件（Ollama 地址、模型名、上传目录）
>
> ├── services/
>
> │ ├── excel\_parser.py \# IT-Mapping Excel 解析服务
>
> │ ├── sql\_parser.py \# SQL 文件解析服务
>
> │ └── review\_service.py \# 审查任务调度服务
>
> ├── agents/ \# CrewAI Agent 定义
>
> │ ├── mapping\_parser\_agent.py \# IT-Mapping 解析 Agent
>
> │ ├── chinese\_agent.py \# 中文理解 Agent
>
> │ ├── sql\_parse\_agent.py \# SQL 解析 Agent
>
> │ ├── mapping\_check\_agent.py \# 映射一致性审查 Agent
>
> │ ├── join\_review\_agent.py \# JOIN 审查 Agent
>
> │ ├── null\_review\_agent.py \# NULL 审查 Agent
>
> │ ├── agg\_review\_agent.py \# 聚合窗口审查 Agent
>
> │ ├── dialect\_agent.py \# 方言兼容审查 Agent
>
> │ ├── judge\_agent.py \# 裁决 Agent
>
> │ └── reporter\_agent.py \# 报告 Agent
>
> ├── crew/
>
> │ └── sql\_review\_crew.py \# Crew 编排
>
> ├── prompts/ \# 提示词模板
>
> ├── static/ \# 前端静态文件
>
> │ ├── css/style.css
>
> │ ├── js/app.js
>
> │ └── index.html
>
> ├── templates/ \# Jinja2 模板
>
> │ └── index.html
>
> ├── uploads/ \# 上传文件存储目录
>
> └── requirements.txt

**6.3 Excel 解析服务设计**

Excel 解析是连接用户输入和 Agent 审查的桥梁，采用"自动化解析 + LLM 补充"的两层架构：

**第一层：pandas 自动化解析（确保准确性）**

-   读取"数据源"Sheet，提取表别名、表名、表间关联关系文本

-   读取"数据映射"Sheet，提取每个字段的完整映射信息

-   处理合并单元格（如多表引用、多字段引用）

**第二层：LLM 智能补充（处理模糊性）**

-   将表间关联关系的自然语言描述解析为结构化 JOIN 条件

-   理解复杂的加工逻辑描述（如"截取前11位拼接"转化为 SQL 函数调用）

-   补充业务上下文信息

**6.4 闭环验证代码实现**

以下代码展示了网站版闭环验证的核心实现，包含 SSE 实时状态推送：

> from pydantic import BaseModel, ValidationError
>
> from typing import Optional, List
>
> import json, time, logging
>
> logger = logging.getLogger(\_\_name\_\_)
>
> \# ─── 格式校骏模型（Pydantic） ───
>
> class ITMappingOutput(BaseModel):
>
> tables: List\[dict\]
>
> relationships: List\[dict\]
>
> filters: List\[str\]
>
> field\_mappings: List\[dict\]
>
> class FindingItem(BaseModel):
>
> severity: str \# 致命 \| 严重 \| 一般 \| 建议
>
> location: str
>
> issue: str
>
> original\_sql: str
>
> suggested\_fix: str
>
> explanation: str
>
> class ReviewOutput(BaseModel):
>
> agent: str
>
> findings: List\[FindingItem\]
>
> \# ─── 闭环验证核心函数（含 SSE 推送） ───
>
> def validate\_with\_retry(
>
> output\_text: str,
>
> pydantic\_model,
>
> content\_validator=None,
>
> max\_retries: int = 3,
>
> retry\_delay: float = 1.0,
>
> agent\_name: str = \"Agent\",
>
> sse\_callback=None \# SSE 推送回调（可选）
>
> ) -\> dict:
>
> \"\"\"
>
> 闭环验证：格式校骏 + 内容校骏，不通过则重试
>
> 支持 SSE 实时推送验证状态到前端
>
> \"\"\"
>
> warnings = \[\]
>
> best\_output = None
>
> for attempt in range(1, max\_retries + 1):
>
> \# 通知前端验证开始
>
> if sse\_callback:
>
> sse\_callback({\"event\": \"validation\_start\",
>
> \"data\": {\"agent\": agent\_name, \"attempt\": attempt}})
>
> \# Step 1: 格式校骏
>
> try:
>
> data = json.loads(output\_text)
>
> validated = pydantic\_model(\*\*data)
>
> best\_output = validated.model\_dump()
>
> except (json.JSONDecodeError, ValidationError) as e:
>
> feedback = f\"格式错误: {str(e)}\\n请严格按照 JSON 格式输出。\"
>
> if sse\_callback:
>
> sse\_callback({\"event\": \"validation\_retry\",
>
> \"data\": {\"agent\": agent\_name, \"attempt\": attempt,
>
> \"error\": \"format\", \"detail\": str(e)}})
>
> if attempt \< max\_retries:
>
> time.sleep(retry\_delay)
>
> return None, feedback
>
> warnings.append(f\"格式校骏始终未通过: {e}\")
>
> break
>
> \# Step 2: 内容校骏（如有）
>
> if content\_validator:
>
> is\_valid, content\_feedback = content\_validator(best\_output)
>
> if not is\_valid:
>
> if sse\_callback:
>
> sse\_callback({\"event\": \"validation\_retry\",
>
> \"data\": {\"agent\": agent\_name, \"attempt\": attempt,
>
> \"error\": \"content\", \"detail\": content\_feedback}})
>
> if attempt \< max\_retries:
>
> time.sleep(retry\_delay)
>
> return None, content\_feedback
>
> warnings.append(f\"内容校骏始终未通过: {content\_feedback}\")
>
> break
>
> \# 校骏通过
>
> if sse\_callback:
>
> sse\_callback({\"event\": \"validation\_pass\",
>
> \"data\": {\"agent\": agent\_name, \"attempt\": attempt}})
>
> return best\_output, None
>
> \# 达到最大重试次数
>
> if sse\_callback:
>
> sse\_callback({\"event\": \"validation\_warning\",
>
> \"data\": {\"agent\": agent\_name, \"warnings\": warnings}})
>
> return best\_output if best\_output else None, warnings

**七、模型选型与硬件配置（针对 AMD APU 优化）**

**7.1 硬件平台分析**

本方案针对 AMD Ryzen AI MAX 392 + Radeon 8060S + 64GB 统一内存平台进行优化。这是一款非常适合本地 AI 推理的 APU：

  ------------------- --------------------------- -----------------------------------------------
  **特性**            **配置**                    **优势**
  统一内存架构        64GB 可全部作为 VRAM 使用   远超独立显卡的 16GB/24GB 限制，可运行更大模型
  Radeon 8060S 核显   RDNA 3.5 架构，40 CU        支持 Vulkan 和 ROCm 双后端推理
  内存带宽            \~120 GB/s（LPDDR5X）       足够支撑 32B 级模型流畅推理
  ------------------- --------------------------- -----------------------------------------------

**7.2 模型选型推荐**

基于您的硬件配置和中文理解 + SQL 代码分析的需求，推荐如下：

**7.2.1 最佳方案：Qwen2.5-Coder 32B（Q4\_K\_M）**

  -------------- --------------------------------------------------
  **项目**       **说明**
  模型           qwen2.5-coder:32b-q4\_K\_M
  内存占用       \~20GB（Q4 量化后）
  推理速度       预计 8-15 tokens/s（Vulkan 后端，全层 GPU 卸载）
  中文能力       极强（Qwen 系列是开源最强中文模型）
  SQL 分析能力   极强（Coder 变体专为代码优化）
  上下文窗口     支持 16K-32K tokens
  -------------- --------------------------------------------------

这是您的最优选择：一个模型同时覆盖中文理解和 SQL 分析两个需求，64GB 内存完全够用。

**7.2.2 备选方案：双模型组合**

  ---------- ---------------------------- -------------- --------------------
  **角色**   **模型**                     **内存占用**   **用途**
  主力审查   qwen2.5-coder:32b-q4\_K\_M   \~20GB         SQL 审查、裁决
  辅助任务   qwen2.5:14b-q4\_K\_M         \~9GB          中文理解、报告生成
  ---------- ---------------------------- -------------- --------------------

两个模型同时加载约 29GB，64GB 内存游刃有余。

**7.3 推理后端选择**

Radeon 8060S 支持两种推理后端，各有优劣：

  ---------------- -------------------------------------- -------------------------------- ------------------------
  **后端**         **优点**                               **缺点**                         **推荐场景**
  Vulkan（推荐）   稳定性好、优先用核显显存、不影响系统   大模型速度稍慢                   日常使用、长时间运行
  ROCm             大模型吞吐更高（\~8.5 t/s for 27B）    长时间运行内存占用高、可能卡顿   Linux + 专用推理服务器
  ---------------- -------------------------------------- -------------------------------- ------------------------

建议使用 Vulkan 后端作为首选，稳定性更好，适合日常开发使用。

**7.4 Ollama 部署配置**

**环境变量配置：**

> OLLAMA\_MAX\_LOADED\_MODELS=2 \# 同时加载的模型数量
>
> OLLAMA\_NUM\_PARALLEL=2 \# 每个模型的并行请求数
>
> OLLAMA\_KEEP\_ALIVE=10m \# 模型保持加载时间
>
> OLLAMA\_CONTEXT\_LENGTH=16000 \# 上下文窗口大小

**模型拉取命令：**

> ollama pull qwen2.5-coder:32b-q4\_K\_M

**验证模型运行状态：**

> ollama ps \# 查看当前加载的模型及内存占用

**八、技术栈与部署**

**8.1 技术栈总览**

  ------------ ------------------------------------- ----------------------------------
  **层级**     **技术组件**                          **版本要求**
  前端         纯 HTML5 + CSS3 + JavaScript (ES6+)   无框架依赖
  UI 美化      Highlight.js（SQL 高亮）              可选：SimpleMDE（Markdown 编辑）
  后端         Flask                                 \>=3.0
  Agent 编排   CrewAI                                \>=0.80
  LLM 运行时   Ollama                                最新版
  主力模型     Qwen2.5-Coder 32B (Q4\_K\_M)          中文 + SQL 双强
  Excel 解析   pandas + openpyxl                     \>=2.0
  SQL 解析     sqlglot                               \>=25.0
  异步任务     threading + SSE                       内置
  数据存储     SQLite（历史记录）                    可选
  ------------ ------------------------------------- ----------------------------------

**8.2 硬件配置**

  ------------ ------------------------ ----------------------------------------
  **配置项**   **配置内容**             **说明**
  CPU          AMD Ryzen AI MAX 392     Zen 5 架构，16 核心
  内存         64GB LPDDR5X             统一内存架构，可全部作为 VRAM
  核显         Radeon 8060S             RDNA 3.5 架构，40 CU，支持 Vulkan/ROCm
  推理速度     8-15 tokens/s (32B Q4)   全层 GPU 卸载，Vulkan 后端
  ------------ ------------------------ ----------------------------------------

**九、关键风险与应对策略**

  --------------------------------- ---------- ---------------------------------------------------------------
  **风险项**                        **等级**   **应对策略**
  IT-Mapping 格式不统一             高         设计灵活的 Excel 解析器，支持自定义表头映射；提供模板配置功能
  复杂 SQL 存储过程超出上下文窗口   高         将大 SQL 拆分为子查询单元分别审查；增大 num\_ctx
  多 Agent 并行审查资源竞争         中         合理配置 OLLAMA\_NUM\_PARALLEL；必要时串行化部分任务
  审查结果误报（幻觉）              中         低温度设置（temperature=0.1）；提示词要求"只报告确定的错误"
  前端大文件上传性能                低         限制文件大小（如 50MB）；显示上传进度条
  ROCm 后端长时间运行内存占用高     中         优先使用 Vulkan 后端；定期重启 Ollama 服务
  --------------------------------- ---------- ---------------------------------------------------------------

--- 文档结束 ---
