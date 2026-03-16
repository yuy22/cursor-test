# -*- coding: utf-8 -*-
"""
split_by_lesson.py v2 — 按 PPT 课时精确切分教师用书

基于手动映射表，将 _RAG优化_base64.md 切分为 49 个课时文件。
每个课时文件包含：单元面包屑 + 概述（学习目标/编写说明）+ 正文 + 图片（base64完整）。

输出结构：
  lessons/
  ├── 第一单元 小数的意义和加减法/
  │   ├── 00_单元概述.md
  │   ├── 01_小数的意义（一）.md
  │   └── ...
  └── ...
"""

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# ============================================================
#  配置
# ============================================================

INPUT_FILE = Path(r"C:\Users\b886855456ly\Desktop\北师大版4年级数学下册教师用书(1)_RAG优化_base64.md")
OUTPUT_DIR = Path(r"C:\Users\b886855456ly\Desktop\Claude结果\lessons")

DRY_RUN = "--dry-run" in sys.argv
TEST_LESSON = None
for arg in sys.argv[1:]:
    if not arg.startswith("--"):
        TEST_LESSON = arg

# ============================================================
#  课时映射表
#  格式: (单元文件夹名, 序号, 课时名, [(起始行, 结束行), ...])
#  行号为 1-indexed，结束行 exclusive
# ============================================================

UNIT1 = "第一单元 小数的意义和加减法"
UNIT2 = "第二单元 认识三角形和四边形"
UNIT3 = "第三单元 小数乘法"
UNIT4 = "第四单元 观察物体"
UNIT5 = "第五单元 认识方程"
UNIT6 = "第六单元 数据的表示和分析"
UNIT7 = "第七单元 总复习"
UNITX = "数学好玩"

MAPPING = [
    # ── 单元概述 ──
    (UNIT1, "00", "单元概述", [(804, 978)]),
    (UNIT2, "00", "单元概述", [(2503, 2572)]),
    (UNIT3, "00", "单元概述", [(3983, 4053)]),
    (UNIT4, "00", "单元概述", [(5963, 6033)]),
    (UNIT5, "00", "单元概述", [(6470, 6543)]),
    (UNIT6, "00", "单元概述", [(8322, 8384)]),
    (UNIT7, "00", "单元概述", [(10330, 10356)]),

    # ── 第一单元 ──
    (UNIT1, "01", "小数的意义（一）", [(979, 996), (1000, 1145)]),
    (UNIT1, "02", "小数的意义（二）", [(1146, 1345)]),
    (UNIT1, "03", "小数的意义（三）", [(1346, 1589)]),
    (UNIT1, "04", "小数的性质", [(1473, 1589)]),
    (UNIT1, "05", "比大小", [(1590, 1689)]),
    (UNIT1, "06", "买菜", [(1690, 1801)]),
    (UNIT1, "07", "比身高", [(1802, 1931)]),
    (UNIT1, "08", "比身高（试一试）", [(1932, 2065)]),
    (UNIT1, "09", "歌手大赛", [(2066, 2218)]),
    (UNIT1, "10", "练习与复习", [(2219, 2380)]),

    # ── 第二单元 ──
    (UNIT2, "01", "图形的分类", [(2572, 2793)]),
    (UNIT2, "02", "三角形分类", [(2794, 2942)]),
    (UNIT2, "03", "三角形内角和", [(2943, 3176)]),
    (UNIT2, "04", "三角形内角和（试一试）", [(3086, 3176)]),
    (UNIT2, "05", "三角形边的关系", [(3177, 3577)]),
    (UNIT2, "06", "四边形的分类", [(3253, 3577)]),
    (UNIT2, "07", "整理与复习", [(3578, 3920)]),

    # ── 第三单元 ──
    (UNIT3, "01", "买文具", [(4054, 4320)]),
    (UNIT3, "02", "小数点搬家", [(4321, 4585)]),
    (UNIT3, "03", "小数点搬家（试一试）", [(4442, 4585)]),
    (UNIT3, "04", "街心广场", [(4586, 4805)]),
    (UNIT3, "05", "包装", [(4806, 4984)]),
    (UNIT3, "06", "蚕丝", [(4985, 5301)]),
    (UNIT3, "07", "手拉手", [(5145, 5301)]),
    (UNIT3, "08", "整理与复习", [(5302, 5496)]),
    (UNIT3, "09", "期中整理与复习", [(5660, 5962)]),

    # ── 第四单元 ──
    (UNIT4, "01", "看一看", [(6034, 6214)]),
    (UNIT4, "02", "我说你搭", [(6215, 6295)]),
    (UNIT4, "03", "搭一搭", [(6296, 6466)]),

    # ── 第五单元 ──
    (UNIT5, "01", "字母表示数", [(6544, 6738), (6667, 6876)]),
    (UNIT5, "02", "字母表示数（试一试）", [(6739, 6876)]),
    (UNIT5, "03", "等量关系", [(6877, 7017)]),
    (UNIT5, "04", "方程", [(7018, 7221)]),
    (UNIT5, "05", "解方程（一）", [(7222, 7395)]),
    (UNIT5, "06", "解方程（二）", [(7396, 7584)]),
    (UNIT5, "07", "猜数游戏", [(7585, 7677)]),
    (UNIT5, "08", "整理与复习", [(7678, 7820)]),

    # ── 第六单元 ──
    (UNIT6, "01", "生日", [(8385, 8730)]),
    (UNIT6, "02", "栽蒜苗（一）", [(8731, 8955)]),
    (UNIT6, "03", "栽蒜苗（二）", [(8956, 9075)]),
    (UNIT6, "04", "平均数", [(9076, 9405)]),
    (UNIT6, "05", "平均数（试一试）", [(9248, 9405)]),
    (UNIT6, "06", "整理与复习", [(9406, 9684)]),

    # ── 第七单元 ──
    (UNIT7, "01", "数与代数总复习", [(10357, 10474)]),
    (UNIT7, "02", "图形与几何总复习", [(10475, 10816)]),
    (UNIT7, "03", "统计与概率总复习", [(10817, 10905)]),

    # ── 数学好玩 ──
    (UNITX, "01", "密铺", [(7928, 7951), (7952, 8162)]),
    (UNITX, "02", "奥运中的数学", [(8163, 8236)]),
    (UNITX, "03", "优化", [(8237, 8318)]),
]

