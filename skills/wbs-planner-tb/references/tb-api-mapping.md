# Teambition API 映射与 ID 转换规则

在执行 `wbs-planner-tb` 技能的"批量创建与反馈"阶段时，必须遵循以下 Teambition MCP 工具的调用规范和数据转换规则。

## 1. 核心字段映射

在调用 `create_task.py` 创建任务时，需将 WBS 拆解出的字段映射为 API 参数：

| WBS 字段 | API 参数 | 格式要求与说明 |
| --- | --- | --- |
| 任务标题 | `--title` | 必需。动宾结构，清晰明确。 |
| 所属项目 | `--project-id` | 必需。必须是真实的 `projectId`，通过 `query_projects.py` 获取。 |
| 执行者 | `--executor-id` | 必须是真实的 `userId`。需先通过 `query_members.py` 将姓名转换为 ID。 |
| 截止时间 | `--due-date` | 格式为 `YYYY-MM-DD`。脚本已内置东八区→UTC 转换，直接传本地时间即可。 |
| 优先级 | `--priority` | 数值型（0=紧急, 1=高, 2=中, 3=低）。**必须**先调用 `get_priority_list.py` 获取企业真实配置后映射。 |
| 备注/描述 | `--note` | 任务的详细描述或验收标准。 |
| 父任务 | `--parent-task-id` | 用于建立 Epic 和 Task 的层级关系。传入已创建的 Epic 任务的 ID。 |

## 2. ID 转换流程 (关键)

API 返回的各类 ID 字段均为原始字符串，展示给用户前必须转换为可读名称；反之，用户输入的名称在调用 API 前必须转换为 ID。

**执行者转换：**
1. 收集 Excel 预览中所有出现的执行者姓名。
2. 调用 `uv run scripts/query_members.py --keyword "<姓名>"` 搜索成员，获取对应的 `userId`。
3. 如果有多个同名成员，需结合上下文或部门信息进行确认。

**优先级转换：**
1. 获取项目的 `organizationId`：`uv run scripts/query_project_detail.py <projectId> --extra-fields organizationId`。
2. 获取企业优先级列表：`uv run scripts/get_priority_list.py <organizationId>`。
3. 将用户描述的优先级（如 P0、紧急）与返回的真实配置进行匹配，获取对应的数值（0-3）。

## 3. 批量创建逻辑

为了正确建立 WBS 的层级关系，批量创建必须按顺序进行：

1. **创建 Epic**：
   - 遍历 WBS 中的所有 Epic。
   - 调用 `create_task.py` 创建 Epic 任务。
   - 记录返回的 `taskId`，作为该 Epic 的标识。
2. **创建 Task**：
   - 遍历每个 Epic 下的 Task。
   - 调用 `create_task.py` 创建 Task，并将对应的 Epic `taskId` 作为 `--parent-task-id` 传入。
3. **依赖关系（可选）**：
   - 如果 Task 之间存在明确的前后置依赖，可通过更新任务链接或自定义字段来实现（视具体项目配置而定）。

## 4. 容错与异常处理

- **必填字段缺失**：如果经过 3 轮追问后，执行者或截止时间仍未明确，创建任务时不要传递这些参数，允许其为空。
- **创建失败**：如果某个任务创建失败（如权限不足、参数错误），记录错误信息，继续创建后续任务，并在最终反馈中汇总失败列表。
- **破坏性操作**：本技能主要涉及创建操作。如果用户要求重新拆解并覆盖原有任务，必须先向用户确认是否删除/归档旧任务，获得明确同意后再执行 `archive_task.py`。
