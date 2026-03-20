#!/usr/bin/env python3
"""
analyze_workload.py — Teambition 人力资源负载分析脚本

输入：从 stdin 读取 JSON 格式的任务数据（由 SKILL.md 工作流调用 dingtalk-teambition 脚本后整理传入）
输出：
  - 终端打印 Markdown 格式的分析结果（供 SKILL.md 工作流嵌入报告）
  - 将图表保存为 PNG 文件（路径由 --output-dir 指定）

用法：
  python analyze_workload.py --input tasks.json --output-dir /tmp/charts [--weekly-hours 40] [--overload-threshold 110]

tasks.json 格式（由 SKILL.md 工作流从 dingtalk-teambition 脚本输出整理而来）：
[
  {
    "taskId": "xxx",
    "title": "任务标题",
    "executorName": "张三",
    "department": "研发部",       // 可选，无则填 "未知"
    "projectName": "项目A",
    "priority": 0,               // 0=紧急 1=高 2=中 3=低
    "priorityName": "紧急",      // 企业自定义优先级名称
    "isDone": false,
    "startDate": "2026-03-23",   // 可为 null
    "dueDate": "2026-03-27",     // 可为 null
    "estimatedHours": 8.0,       // 计划工时，可为 null（按 0 处理）
    "loggedHours": 6.0           // 实际工时，可为 null（按 0 处理）
  }
]
"""

import argparse
import json
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── 优先级配置 ────────────────────────────────────────────────────────────────
PRIORITY_ORDER = [0, 1, 2, 3]
PRIORITY_COLORS = {0: "#e74c3c", 1: "#e67e22", 2: "#3498db", 3: "#95a5a6"}
DEFAULT_PRIORITY_NAMES = {0: "紧急", 1: "高", 2: "中", 3: "低"}

# ── 负载状态 ──────────────────────────────────────────────────────────────────
def load_status(rate, overload_threshold):
    if rate > overload_threshold / 100:
        return "🔴 超载"
    elif rate >= 0.9:
        return "🟢 饱和"
    else:
        return "🔵 可用"


def parse_args():
    parser = argparse.ArgumentParser(description="Teambition 人力资源负载分析")
    parser.add_argument("--input", required=True, help="tasks.json 文件路径")
    parser.add_argument("--output-dir", default="/tmp/tb_resource_charts", help="图表输出目录")
    parser.add_argument("--weekly-hours", type=float, default=40.0, help="每周基准工时（默认 40）")
    parser.add_argument("--overload-threshold", type=float, default=110.0, help="超载阈值百分比（默认 110）")
    parser.add_argument("--period-label", default="本周", help="分析周期描述，如下周、本月")
    return parser.parse_args()


