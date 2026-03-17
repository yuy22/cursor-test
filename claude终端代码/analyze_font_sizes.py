# -*- coding: utf-8 -*-
"""分析三个 docx 文件的字号分布，确定标题层级映射"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from docx import Document
from collections import Counter

_base = Path(os.environ.get("MATH_TOOLKIT_BASE", str(Path.cwd())))
_names = ["四年级+整合与拓展.docx", "王永春《小学数学教材一本通》.docx", "俞正强：低头找幸福.docx"]
DOCS = []
for n in _names:
    for p in [_base / "input" / n, _base / n]:
        if p.exists():
            DOCS.append(p)
            break

for path in DOCS:
    print(f'\n{"="*60}')
    print(f'文件：{path.name}')
    print('='*60)

    doc = Document(path)
    size_samples = {}
    size_counts = Counter()

    for p in doc.paragraphs:
        if not p.text.strip():
            continue
        # 取第一个有字号的 run
        size_pt = None
        bold = False
        style = p.style.name if p.style else ''
        for run in p.runs:
            if run.font.size:
                size_pt = round(run.font.size.pt, 1)
                bold = bool(run.bold)
                break
        key = (size_pt, bold, style)
        size_counts[key] += 1
        if key not in size_samples:
            size_samples[key] = p.text.strip()[:60]

    print(f'{"字号(pt)":<10} {"加粗":<6} {"样式名":<25} {"出现次数":<8} 示例文本')
    print('-'*90)
    for (sz, b, st), cnt in sorted(size_counts.items(), key=lambda x: (-(x[0][0] or 0), not x[0][1])):
        sz_str = f'{sz}pt' if sz else 'None'
        print(f'{sz_str:<10} {str(b):<6} {st:<25} {cnt:<8} {size_samples[(sz,b,st)]}')
