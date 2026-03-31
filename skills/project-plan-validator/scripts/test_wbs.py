#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 WBS 编号生成
"""

import pandas as pd

# 读取原始文件
df = pd.read_excel('/Users/guoxinyuan/Downloads/计划管理导出明细.xlsx')
print(f"读取到 {len(df)} 个任务")
print(f"列名：{df.columns.tolist()}")
print("\n前 10 个任务的层级和父任务:")
for i in range(10):
    level = df.iloc[i]['任务层级']
    parent = df.iloc[i].get('父任务', '')
    title = df.iloc[i]['标题']
    print(f"{i+1}. {title} (层级:{level}, 父任务:{parent})")

# 生成 WBS 编号
level_counters = {1: 0, 2: 0, 3: 0, 4: 0}
wbs_numbers = []

for idx, row in df.iterrows():
    level = int(row['任务层级']) if pd.notna(row.get('任务层级')) else 1
    
    # 重置当前层级及所有子层级的计数器
    for l in range(level, 5):
        level_counters[l] = 0
    
    # 当前层级计数器加 1
    level_counters[level] += 1
    
    # 构建 WBS 编号
    wbs_parts = []
    for l in range(1, level + 1):
        wbs_parts.append(str(level_counters[l]))
    
    wbs = '.'.join(wbs_parts)
    wbs_numbers.append(wbs)

print("\n生成的 WBS 编号（前 20 个）:")
for i in range(min(20, len(wbs_numbers))):
    title = df.iloc[i]['标题']
    level = df.iloc[i]['任务层级']
    print(f"{wbs_numbers[i]} - {title} (层级{level})")

# 插入序号列
df.insert(0, '序号', wbs_numbers)

# 保存
output_path = '/Users/guoxinyuan/Downloads/test_wbs.xlsx'
df.to_excel(output_path, index=False)
print(f"\n✅ 测试文件已保存：{output_path}")
print(f"序号列类型：{type(wbs_numbers[0])}")
print(f"前 5 个 WBS 编号：{wbs_numbers[:5]}")
