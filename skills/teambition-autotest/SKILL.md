---
name: teambition-autotest
description: "基于 Playwright 的 Teambition Web 应用自动化功能测试技能，测试完成后将结果自动回写至 Teambition 项目任务。适用场景：对 Teambition 进行端到端功能链路测试、验证新功能操作流程是否走通、生成带截图的测试报告、测试完成后自动在 Teambition 项目中创建通过或缺陷任务。"
---

# Teambition 自动化测试技能

使用浏览器自动化驱动 Teambition 完成功能链路测试，并将测试结果回写至指定 Teambition 项目。

## 工作流总览

1. **收集输入** — 获取应用地址、登录方式、测试目标、操作链路和结果回写配置
2. **处理登录** — 暂停等待用户扫码或输入手机验证码，完成后继续执行
3. **执行测试链路** — 逐步驱动浏览器操作，每个关键步骤截图留证
4. **评估结果** — 对比每个验证点的实际结果与预期结果
5. **结果回写 Teambition** — 全部通过则创建「测试通过」任务，有失败则为每个失败点单独创建「缺陷」任务
6. **生成报告** — 输出嵌入截图的 Markdown 测试报告并转换为 PDF

---

## 第一步：收集必要输入

执行前收集以下信息，仅询问缺失的部分。

| 参数 | 说明 | 示例 |
|---|---|---|
| `app_url` | 目标 Teambition 项目 URL | `https://www.teambition.com/project/<id>/tasks/view/<id>` |
| `login_method` | 登录方式 | `qrcode`（扫码）/ `phone_otp`（手机验证码）/ `session_file`（复用会话） |
| `feature_name` | 被测功能名称 | `创建任务` |
| `feature_desc` | 功能一句话描述 | `在指定项目中创建一条新任务` |
| `steps` | 有序操作步骤列表 | 见下方格式说明 |
| `checkpoints` | 关键步骤的验证断言 | 见下方格式说明 |
| `tb_project` | 接收测试结果任务的 Teambition 项目名 | `claw-test-bugs` |
| `priority_rules` | 失败严重程度与优先级的映射规则 | 见下方默认规则 |

**操作步骤格式**（自然语言，有序）：
```
1. 点击看板右上角「创建任务」按钮
2. 填写标题、截止时间、备注、优先级
3. 点击「完成」
```

**验证点格式**：
```
- 步骤1完成后：弹出创建任务弹窗
- 步骤3完成后：左下角出现 Toast 成功提示，看板出现新任务卡片
```

**默认优先级规则**（用户未指定时使用）：
- 主链路阻断（如创建失败）→ `非常紧急`
- 功能异常但可绕过 → `紧急`
- 仅 UI / 展示问题 → `普通`

---

## 第二步：处理登录

Teambition 不支持账号密码登录，固定使用**用户接管**方案：

1. 导航至 `app_url`
2. 若跳转至登录页，暂停并提示用户接管浏览器完成扫码或手机验证码登录
3. 用户回复「已登录」后，继续执行后续自动化步骤

**会话复用（可选）**：首次登录后，用 Playwright 的 `storageState` 将浏览器状态保存为文件，后续运行直接加载，跳过登录步骤（有效期至 Session 过期）。

```python
# 首次登录后保存会话
await context.storage_state(path="/home/ubuntu/tb-test/auth_state.json")

# 后续运行加载会话
context = await browser.new_context(storage_state="/home/ubuntu/tb-test/auth_state.json")
```

---

## 第三步：执行测试链路

逐步驱动浏览器，每个步骤注意：

- 优先使用语义选择器（文本、role、aria-label），避免使用哈希 CSS 类名
- 选择器不明确时，用 `page.evaluate()` 检查 DOM 结构，获取元素精确位置
- 每个验证点步骤完成后截图：`await page.screenshot(path=f"screenshots/stepXX_<描述>.png")`
- 截图保存至 `/home/ubuntu/tb-test/screenshots/`

