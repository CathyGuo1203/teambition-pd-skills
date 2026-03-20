---
name: teambition-resource-analyzer
description: 自动通过 Teambition MCP 工具拉取项目数据，分析团队成员的工时投入、负载情况及可用性。当项目经理或部门负责人需要了解“下周谁有空”、“团队工作量是否饱和”、“各项目/部门/优先级的人力投入分布”，以进行资源调配、风险预警和排期优化时，使用此 Skill。
---

# Teambition 项目人力资源分析技能

本技能通过调用 `dingtalk-teambition` MCP 工具获取任务和工时数据，并自动生成包含可视化图表和可行动建议的 Markdown 报告。

## 核心工作流

执行本技能时，请严格按照以下步骤进行：

### 1. 确认分析范围与参数
与用户确认或从上下文中提取以下参数：
- **时间范围**：如“下周”、“本周”、“2026-03-23 到 2026-03-27”。
- **分析范围**：特定的项目名称/ID，或特定的成员/部门。
- **饱和度基准**：默认每周 40 小时，超载阈值 110%。如用户有特殊要求，请记录。

### 2. 发现工时字段 ID
Teambition 的“计划工时”和“实际工时”是自定义字段，必须先获取其 ID：
1. 找到目标项目的一个任务 ID（可通过 `query_tasks.py` 随便查一个）。
2. 执行 `uv run scripts/query_task_detail.py <taskId> --detail-level detailed` 获取 `sfcId`（任务类型ID）和 `projectId`。
3. 执行 `uv run scripts/get_custom_fields.py <projectId> --sfc-id <sfcId>`。
4. 在返回结果中，找到名称为“计划工时”和“实际工时”的字段，记录它们的 `_id`。

### 3. 获取企业优先级配置
执行 `uv run scripts/get_priority_list.py <organizationId>` 获取企业真实的优先级名称映射（organizationId 可通过 `query_project_detail.py <projectId> --extra-fields organizationId` 获取）。

### 4. 拉取任务数据
使用 `dingtalk-teambition` 的 `query_tasks.py` 拉取指定范围内的任务：
```bash
# 示例：拉取项目 xxx 下周截止的任务
uv run scripts/query_tasks.py --tql "projectId = 'xxx' AND dueDate >= startOf(w, 1w) AND dueDate <= endOf(w, 1w)" --page-size 100
```
提取返回的所有任务 ID，以逗号分隔。

### 5. 获取任务详情与成员信息
1. 使用 `query_task_detail.py <id1,id2,...> --detail-level detailed` 批量获取任务详情。
2. 收集所有出现的 `executorId`，使用 `query_members.py --user-ids "<id1,id2,...>"` 批量转换为成员姓名和部门信息。

### 6. 整理数据并执行分析脚本
将获取到的数据整理为 `analyze_workload.py` 所需的 JSON 格式（见脚本注释），保存为 `/tmp/tasks.json`。

然后执行分析脚本：
```bash
python /home/ubuntu/skills/teambition-resource-analyzer/scripts/analyze_workload.py \
  --input /tmp/tasks.json \
  --output-dir /tmp/tb_resource_charts \
  --weekly-hours 40 \
  --overload-threshold 110 \
  --period-label "下周"
```

### 7. 生成并交付报告
1. 脚本会在终端输出 Markdown 格式的分析结果，并生成 PNG 图表。
2. 读取 `templates/report_template.md`。
3. 将脚本输出的内容填入模板对应的占位符中。
4. 结合数据洞察，在“行动建议”部分补充 2-3 条具体的排期或资源调整建议。
5. 将最终的 Markdown 报告保存为文件（如 `resource_report.md`），并使用 `message` 工具将其作为附件发送给用户。

## 注意事项
- **数据隐私**：仅拉取用户有权限访问的项目数据。
- **缺失值处理**：如果任务未填写计划工时，分析脚本会默认按 0 处理，这可能导致负载率偏低。在报告中应提示用户规范填写工时。
- **图表路径**：脚本输出的图表路径为绝对路径，在最终交付的 Markdown 报告中，请确保图表能够正确渲染或作为附件一并提供。