# ============================================================
#  Windows 文件名清理
# ============================================================

ILLEGAL = re.compile(r'[\\/:*?"<>|]')

def clean_name(s):
    return ILLEGAL.sub('', s).strip()

# ============================================================
#  主逻辑
# ============================================================

def main():
    text = INPUT_FILE.read_text(encoding='utf-8')
    lines = text.split('\n')
    total_lines = len(lines)

    written = 0
    total_imgs = 0

    for unit_folder, seq, lesson_name, ranges in MAPPING:
        if TEST_LESSON and TEST_LESSON not in lesson_name:
            continue

        # 合并所有行范围（去重）
        included_lines = set()
        for start, end in ranges:
            s = max(0, start - 1)  # 转为 0-indexed
            e = min(total_lines, end)
            for i in range(s, e):
                included_lines.add(i)

        section_lines = [lines[i] for i in sorted(included_lines)]
        content = '\n'.join(section_lines)

        # 统计
        img_count = sum(1 for line in section_lines if 'data:image/' in line)
        total_imgs += img_count
        char_count = len(content)

        # 面包屑
        unit_display = unit_folder.split(' ', 1)[1] if ' ' in unit_folder else unit_folder
        breadcrumb = f"> 北师大版四年级数学下册教师教学用书 > {unit_display} > {lesson_name}\n\n"
        full_content = breadcrumb + content

        # 输出路径
        folder = OUTPUT_DIR / clean_name(unit_folder)
        fname = f"{seq}_{clean_name(lesson_name)}.md"
        fpath = folder / fname

        if DRY_RUN:
            print(f"  [{unit_folder}] {fname}: {len(section_lines)}行, {img_count}图, {char_count // 1024}KB")
        else:
            folder.mkdir(parents=True, exist_ok=True)
            fpath.write_text(full_content, encoding='utf-8')
            print(f"  ✅ {unit_folder}/{fname}: {len(section_lines)}行, {img_count}图, {char_count // 1024}KB")

        written += 1

    print(f"\n{'[DRY-RUN] ' if DRY_RUN else ''}共输出 {written} 个文件, {total_imgs} 张图片")


if __name__ == "__main__":
    main()
