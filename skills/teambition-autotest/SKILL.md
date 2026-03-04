---
name: teambition-autotest
description: "Playwright-based automated functional testing for Teambition web application, with results written back to a Teambition project as tasks. Use when: running end-to-end feature chain tests on Teambition, verifying new feature operation flows, generating test reports with screenshots, or automatically creating bug/pass tasks in a Teambition project after testing."
---

# Teambition Automated Testing Skill

Automate functional chain testing on Teambition using browser automation, then write results back to a Teambition project as tasks.

## Workflow Overview

1. **Collect inputs** — gather app URL, login method, test target, operation chain, and result-writing config
2. **Handle login** — pause for user to scan QR code / enter phone OTP, then resume
3. **Execute test chain** — drive browser step-by-step, screenshot each key step
4. **Evaluate results** — compare actual vs expected for each checkpoint
5. **Write results to Teambition** — create a pass task or per-failure bug tasks
6. **Generate report** — produce a Markdown report with embedded screenshots

---

## Step 1: Required Inputs

Collect the following before starting. Ask the user only for what is missing.

| Input | Description | Example |
|---|---|---|
| `app_url` | Target Teambition project URL | `https://www.teambition.com/project/<id>/tasks/view/<id>` |
| `login_method` | How the app authenticates | `qrcode` / `phone_otp` / `session_file` |
| `feature_name` | Name of the feature under test | `创建任务` |
| `feature_desc` | One-sentence description | `在指定项目中创建一条新任务` |
| `steps` | Ordered list of user actions | See format below |
| `checkpoints` | What to assert after key steps | See format below |
| `tb_project` | Teambition project name for result tasks | `claw-test-bugs` |
| `priority_rules` | How to map failure severity to priority | See defaults below |

**Steps format** (natural language, ordered):
```
1. 点击看板右上角「创建任务」按钮
2. 填写标题、截止时间、备注、优先级
3. 点击「完成」
```

**Checkpoints format**:
```
- 步骤1完成后：弹出创建任务弹窗
- 步骤3完成后：左下角出现 Toast 成功提示，看板出现新任务卡片
```

**Default priority rules** (override if user specifies):
- Main flow blocked (e.g., creation fails) → `非常紧急`
- Feature broken but workaround exists → `紧急`
- UI/display issue only → `普通`

---

## Step 2: Handle Login

Teambition does not support username/password login. Always use the **user takeover** approach:

1. Navigate to `app_url`
2. If redirected to login page, pause and ask user to take over browser to complete QR code scan or phone OTP
3. After user replies "已登录" (or equivalent), resume automation

**Session reuse (optional):** After first login, save browser state with Playwright's `storageState` to a file (e.g., `/home/ubuntu/tb-test/auth_state.json`). On subsequent runs, load this file to skip login — valid until session expires.

```python
# Save session after login
await context.storage_state(path="/home/ubuntu/tb-test/auth_state.json")

# Load session on next run
context = await browser.new_context(storage_state="/home/ubuntu/tb-test/auth_state.json")
```

---

## Step 3: Execute Test Chain

Drive the browser step by step. For each step:

- Use `page.locator()` with semantic selectors (text, role, aria-label) before CSS/XPath
- When selectors are unclear, use `page.evaluate()` to inspect the DOM and find element positions
- Take a screenshot after each checkpoint step: `await page.screenshot(path=f"screenshots/stepXX_<desc>.png")`
- Save screenshots to `/home/ubuntu/tb-test/screenshots/`

**Key Teambition UI patterns learned from real usage:**

| Action | Approach |
|---|---|
| Click「创建任务」button | `page.get_by_role("button", name="创建任务")` or `page.locator('button:has-text("创建任务")')` |
| Fill task title | JS inject: `document.querySelector('input[placeholder*="标题"]').value = ...` + trigger React event |
| Set due date | Click「设置截止时间」→ calendar picker appears → click target date cell → click「确定」|
| Fill rich-text note | Click note area → `page.keyboard.type(text)` or JS `contenteditable` injection |
| Set priority | Click current priority badge (e.g.,「较低」) → dropdown appears → JS click target `<li>` item |
| Click「完成」| `document.querySelector('button.progress-button__LsFk__detail').click()` (JS fallback if button is off-screen) |
| Verify Toast | Check for element containing「成功创建任务」in bottom-left area |
| Verify board card | Check kanban column text includes new task title |

**Handling off-screen elements:** Teambition's create-task modal may push the「完成」button below the visible viewport. Use `element.scrollIntoView()` before clicking, or trigger via JS directly.

---

## Step 4: Evaluate Results

For each checkpoint, record:

```
Checkpoint: <name>
Expected:   <what should happen>
Actual:     <what actually happened>
Status:     PASS ✅ / FAIL ❌
Screenshot: <path>
```

Determine failure severity using `priority_rules` from Step 1.

---

## Step 5: Write Results to Teambition

Use the browser (already authenticated) to navigate to the target project and create tasks via the UI, or use Teambition Open API if a token is available.

### If all checkpoints pass → Create one "pass" task:

```
Title:   [测试通过] <feature_name> — <date>
Note:    通过率：100%，执行时间：<datetime>，用例数：<n>
```

### If any checkpoint fails → Create one bug task per failure:

```
Title:   [缺陷] <feature_name> — <checkpoint_name>
Note:    失败步骤：<step>
         预期结果：<expected>
         实际结果：<actual>
         复现路径：<steps_to_reproduce>
Tags:    auto-test
Priority: <derived from priority_rules>
Attachment: failure screenshot
```

**Creating tasks via Teambition UI** (no API token needed):
1. Navigate to project URL
2. Click「+ 创建任务」
3. Fill title, note, priority using the same browser automation patterns from Step 3
4. Click「完成」

---

## Step 6: Generate Report

Use the template at `/home/ubuntu/skills/teambition-autotest/templates/test_report_template.md` as a starting point.

Replace all placeholder values with actual test data. Embed screenshots using relative paths:

```markdown
![步骤描述](./screenshots/stepXX_desc.png)
```

Save report to `/home/ubuntu/tb-test/teambition_test_report.md` and convert to PDF:

```bash
manus-md-to-pdf /home/ubuntu/tb-test/teambition_test_report.md /home/ubuntu/tb-test/teambition_test_report.pdf
```

Attach both `.md` and `.pdf` plus key screenshots when delivering to user.

---

## Notes

- Screenshots directory: `/home/ubuntu/tb-test/screenshots/` (create if missing: `mkdir -p`)
- Teambition uses React with hashed CSS class names — prefer text/role selectors over class selectors
- The create-task modal is a floating overlay; DOM coordinates shift when the modal scrolls internally
- Priority badge click opens a dropdown `<ul>` — the `<li>` items may be off-screen; use JS `.click()` to select reliably
- Toast appears at bottom-left with ~2s delay after task creation; use `page.wait_for_selector()` or a short sleep before asserting
