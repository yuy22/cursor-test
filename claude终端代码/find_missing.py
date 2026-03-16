# -*- coding: utf-8 -*-
"""
find_missing.py — 查找未匹配课时在MD中的实际内容位置
"""

import re, sys
sys.stdout.reconfigure(encoding='utf-8')

MD_PATH = r"C:\Users\b886855456ly\Desktop\北师大版4年级数学下册教师用书(1)_RAG优化_base64.md"
text = open(MD_PATH, encoding='utf-8').read()
lines = text.split('\n')

# 未匹配的课时及其可能的关键词
MISSING = {
    "小数的性质": ["性质", "涂一涂", "小数末尾"],
    "比大小": ["比大小", "比较小数", "谁跳得"],
    "买菜": ["买菜", "买东西", "售货员", "付多少元"],
    "比身高": ["比身高", "鹿妈妈", "小黑高"],
    "图形的分类": ["图形分类", "图形的分类"],
    "四边形的分类": ["四边形分类", "四边形的分类", "平行四边形", "梯形"],
    "买文具": ["买文具", "文具", "铅笔"],
    "街心广场": ["街心广场"],
    "手拉手": ["手拉手"],
    "期中整理与复习": ["期中"],
    "看一看": ["看一看", "观察物体"],
    "我说你搭": ["我说你搭"],
    "搭一搭": ["搭一搭"],
    "生日": ["生日", "条形统计图"],
    "栽蒜苗（一）": ["栽蒜苗"],
    "数与代数总复习": ["数与代数"],
    "图形与几何总复习": ["图形与几何"],
    "统计与概率总复习": ["统计与概率"],
    "优化": ["优化", "沏茶", "烧水", "烙饼"],
}

for lesson, keywords in MISSING.items():
    print(f"\n=== {lesson} ===")
    for kw in keywords:
        found = False
        for i, line in enumerate(lines):
            if re.match(r'^#{1,5} ', line) and kw in line:
                print(f'  关键词"{kw}" → 行{i+1}: {line[:100]}')
                found = True
        if not found:
            # 搜索正文
            hits = [(i+1, line[:80]) for i, line in enumerate(lines) if kw in line and not line.startswith('!')]
            if hits:
                print(f'  关键词"{kw}" → 出现在正文: 行{hits[0][0]}, {hits[0][1]}...')
                if len(hits) > 1:
                    print(f'    (共{len(hits)}处)')
