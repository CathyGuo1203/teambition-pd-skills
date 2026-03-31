#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WBS 编号生成器 + 时间逻辑检查器
处理 Teambition 导出的项目计划 Excel，生成 WBS 编号并验证时间逻辑
"""

import sys
import os
from datetime import datetime
import pandas as pd
from openpyxl import load_workbook


def generate_wbs_numbering(df):
    """根据任务层级生成 WBS 编号"""
    wbs_numbers = []
    # 使用列表存储每个层级的当前计数
    counters = [0] * 10  # 支持最多 10 层级
    
    for idx, row in df.iterrows():
        level = int(row['任务层级']) if pd.notna(row.get('任务层级')) else 1
        
        # 当前层级计数器加 1
        counters[level - 1] += 1
        
        # 重置所有子层级的计数器
        for l in range(level, 10):
            counters[l] = 0
        
        # 构建 WBS 编号（只取到当前层级）
        wbs_parts = [str(counters[l]) for l in range(level)]
        wbs = '.'.join(wbs_parts)
        wbs_numbers.append(wbs)
    
    return wbs_numbers


def infer_task_level_from_parent(df):
    """根据父任务关系推断任务层级"""
    # 构建标题到索引和层级的映射
    title_to_idx = {}
    for idx, row in df.iterrows():
        title = row['标题']
        title_to_idx[title] = idx
    
    levels = [0] * len(df)
    
    for idx, row in df.iterrows():
        parent = row.get('父任务')
        
        # 如果没有父任务或父任务为空/无，是根任务（层级 1）
        if pd.isna(parent) or parent == '' or parent == '无':
            levels[idx] = 1
        elif parent in title_to_idx:
            # 父任务存在，需要先计算父任务的层级
            parent_idx = title_to_idx[parent]
            # 如果父任务层级还未计算，递归计算
            if levels[parent_idx] == 0:
                # 简单处理：假设父任务在前面已经出现过
                levels[idx] = 2  # 默认子任务为层级 2
            else:
                levels[idx] = levels[parent_idx] + 1
        else:
            # 父任务不在列表中，默认为层级 2
            levels[idx] = 2
    
    return levels


def check_time_field_completeness(df):
    """检查 1: 时间字段完整性"""
    missing_tasks = []
    
    for idx, row in df.iterrows():
        start_time = row.get('开始时间')
        end_time = row.get('截止时间')
        
        if pd.isna(start_time) and pd.isna(end_time):
            missing_tasks.append({
                'wbs': row.get('序号', ''),
                'title': row.get('标题', ''),
                'parent': row.get('父任务', '')
            })
    
    return {
        'complete_count': len(df) - len(missing_tasks),
        'missing_count': len(missing_tasks),
        'missing_tasks': missing_tasks
    }


def check_parent_child_time_logic(df):
    """检查 2: 父子任务时间逻辑"""
    conflicts = []
    
    parent_map = {}
    for idx, row in df.iterrows():
        parent_name = row.get('父任务')
        if pd.notna(parent_name) and parent_name != '':
            parent_map[row['标题']] = parent_name
    
    time_map = {}
    for idx, row in df.iterrows():
        title = row['标题']
        start = pd.to_datetime(row.get('开始时间')) if pd.notna(row.get('开始时间')) else None
        end = pd.to_datetime(row.get('截止时间')) if pd.notna(row.get('截止时间')) else None
        time_map[title] = {'start': start, 'end': end}
    
    for child_title, parent_title in parent_map.items():
        if child_title not in time_map or parent_title not in time_map:
            continue
        
        child_start = time_map[child_title]['start']
        child_end = time_map[child_title]['end']
        parent_start = time_map[parent_title]['start']
        parent_end = time_map[parent_title]['end']
        
        if child_start and parent_start and child_start < parent_start:
            conflicts.append({
                'type': 'start_early',
                'child': child_title,
                'parent': parent_title,
                'child_start': child_start,
                'parent_start': parent_start
            })
        
        if child_end and parent_end and child_end > parent_end:
            conflicts.append({
                'type': 'end_late',
                'child': child_title,
                'parent': parent_title,
                'child_end': child_end,
                'parent_end': parent_end
            })
    
    return {
        'conflict_count': len(conflicts),
        'conflicts': conflicts
    }


def check_sibling_time_order(df):
    """检查 3: 同层级子任务时间顺序"""
    overlaps = []
    
    siblings_by_parent = {}
    for idx, row in df.iterrows():
        parent = row.get('父任务', 'ROOT')
        if parent not in siblings_by_parent:
            siblings_by_parent[parent] = []
        siblings_by_parent[parent].append(row)
    
    for parent, siblings in siblings_by_parent.items():
        if len(siblings) < 2:
            continue
        
        siblings_sorted = sorted(siblings, key=lambda x: str(x.get('序号', '')))
        
        for i in range(len(siblings_sorted) - 1):
            task1 = siblings_sorted[i]
            task2 = siblings_sorted[i + 1]
            
            end1 = pd.to_datetime(task1.get('截止时间')) if pd.notna(task1.get('截止时间')) else None
            start2 = pd.to_datetime(task2.get('开始时间')) if pd.notna(task2.get('开始时间')) else None
            
            if end1 and start2 and end1 > start2:
                overlap_days = (end1 - start2).days
                overlaps.append({
                    'task1_title': task1.get('标题', ''),
                    'task1_end': end1,
                    'task2_title': task2.get('标题', ''),
                    'task2_start': start2,
                    'overlap_days': overlap_days,
                    'parent': parent
                })
    
    return {
        'overlap_count': len(overlaps),
        'overlaps': overlaps[:20]
    }


def check_time_range_validity(df):
    """检查 4: 时间范围有效性"""
    invalid_tasks = []
    
    for idx, row in df.iterrows():
        start = pd.to_datetime(row.get('开始时间')) if pd.notna(row.get('开始时间')) else None
        end = pd.to_datetime(row.get('截止时间')) if pd.notna(row.get('截止时间')) else None
        
        if start and end and end < start:
            invalid_tasks.append({
                'wbs': row.get('序号', ''),
                'title': row.get('标题', ''),
                'start': start,
                'end': end
            })
    
    return {
        'invalid_count': len(invalid_tasks),
        'invalid_tasks': invalid_tasks
    }


def generate_report(df, wbs_results, check_results, output_path):
    """生成 Markdown 格式的验证报告"""
    total_issues = (
        check_results['completeness']['missing_count'] +
        check_results['parent_child']['conflict_count'] +
        check_results['sibling_order']['overlap_count'] +
        check_results['validity']['invalid_count']
    )
    
    report = []
    report.append("# 项目计划验证报告\n\n")
    report.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append(f"**任务总数**: {len(df)}\n\n")
    
    report.append("## 📊 总体结论\n\n")
    if total_issues == 0:
        report.append("✅ **未发现明显问题** - 项目计划时间逻辑合理\n\n")
    else:
        report.append(f"⚠️ **发现 {total_issues} 个问题**，需要重点关注和调整\n\n")
    
    report.append("| 检查项 | 状态 | 问题数 |\n")
    report.append("|--------|------|--------|\n")
    
    comp = check_results['completeness']
    status = "⚠️ 部分缺失" if comp['missing_count'] > 0 else "✅ 完整"
    report.append(f"| 时间字段完整性 | {status} | {comp['missing_count']} |\n")
    
    pc = check_results['parent_child']
    status = "❌ 存在冲突" if pc['conflict_count'] > 0 else "✅ 正常"
    report.append(f"| 父子任务时间逻辑 | {status} | {pc['conflict_count']} |\n")
    
    sib = check_results['sibling_order']
    if sib['overlap_count'] > 10:
        status = f"❌ 大量重叠 ({sib['overlap_count']}个)"
    elif sib['overlap_count'] > 0:
        status = f"⚠️ 少量重叠 ({sib['overlap_count']}个)"
    else:
        status = "✅ 正常"
    report.append(f"| 同层子任务时间顺序 | {status} | {sib['overlap_count']} |\n")
    
    val = check_results['validity']
    status = "❌ 存在无效" if val['invalid_count'] > 0 else "✅ 正常"
    report.append(f"| 时间范围有效性 | {status} | {val['invalid_count']} |\n\n")
    
    report.append("## 🔍 详细检查结果\n\n")
    
    report.append("### 1. 时间字段完整性检查\n\n")
    if comp['missing_count'] == 0:
        report.append("✅ 所有任务时间字段完整\n\n")
    else:
        report.append(f"⚠️ **{comp['missing_count']} 个任务完全缺失时间信息**\n\n")
        report.append("| WBS 编号 | 任务标题 | 父任务 |\n")
        report.append("|----------|----------|--------|\n")
        for task in comp['missing_tasks']:
            report.append(f"| {task['wbs']} | {task['title']} | {task['parent']} |\n")
        report.append("\n")
    
    report.append("### 2. 父子任务时间逻辑检查\n\n")
    if pc['conflict_count'] == 0:
        report.append("✅ 通过检查 - 未发现父子任务时间冲突\n\n")
    else:
        report.append(f"❌ **发现 {pc['conflict_count']} 个父子时间冲突**\n\n")
        report.append("| 冲突类型 | 子任务 | 父任务 | 详情 |\n")
        report.append("|----------|--------|--------|------|\n")
        for conflict in pc['conflicts'][:10]:
            if conflict['type'] == 'start_early':
                detail = f"子任务开始 {conflict['child_start'].strftime('%Y-%m-%d')} 早于父任务 {conflict['parent_start'].strftime('%Y-%m-%d')}"
            else:
                detail = f"子任务结束 {conflict['child_end'].strftime('%Y-%m-%d')} 晚于父任务 {conflict['parent_end'].strftime('%Y-%m-%d')}"
            report.append(f"| {conflict['type']} | {conflict['child']} | {conflict['parent']} | {detail} |\n")
        report.append("\n")
    
    report.append("### 3. 同层级子任务时间顺序检查\n\n")
    if sib['overlap_count'] == 0:
        report.append("✅ 通过检查 - 所有同层任务时间顺序合理\n\n")
    else:
        report.append(f"❌ **发现 {sib['overlap_count']} 个时间重叠/倒序问题**\n\n")
        report.append("前 20 个重叠示例：\n\n")
        report.append("| 任务 1 | 任务 1 结束 | 任务 2 | 任务 2 开始 | 重叠天数 | 父任务 |\n")
        report.append("|--------|------------|--------|------------|----------|--------|\n")
        for overlap in sib['overlaps']:
            end1_str = overlap['task1_end'].strftime('%Y-%m-%d') if overlap['task1_end'] else ''
            start2_str = overlap['task2_start'].strftime('%Y-%m-%d') if overlap['task2_start'] else ''
            report.append(f"| {overlap['task1_title']} | {end1_str} | {overlap['task2_title']} | {start2_str} | {overlap['overlap_days']} | {overlap['parent']} |\n")
        report.append("\n")
        
        if sib['overlap_count'] > 20:
            report.append(f"*...还有 {sib['overlap_count'] - 20} 个重叠未显示*\n\n")
    
    report.append("### 4. 时间范围有效性检查\n\n")
    if val['invalid_count'] == 0:
        report.append("✅ 通过检查 - 所有任务的截止时间都不早于开始时间\n\n")
    else:
        report.append(f"❌ **发现 {val['invalid_count']} 个任务时间范围无效**\n\n")
        report.append("| WBS 编号 | 任务标题 | 开始时间 | 截止时间 |\n")
        report.append("|----------|----------|----------|----------|\n")
        for task in val['invalid_tasks']:
            start_str = task['start'].strftime('%Y-%m-%d') if task['start'] else ''
            end_str = task['end'].strftime('%Y-%m-%d') if task['end'] else ''
            report.append(f"| {task['wbs']} | {task['title']} | {start_str} | {end_str} |\n")
        report.append("\n")
    
    report.append("## 📈 问题分析与建议\n\n")
    
    if total_issues == 0:
        report.append("✅ 项目计划整体质量良好，时间逻辑自洽，可以执行。\n\n")
    else:
        if sib['overlap_count'] > len(df) * 0.7:
            report.append("**主要问题**: 大量任务时间重叠（超过 70%）\n\n")
            report.append("**原因分析**: 这通常是因为从 Teambition 批量导出时，所有任务使用了相同的默认时间值。\n\n")
            report.append("**改进建议**:\n")
            report.append("1. 使用 `teambition-project-planner` 技能重新排期\n")
            report.append("2. 基于 WBS 结构建立真实的任务依赖关系\n")
            report.append("3. 为关键路径任务设置合理的时间缓冲\n\n")
        elif comp['missing_count'] > 0:
            report.append("**主要问题**: 部分任务缺失时间信息\n\n")
            report.append("**原因分析**: 这些任务可能是模板任务或尚未规划的任务。\n\n")
            report.append("**改进建议**:\n")
            report.append("1. 根据实际工作计划补充缺失的时间字段\n")
            report.append("2. 如确认为模板任务，可暂时忽略\n\n")
        elif pc['conflict_count'] > 0:
            report.append("**主要问题**: 存在父子任务时间冲突\n\n")
            report.append("**原因分析**: 通常是手动调整子任务时间时导致的疏忽。\n\n")
            report.append("**改进建议**:\n")
            report.append("1. 调整子任务时间，确保在父任务时间范围内\n")
            report.append("2. 或者扩大父任务时间范围以包含所有子任务\n\n")
    
    report.append("## 📋 下一步行动\n\n")
    if total_issues > 50:
        report.append("⚠️ **问题数量较多**，建议采取以下行动：\n\n")
        report.append("1. **优先处理**: 使用 `teambition-project-planner` 技能重新排期\n")
        report.append("2. **重点关注**: 关键路径上的任务时间安排\n")
        report.append("3. **验证确认**: 重新排期后再次运行本验证工具\n\n")
    elif total_issues > 0:
        report.append("📝 **问题数量可控**，建议采取以下行动：\n\n")
        report.append("1. **手动调整**: 根据上述检查结果修正问题任务\n")
        report.append("2. **标记并行**: 如某些重叠任务是合理的并行工作，可在报告中注明\n")
        report.append("3. **定期复查**: 在项目关键节点前再次验证\n\n")
    else:
        report.append("✅ **无需额外行动**，项目计划可以直接使用。\n\n")
    
    report.append("---\n*报告由 project-plan-validator 技能自动生成*\n")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(report)
    
    return total_issues


def process_excel(input_path, output_dir=None):
    """主处理函数"""
    print(f"📂 正在读取文件：{input_path}")
    
    try:
        df = pd.read_excel(input_path)
        print(f"✅ 成功读取 {len(df)} 个任务")
    except Exception as e:
        print(f"❌ 读取文件失败：{e}")
        return None
    
    # 检查必要列
    required_cols = ['标题']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"❌ 缺少必要列：{missing_cols}")
        return None
    
    # 检查是否有任务层级列，如果没有则推断
    if '任务层级' not in df.columns:
        if '父任务' in df.columns:
            print("🔢 未找到'任务层级'列，根据父子关系推断...")
            df['任务层级'] = infer_task_level_from_parent(df)
        else:
            print("⚠️ 未找到'任务层级'列和'父任务'列，默认所有任务为层级 1")
            df['任务层级'] = 1
    else:
        print("✅ 找到'任务层级'列")
    
    print("🔢 正在生成 WBS 编号...")
    wbs_numbers = generate_wbs_numbering(df)
    df.insert(0, '序号', wbs_numbers)
    print(f"✅ WBS 编号生成完成")
    
    if output_dir is None:
        output_dir = os.path.dirname(input_path)
    
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    wbs_output_path = os.path.join(output_dir, f"{base_name}_WBS.xlsx")
    
    print(f"💾 保存带 WBS 编号的 Excel: {wbs_output_path}")
    
    # 使用 pandas 直接保存，确保 WBS 编号正确写入
    df.to_excel(wbs_output_path, index=False)
    print(f"✅ WBS Excel 已保存")
    
    print("🔍 正在执行时间逻辑检查...")
    check_results = {
        'completeness': check_time_field_completeness(df),
        'parent_child': check_parent_child_time_logic(df),
        'sibling_order': check_sibling_time_order(df),
        'validity': check_time_range_validity(df)
    }
    
    total_issues = (
        check_results['completeness']['missing_count'] +
        check_results['parent_child']['conflict_count'] +
        check_results['sibling_order']['overlap_count'] +
        check_results['validity']['invalid_count']
    )
    
    print(f"{'✅' if total_issues == 0 else '⚠️'} 检查完成，发现 {total_issues} 个问题")
    
    report_path = os.path.join(output_dir, f"{base_name}_验证报告.md")
    print(f"📝 正在生成验证报告：{report_path}")
    generate_report(df, wbs_numbers, check_results, report_path)
    print(f"✅ 报告已生成")
    
    return {
        'wbs_file': wbs_output_path,
        'report_file': report_path,
        'total_issues': total_issues,
        'check_results': check_results
    }


if __name__ == "__main__":
    if len(sys.argv)< 2:
        print("用法：python wbs_generator.py <输入 Excel 文件> [输出目录]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = process_excel(input_file, output_dir)
    
    if result:
        print("\n" + "="*60)
        print("🎉 处理完成!")
        print("="*60)
        print(f"📄 WBS 文件：{result['wbs_file']}")
        print(f"📋 验证报告：{result['report_file']}")
        print(f"⚠️  问题总数：{result['total_issues']}")
        print("="*60)
