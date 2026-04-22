# SQL智能纠错系统优化 - 实现计划

## [x] 任务1: 扩展InsertBlock类，添加字段位置信息
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 修改InsertBlock类，添加字段位置信息字段
  - 在解析过程中记录每个字段的精确位置（行号和列号）
  - 实现字段位置的序列化和反序列化
- **Acceptance Criteria Addressed**: AC-1, AC-2
- **Test Requirements**:
  - `programmatic` TR-1.1: 解析包含多个字段的SQL文件，验证每个字段的位置信息正确
  - `programmatic` TR-1.2: 解析包含嵌套表达式的复杂SQL，验证位置信息正确
- **Notes**: 需要修改sql_group_parser.py文件，确保与现有解析逻辑兼容

## [x] 任务2: 实现FieldLocator类，优化字段定位算法
- **Priority**: P0
- **Depends On**: 任务1
- **Description**: 
  - 创建FieldLocator类，专门处理字段精确定位
  - 利用SQL解析结果进行精确搜索
  - 实现基于分组的搜索策略，缩小搜索范围
  - 支持上下文感知搜索，区分不同子句中的字段
  - 支持不同数据库方言的语法差异（如MySQL、PostgreSQL、Oracle等）
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-6
- **Test Requirements**:
  - `programmatic` TR-2.1: 测试不同类型SQL语句的字段定位准确率
  - `programmatic` TR-2.2: 测试不同格式SQL文件的兼容性
  - `programmatic` TR-2.3: 测试不同数据库方言的兼容性
- **Notes**: 需要考虑各种边缘情况，如字段别名、表别名等，以及不同数据库方言的语法差异

## [x] 任务3: 修改FieldCheckAgent，集成新的定位逻辑
- **Priority**: P1
- **Depends On**: 任务2
- **Description**: 
  - 更新FieldCheckAgent._locate_field_in_sql方法
  - 集成FieldLocator的定位逻辑
  - 在检查结果中包含精确的位置信息
  - 确保与现有检查逻辑的兼容性
- **Acceptance Criteria Addressed**: AC-1, AC-4
- **Test Requirements**:
  - `programmatic` TR-3.1: 验证检查结果中包含精确的位置信息
  - `human-judgment` TR-3.2: 检查位置信息的可读性和准确性
- **Notes**: 需要确保位置信息的格式统一和清晰

## [x] 任务4: 优化前端展示，支持精确位置标记
- **Priority**: P1
- **Depends On**: 任务3
- **Description**: 
  - 修改前端代码，支持显示精确的位置信息
  - 实现代码高亮和位置标记功能
  - 优化用户界面，显示行号、列号和代码片段
  - 确保前端展示的响应速度和用户体验
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - `human-judgment` TR-4.1: 验证前端能够正确显示精确的位置信息
  - `human-judgment` TR-4.2: 检查前端界面的用户体验和响应速度
- **Notes**: 需要修改static/js目录下的相关文件

## [x] 任务5: 实现按指定格式输出结果
- **Priority**: P1
- **Depends On**: 任务3
- **Description**: 
  - 分析"test输出示例.xlsx"的格式
  - 实现Excel输出功能，按照指定格式生成结果
  - 确保输出内容与示例格式完全匹配
  - 添加导出功能到前端界面
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `programmatic` TR-5.1: 验证输出Excel文件格式与示例一致
  - `programmatic` TR-5.2: 验证输出内容的完整性和准确性
- **Notes**: 需要使用openpyxl库生成Excel文件

## [x] 任务6: 性能优化和测试
- **Priority**: P2
- **Depends On**: 任务2
- **Description**: 
  - 优化SQL解析和字段定位的性能
  - 实现解析结果缓存机制，避免重复解析
  - 测试大SQL文件的解析性能
  - 编写全面的测试用例，覆盖各种场景
- **Acceptance Criteria Addressed**: AC-3, AC-6
- **Test Requirements**:
  - `programmatic` TR-6.1: 测试1000行以上SQL文件的解析时间
  - `programmatic` TR-6.2: 测试不同格式SQL文件的解析成功率
- **Notes**: 需要关注性能优化，确保大文件解析的效率

## [x] 任务7: 集成和验证
- **Priority**: P1
- **Depends On**: 任务3, 任务4, 任务5, 任务6
- **Description**: 
  - 将所有组件集成到完整的系统中
  - 进行端到端测试，验证整个流程
  - 修复集成过程中发现的问题
  - 确保系统的稳定性和可靠性
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6
- **Test Requirements**:
  - `programmatic` TR-7.1: 端到端测试，验证完整流程的正确性
  - `human-judgment` TR-7.2: 验证系统的整体用户体验
- **Notes**: 需要确保与现有系统的无缝集成