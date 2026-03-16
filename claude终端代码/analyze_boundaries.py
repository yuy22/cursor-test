# -*- coding: utf-8 -*-
"""
analyze_boundaries.py — 找出 #### 学习目标 / #### 教学记录 标记，确定课时边界
"""

import re, sys
sys.stdout.reconfigure(encoding='utf-8')

MD_PATH = r"C:\Users\b886855456ly\Desktop\北师大版4年级数学下册教师用书(1)_RAG优化_base64.md"
text = open(MD_PATH, encoding='utf-8').read()
lines = text.split('\n')

# 找所有 H2/H3/H4 标题，特别关注 学习目标 和 教学记录
print("=== 教学内容区域的 H2~H4 标题 ===")
print("（只看行800以后的实际教学内容）\n")

current_h2 = ""
for i, line in enumerate(lines):
    if i < 799:
        continue
    m = re.match(r'^(#{2,4}) (.+)', line)
    if m:
        level = len(m.group(1))
        title = m.group(2).strip()

        if level == 2:
            current_h2 = title
            print(f'\n{"="*60}')
            print(f'行{i+1:5d}  H{level}  {title}')
            print(f'{"="*60}')
        elif level == 3:
            print(f'行{i+1:5d}  H{level}    {title[:80]}')
        elif level == 4 and any(k in title for k in ['学习目标', '教学记录', '编写说明', '教学建议']):
            print(f'行{i+1:5d}  H{level}      [{title}]')
