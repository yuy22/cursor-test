# -*- coding: utf-8 -*-
"""
《低头找幸福》二次清洗
针对第一遍漏网的噪声做正则修复：
  1. 出版社信息表格块
  2. 页眉/页脚行（"数字 俞正强：低头找" / "第X章...数字"）
  3. 目录行（含 /数字 页码）
  4. 封面碎片行
  5. 丛书编委会信息块
  6. OCR 书名行
"""
import re
from pathlib import Path

SRC = Path(__file__).parent / "output" / "低头找幸福_cleaned" / "低头找幸福_cleaned.md"
DST = SRC  # 原地修改

lines = SRC.read_text(encoding='utf-8').splitlines()

# ── 二次噪声规则（每条命中即删整行）──────────────────────────
SECOND_NOISE = [
    # 页眉/页脚：" 数字 俞正强" 或 "俞正强：低头找" 开头的短行
    re.compile(r'^\d+\s+俞正强[：:][^，。\n]{0,20}$'),
    re.compile(r'^俞正强[：:][^，。\n]{0,20}$'),
    # 章节页眉 "第X章 ... 数字" 行尾纯数字
    re.compile(r'^第[一二三四五六七八九十]+章.{2,30}\d+\s*$'),
    # 目录行：含 /数字（页码）
    re.compile(r'.+/\d+\s*$'),
    # 封面/扉页碎片
    re.compile(r'^低头找\s*$'),
    re.compile(r'^低\s+头\s+找[，,]?\s*$'),
    re.compile(r'^王永红\s*$'),
    # 丛书编委会行
    re.compile(r'^名师成长轨迹访谈录\s+丛书编委会\s*$'),
    re.compile(r'^学术顾问[：:]\s*顾明远'),
    re.compile(r'^主\s+任[：:]\s*张斌贤'),
    re.compile(r'^委\s+员\s*[（\(]按音序排列[）\)]'),
    re.compile(r'^丛立新\s*郭华\s*楼世洲'),
    # 书目引用行（"书名/作者.一出版社"）
    re.compile(r'俞正强[：:][^/]+/王永红\.一'),
    re.compile(r'[（\(]名师成长轨迹访谈录'),
    # 孤立的3字以下汉字行（可能是遗漏的人名/短标签，保护##开头的标题行）
    re.compile(r'^(?!#)[\u4e00-\u9fff]{2,3}\s*$'),
    # 行尾孤立数字短行（如 "光" "突" 这类单字OCR碎片）
    re.compile(r'^[\u4e00-\u9fff]{1}\s*$'),
    # 纯数字带点（"230." 这类页眉数字行）
    re.compile(r'^\d+\.\s*$'),
    # 页眉：数字 + 俞正强（含可能的空格）
    re.compile(r'^\d+\s+俞正强\s*[：:]\s*低头找'),
    # "目 录 数字" 页眉行
    re.compile(r'^目\s+录\s+\d+\s*$'),
]

# ── 出版社信息表格块检测 ────────────────────────────────────
TABLE_START = re.compile(r'^\|\s*(出\s*版\s*发\s*行|出版发行)\s*\|')

def is_publisher_table_row(line):
    """出版社信息表格的行"""
    pub_keywords = ['出版发行', '出 版发行', '社    址', '社   址', '社  址', '社 址',
                    '邮    编', '邮   编', '邮  编', '传   真', '网    址',
                    '市场部电话', '编辑部电话', '经    销', '制    作',
                    '印    刷', '开   本', '印    张', '字   数',
                    '印    次', '版    次', '印    数', '定    价',
                    '教有井等出既社', '北京 ·朝阳']
    return any(kw in line for kw in pub_keywords)

def is_noise_line(line):
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith('#'):
        return False
    for pat in SECOND_NOISE:
        if pat.search(stripped):
            return True
    if stripped.startswith('|') and is_publisher_table_row(stripped):
        return True
    return False


# ── 主处理 ────────────────────────────────────────────────
cleaned = []
skip_table = False
removed = 0

for line in lines:
    stripped = line.strip()

    # 出版社表格：检测到表格开始行，跳过整个表格块（直到表格结束）
    if stripped.startswith('|'):
        if TABLE_START.match(stripped) or is_publisher_table_row(stripped):
            skip_table = True
        if skip_table:
            removed += 1
            continue
    else:
        skip_table = False

    if is_noise_line(line):
        removed += 1
        continue

    cleaned.append(line)

# 合并多余空行
output = []
blank_count = 0
for line in cleaned:
    if line.strip() == '':
        blank_count += 1
        if blank_count <= 1:
            output.append(line)
    else:
        blank_count = 0
        output.append(line)

# 已知 OCR 字错误修正（忠实原文，仅修正明显误识别）
text = '\n'.join(output).strip() + '\n'
text = text.replace('教育的意义右于让学生', '教育的意义在于让学生')

DST.write_text(text, encoding='utf-8')

print(f'二次清洗完成')
print(f'  输入行数: {len(lines)}')
print(f'  删除行数: {removed}')
print(f'  输出行数: {len(output)}')
print(f'  输出文件: {DST}')