def load_tasks(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_priority_names(tasks):
    """从数据中收集企业自定义优先级名称，回退到默认值"""
    names = dict(DEFAULT_PRIORITY_NAMES)
    for t in tasks:
        p = t.get("priority")
        pn = t.get("priorityName")
        if p is not None and pn:
            names[p] = pn
    return names


# ── 1. 个人负载计算 ───────────────────────────────────────────────────────────
def calc_individual_workload(tasks, weekly_hours, overload_threshold):
    member_data = defaultdict(lambda: {
        "department": "未知",
        "projects": set(),
        "estimated": 0.0,
        "logged": 0.0,
    })
    for t in tasks:
        name = t.get("executorName") or "未分配"
        member_data[name]["department"] = t.get("department") or "未知"
        member_data[name]["projects"].add(t.get("projectName") or "未知")
        member_data[name]["estimated"] += float(t.get("estimatedHours") or 0)
        member_data[name]["logged"] += float(t.get("loggedHours") or 0)

    rows = []
    for name, d in sorted(member_data.items()):
        rate = d["estimated"] / weekly_hours if weekly_hours > 0 else 0
        rows.append({
            "name": name,
            "department": d["department"],
            "estimated": round(d["estimated"], 1),
            "logged": round(d["logged"], 1),
            "baseline": weekly_hours,
            "rate": round(rate * 100, 1),
            "status": load_status(rate, overload_threshold),
            "projects": "、".join(sorted(d["projects"])),
        })
    return rows


# ── 2. 项目维度汇总 ───────────────────────────────────────────────────────────
def calc_project_allocation(tasks):
    proj = defaultdict(lambda: {"estimated": 0.0, "members": set()})
    for t in tasks:
        pn = t.get("projectName") or "未知"
        proj[pn]["estimated"] += float(t.get("estimatedHours") or 0)
        proj[pn]["members"].add(t.get("executorName") or "未分配")
    total = sum(d["estimated"] for d in proj.values()) or 1
    rows = []
    for pn, d in sorted(proj.items(), key=lambda x: -x[1]["estimated"]):
        rows.append({
            "project": pn,
            "estimated": round(d["estimated"], 1),
            "ratio": round(d["estimated"] / total * 100, 1),
            "member_count": len(d["members"]),
            "members": "、".join(sorted(d["members"])),
        })
    return rows


# ── 3. 部门维度汇总 ───────────────────────────────────────────────────────────
def calc_department_allocation(tasks):
    dept = defaultdict(lambda: {"estimated": 0.0, "projects": set()})
    for t in tasks:
        dn = t.get("department") or "未知"
        dept[dn]["estimated"] += float(t.get("estimatedHours") or 0)
        dept[dn]["projects"].add(t.get("projectName") or "未知")
    total = sum(d["estimated"] for d in dept.values()) or 1
    rows = []
    for dn, d in sorted(dept.items(), key=lambda x: -x[1]["estimated"]):
        rows.append({
            "department": dn,
            "estimated": round(d["estimated"], 1),
            "ratio": round(d["estimated"] / total * 100, 1),
            "project_count": len(d["projects"]),
        })
    return rows


# ── 4. 优先级维度汇总 ─────────────────────────────────────────────────────────
def calc_priority_allocation(tasks, priority_names):
    prio = defaultdict(lambda: {"estimated": 0.0, "members": set(), "name": ""})
    for t in tasks:
        p = t.get("priority")
        if p is None:
            p = 2  # 默认中优先级
        prio[p]["estimated"] += float(t.get("estimatedHours") or 0)
        prio[p]["members"].add(t.get("executorName") or "未分配")
        prio[p]["name"] = priority_names.get(p, str(p))
    total = sum(d["estimated"] for d in prio.values()) or 1
    rows = []
    for p in PRIORITY_ORDER:
        if p in prio:
            d = prio[p]
            rows.append({
                "priority": p,
                "priority_name": d["name"],
                "estimated": round(d["estimated"], 1),
                "ratio": round(d["estimated"] / total * 100, 1),
                "member_count": len(d["members"]),
                "members": "、".join(sorted(d["members"])),
            })
    return rows


# ── 5. 个人优先级分布（用于堆叠图） ──────────────────────────────────────────
def calc_member_priority_distribution(tasks, priority_names):
    data = defaultdict(lambda: defaultdict(float))
    for t in tasks:
        name = t.get("executorName") or "未分配"
        p = t.get("priority") if t.get("priority") is not None else 2
        data[name][p] += float(t.get("estimatedHours") or 0)
    return data


# ── 图表生成 ──────────────────────────────────────────────────────────────────
def set_chinese_font():
    """尝试设置中文字体，失败则使用默认字体"""
    try:
        from matplotlib import font_manager
        # 常见中文字体路径
        candidates = [
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/System/Library/Fonts/PingFang.ttc",
        ]
        for path in candidates:
            if os.path.exists(path):
                font_manager.fontManager.addfont(path)
                prop = font_manager.FontProperties(fname=path)
                plt.rcParams["font.family"] = prop.get_name()
                return
        # 回退：使用 matplotlib 默认，中文可能显示为方块，但不影响数据正确性
        plt.rcParams["font.family"] = "DejaVu Sans"
    except Exception:
        pass


def chart_workload(rows, weekly_hours, output_dir, period_label):
    """团队负载柱状图"""
    set_chinese_font()
    names = [r["name"] for r in rows]
    estimated = [r["estimated"] for r in rows]
    colors = []
    for r in rows:
        if r["rate"] > 110:
            colors.append("#e74c3c")
        elif r["rate"] >= 90:
            colors.append("#2ecc71")
        else:
            colors.append("#3498db")

    fig, ax = plt.subplots(figsize=(max(8, len(names) * 0.9), 5))
    x = np.arange(len(names))
    bars = ax.bar(x, estimated, color=colors, width=0.6, label="计划工时")
    ax.axhline(y=weekly_hours, color="#e67e22", linestyle="--", linewidth=1.5, label=f"基准工时 ({weekly_hours}h)")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("工时 (h)")
    ax.set_title(f"{period_label} 团队成员负载分布")
    ax.legend()
    # 标注数值
    for bar, r in zip(bars, rows):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{r['rate']}%", ha="center", va="bottom", fontsize=8)
    plt.tight_layout()
    path = os.path.join(output_dir, "chart_workload.png")
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def chart_project_pie(proj_rows, output_dir, period_label):
    """项目工时占比饼图"""
    set_chinese_font()
    labels = [r["project"] for r in proj_rows]
    sizes = [r["estimated"] for r in proj_rows]
    fig, ax = plt.subplots(figsize=(7, 5))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct="%1.1f%%", startangle=140,
        pctdistance=0.8, textprops={"fontsize": 9}
    )
    ax.set_title(f"{period_label} 人力投入 — 按项目")
    plt.tight_layout()
    path = os.path.join(output_dir, "chart_project_pie.png")
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def chart_priority_pie(prio_rows, output_dir, period_label):
    """优先级工时占比饼图"""
    set_chinese_font()
    labels = [r["priority_name"] for r in prio_rows]
    sizes = [r["estimated"] for r in prio_rows]
    colors = [PRIORITY_COLORS.get(r["priority"], "#bdc3c7") for r in prio_rows]
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=140,
           colors=colors, pctdistance=0.8, textprops={"fontsize": 9})
    ax.set_title(f"{period_label} 人力投入 — 按优先级")
    plt.tight_layout()
    path = os.path.join(output_dir, "chart_priority_pie.png")
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def chart_member_priority_stacked(member_prio_data, priority_names, output_dir, period_label):
    """成员优先级工时堆叠柱状图"""
    set_chinese_font()
    members = sorted(member_prio_data.keys())
    x = np.arange(len(members))
    bottoms = np.zeros(len(members))
    fig, ax = plt.subplots(figsize=(max(8, len(members) * 0.9), 5))
    patches = []
    for p in PRIORITY_ORDER:
        values = np.array([member_prio_data[m].get(p, 0.0) for m in members])
        color = PRIORITY_COLORS.get(p, "#bdc3c7")
        ax.bar(x, values, bottom=bottoms, color=color, width=0.6, label=priority_names.get(p, str(p)))
        bottoms += values
        patches.append(mpatches.Patch(color=color, label=priority_names.get(p, str(p))))
    ax.set_xticks(x)
    ax.set_xticklabels(members, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("工时 (h)")
    ax.set_title(f"{period_label} 成员工时 — 按优先级分布")
    ax.legend(handles=patches, loc="upper right", fontsize=8)
    plt.tight_layout()
    path = os.path.join(output_dir, "chart_member_priority_stacked.png")
    plt.savefig(path, dpi=150)
    plt.close()
    return path


# ── Markdown 输出 ─────────────────────────────────────────────────────────────
def md_workload_table(rows):
    lines = [
        "| 成员姓名 | 所属部门 | 计划工时 | 基准工时 | 负载率 | 状态 | 主要参与项目 |",
        "| :--- | :--- | ---: | ---: | ---: | :--- | :--- |",
    ]
    for r in rows:
        lines.append(
            f"| {r['name']} | {r['department']} | {r['estimated']}h | {r['baseline']}h "
            f"| {r['rate']}% | {r['status']} | {r['projects']} |"
        )
    return "\n".join(lines)


def md_project_table(rows):
    lines = [
        "| 项目名称 | 投入总工时 | 占比 | 投入人数 | 核心成员 |",
        "| :--- | ---: | ---: | ---: | :--- |",
    ]
    for r in rows:
        lines.append(
            f"| {r['project']} | {r['estimated']}h | {r['ratio']}% | {r['member_count']}人 | {r['members']} |"
        )
    return "\n".join(lines)


def md_department_table(rows):
    lines = [
        "| 部门名称 | 投入总工时 | 占比 | 参与项目数 |",
        "| :--- | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append(
            f"| {r['department']} | {r['estimated']}h | {r['ratio']}% | {r['project_count']} |"
        )
    return "\n".join(lines)


def md_priority_table(rows):
    lines = [
        "| 优先级 | 投入总工时 | 占比 | 涉及人数 | 核心成员 |",
        "| :--- | ---: | ---: | ---: | :--- |",
    ]
    for r in rows:
        lines.append(
            f"| {r['priority_name']} | {r['estimated']}h | {r['ratio']}% | {r['member_count']}人 | {r['members']} |"
        )
    return "\n".join(lines)


def generate_insights(workload_rows, proj_rows, prio_rows, weekly_hours, overload_threshold, period_label):
    insights = []
    overloaded = [r for r in workload_rows if r["rate"] > overload_threshold]
    available = [r for r in workload_rows if r["rate"] < 90]

    if overloaded:
        names = "、".join(r["name"] for r in overloaded)
        insights.append(
            f"**风险预警**：{names} 在{period_label}负载率超过 {overload_threshold:.0f}%，"
            f"存在延期或倦怠风险，建议立即介入调整任务分配。"
        )
    if available:
        total_free = sum(max(0, weekly_hours - r["estimated"]) for r in available)
        names = "、".join(r["name"] for r in available)
        insights.append(
            f"**可用资源**：{names} 在{period_label}负载率低于 90%，"
            f"合计约有 {total_free:.1f}h 可用，可承接新任务或协助高负载成员。"
        )
    if proj_rows:
        top = proj_rows[0]
        insights.append(
            f"**投入重心**：{period_label}团队核心精力集中在「{top['project']}」"
            f"（占比 {top['ratio']}%，投入 {top['estimated']}h）。"
        )
    if prio_rows:
        high_prio = [r for r in prio_rows if r["priority"] in (0, 1)]
        high_ratio = sum(r["ratio"] for r in high_prio)
        low_prio = [r for r in prio_rows if r["priority"] == 3]
        low_ratio = sum(r["ratio"] for r in low_prio)
        if high_ratio >= 50:
            insights.append(
                f"**优先级健康度**：{period_label}团队 {high_ratio:.1f}% 的工时投入在紧急/高优先级任务上，"
                f"资源分配聚焦，符合预期。"
            )
        elif low_ratio > 30:
            insights.append(
                f"**优先级健康度**：{period_label}有 {low_ratio:.1f}% 的工时消耗在低优先级任务上，"
                f"建议重新评估任务优先级排序，确保核心目标资源充足。"
            )

    return insights


def main():
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    tasks = load_tasks(args.input)
    if not tasks:
        print("## ⚠️ 未找到任何任务数据，请检查查询条件或时间范围。")
        sys.exit(0)

    priority_names = build_priority_names(tasks)

    # 计算各维度数据
    workload_rows = calc_individual_workload(tasks, args.weekly_hours, args.overload_threshold)
    proj_rows = calc_project_allocation(tasks)
    dept_rows = calc_department_allocation(tasks)
    prio_rows = calc_priority_allocation(tasks, priority_names)
    member_prio_data = calc_member_priority_distribution(tasks, priority_names)

    # 生成图表
    chart_wl = chart_workload(workload_rows, args.weekly_hours, args.output_dir, args.period_label)
    chart_pp = chart_project_pie(proj_rows, args.output_dir, args.period_label)
    chart_prp = chart_priority_pie(prio_rows, args.output_dir, args.period_label)
    chart_mps = chart_member_priority_stacked(member_prio_data, priority_names, args.output_dir, args.period_label)

    # 生成洞察
    insights = generate_insights(workload_rows, proj_rows, prio_rows,
                                  args.weekly_hours, args.overload_threshold, args.period_label)

    # 统计负载状态分布
    overloaded_count = sum(1 for r in workload_rows if "超载" in r["status"])
    full_count = sum(1 for r in workload_rows if "饱和" in r["status"])
    avail_count = sum(1 for r in workload_rows if "可用" in r["status"])

    # 输出 Markdown
    print("## 💡 核心洞察与建议 (Executive Summary)")
    for ins in insights:
        print(f"- {ins}")
    print()

    print("## 1. 团队整体负载情况 (Team Workload)")
    print(f"\n![团队负载分布]({chart_wl})\n")
    print(f"**负载状态分布：** 🔴 超载 {overloaded_count} 人 ｜ 🟢 饱和 {full_count} 人 ｜ 🔵 可用 {avail_count} 人\n")
    print(md_workload_table(workload_rows))
    print()

    print("## 2. 人力投入方向分析 (Resource Allocation)")
    print("\n### 2.1 按项目维度")
    print(f"\n![项目工时占比]({chart_pp})\n")
    print(md_project_table(proj_rows))
    print()

    print("### 2.2 按部门维度")
    print(md_department_table(dept_rows))
    print()

    print("### 2.3 按任务优先级维度")
    print(f"\n![优先级工时占比]({chart_prp})\n")
    print(f"\n![成员优先级分布]({chart_mps})\n")
    print(md_priority_table(prio_rows))
    print()

    # 输出图表路径供 SKILL.md 工作流引用
    print(f"<!-- CHART_PATHS: {chart_wl}|{chart_pp}|{chart_prp}|{chart_mps} -->")


if __name__ == "__main__":
    main()