**Teambition 关键 UI 操作模式（来自真实测试经验）**：

| 操作 | 推荐方案 |
|---|---|
| 点击「创建任务」按钮 | `page.get_by_role("button", name="创建任务")` 或 `page.locator('button:has-text("创建任务")')` |
| 填写任务标题 | JS 注入：`document.querySelector('input[placeholder*="标题"]').value = ...` + 触发 React 合成事件 |
| 设置截止时间 | 点击「设置截止时间」→ 日历选择器弹出 → 点击目标日期格 → 点击「确定」 |
| 填写富文本备注 | 点击备注区域 → `page.keyboard.type(text)` 或 JS 注入 `contenteditable` |
| 设置优先级 | 点击当前优先级标签（如「较低」）→ 下拉菜单弹出 → JS `.click()` 目标 `<li>` 选项 |
| 点击「完成」提交 | `document.querySelector('button.progress-button__LsFk__detail').click()`（按钮超出视口时用 JS 直接触发） |
| 验证 Toast 提示 | 等待左下角出现包含「成功创建任务」文本的元素 |
| 验证看板卡片 | 检查看板列文本是否包含新任务标题 |

**弹窗溢出处理**：Teambition 新建任务弹窗内容较长时，「完成」按钮可能超出视口。先用 `element.scrollIntoView()` 滚动到按钮位置，或直接通过 JS 触发点击。

---

## 第四步：评估结果

每个验证点记录以下内容：

```
验证点：<名称>
预期结果：<应该发生什么>
实际结果：<实际发生了什么>
状态：通过 ✅ / 失败 ❌
截图路径：<文件路径>
```

根据第一步中的 `priority_rules` 判定失败的严重程度。

---

## 第五步：结果回写 Teambition

使用已登录的浏览器导航至目标项目，通过 UI 操作创建任务（无需 API Token）；若有可用 Token 也可调用 Teambition Open API。

### 全部通过 → 创建一条「测试通过」任务：

```
标题：[测试通过] <功能名称> — <日期>
备注：通过率：100%，执行时间：<datetime>，用例数：<n>
```

### 有失败 → 每个失败点单独创建一条「缺陷」任务：

```
标题：[缺陷] <功能名称> — <验证点名称>
备注：失败步骤：<step>
     预期结果：<expected>
     实际结果：<actual>
     复现路径：<steps_to_reproduce>
标签：auto-test
优先级：<根据 priority_rules 映射>
附件：失败现场截图
```

**通过 Teambition UI 创建任务**（无需 API Token）：
1. 导航至项目 URL
2. 点击「+ 创建任务」
3. 按第三步中的 UI 操作模式填写标题、备注、优先级
4. 点击「完成」

---

## 第六步：生成测试报告

使用 `/home/ubuntu/skills/teambition-autotest/templates/test_report_template.md` 作为起始模板。

将所有占位符替换为实际测试数据，用相对路径嵌入截图：

```markdown
![步骤描述](./screenshots/stepXX_描述.png)
```

保存报告并转换为 PDF：

```bash
manus-md-to-pdf /home/ubuntu/tb-test/teambition_test_report.md /home/ubuntu/tb-test/teambition_test_report.pdf
```

交付时同时附上 `.md`、`.pdf` 文件及关键步骤截图。

---

## 注意事项

- 截图目录：`/home/ubuntu/tb-test/screenshots/`（不存在时先执行 `mkdir -p` 创建）
- Teambition 使用 React，CSS 类名经过哈希处理 — 优先使用文本/role 选择器，避免依赖类名
- 新建任务弹窗为浮层，弹窗内部滚动时 DOM 坐标会偏移，注意重新定位
- 优先级下拉的 `<li>` 选项可能在屏幕外，必须用 JS `.click()` 触发，坐标点击不可靠
- Toast 提示在任务创建后约 2 秒才出现，断言前需用 `page.wait_for_selector()` 或短暂等待
