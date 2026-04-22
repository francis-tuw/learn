# SQL智能纠错系统优化 - 产品需求文档

## Overview
- **Summary**: 优化SQL智能纠错系统，实现IT-Mapping与SQL文件的100%精准位置匹配，提高纠错准确性和用户体验，并根据指定格式输出结果
- **Purpose**: 解决当前系统中SQL字段位置匹配不准确的问题，确保系统能够精确定位到SQL文件中的具体字符位置，并按要求格式输出结果
- **Target Users**: 数据仓库开发人员、SQL审核人员、数据质量管理人员

## Goals
- 实现IT-Mapping字段与SQL文件中对应代码的100%精准匹配
- 提供字符级别的精确位置信息，包括行号和列号
- 提高SQL解析的准确性和性能
- 优化前端展示，显示精确的错误位置
- 按照"test输出示例.xlsx"格式输出结果
- 保持系统的可扩展性和稳定性

## Non-Goals (Out of Scope)
- 重新设计整个系统架构
- 改变现有的AI检查逻辑
- 支持非SQL语言的代码检查
- 开发新的前端框架

## Background & Context
- 当前系统使用简单的字符串搜索定位SQL字段位置，精度有限
- 系统已有SQL解析器，但未充分利用其结构信息
- 缺少字符级的位置信息记录和传递
- 用户需要精确的错误位置信息来快速定位和修复问题
- 用户要求按照特定Excel格式输出结果

## Functional Requirements
- **FR-1**: 扩展SQLGroupParser，添加字段位置信息记录
- **FR-2**: 实现FieldLocator类，优化字段定位算法
- **FR-3**: 建立字段名到SQL位置的映射表
- **FR-4**: 在检查结果中包含精确的位置信息
- **FR-5**: 优化前端展示，支持精确位置标记
- **FR-6**: 实现按"test输出示例.xlsx"格式输出结果

## Non-Functional Requirements
- **NFR-1**: 解析性能：大SQL文件（>1000行）的解析时间不超过5秒
- **NFR-2**: 定位精度：字段位置定位准确率达到100%
- **NFR-3**: 兼容性：支持多种SQL方言（如MySQL、PostgreSQL、Oracle等）和格式
- **NFR-4**: 可维护性：代码结构清晰，易于扩展
- **NFR-5**: 稳定性：处理各种边缘情况和异常输入

## Constraints
- **Technical**: 基于现有Python技术栈，不引入新的依赖
- **Business**: 保持与现有系统的兼容性
- **Dependencies**: 依赖现有的SQL解析器和检查逻辑

## Assumptions
- SQL文件遵循标准的SQL语法规范
- IT-Mapping文件格式与现有系统兼容
- 系统运行环境具备足够的计算资源

## Acceptance Criteria

### AC-1: 字段精确定位
- **Given**: 输入包含多个字段的SQL文件和对应的IT-Mapping文件
- **When**: 系统执行一致性检查
- **Then**: 系统能够准确定位每个字段在SQL文件中的精确位置（行号和列号）
- **Verification**: `programmatic`

### AC-2: 复杂SQL支持
- **Given**: 输入包含嵌套表达式、多表关联的复杂SQL文件
- **When**: 系统执行解析和定位
- **Then**: 系统能够正确解析并定位所有字段的位置
- **Verification**: `programmatic`

### AC-3: 性能要求
- **Given**: 输入1000行以上的大型SQL文件
- **When**: 系统执行解析和定位
- **Then**: 解析时间不超过5秒
- **Verification**: `programmatic`

### AC-4: 前端展示
- **Given**: 系统检测到字段不一致
- **When**: 前端展示检查结果
- **Then**: 前端显示精确的错误位置，包括行号、列号和代码片段
- **Verification**: `human-judgment`

### AC-5: 输出格式
- **Given**: 系统完成一致性检查
- **When**: 用户请求导出结果
- **Then**: 系统按照"test输出示例.xlsx"格式输出结果
- **Verification**: `programmatic`

### AC-6: 兼容性
- **Given**: 输入不同格式的SQL文件（不同缩进、注释风格）
- **When**: 系统执行解析和定位
- **Then**: 系统能够正确处理各种格式的SQL文件
- **Verification**: `programmatic`

## Open Questions
- [ ] 是否需要支持存储过程中的动态SQL语句定位？
- [ ] 如何处理SQL文件中的宏变量和动态生成的SQL？
- [ ] 是否需要考虑不同数据库方言的语法差异？