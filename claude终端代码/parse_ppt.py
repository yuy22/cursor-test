# -*- coding: utf-8 -*-
import re, sys, os

sys.stdout.reconfigure(encoding='utf-8')

files = os.listdir(r'E:\四年级数学')
ppts = [f for f in files if f.endswith('.pptx') and not f.endswith('.tmp')]
ppts.sort()

lessons = []
for f in ppts:
    m = re.match(
        r'(\d+)_(第[一二三四五六七八九十\d]+单元|数学好玩)\s*第?\d*课?时?\s*(.+?)（教学课件）',
        f
    )
    if m:
        lessons.append((m.group(1), m.group(2), m.group(3).strip()))
    else:
        print(f'warn: {f}')

current_unit = ''
for seq, unit, name in lessons:
    if unit != current_unit:
        current_unit = unit
        print(f'\n{unit}')
    print(f'  {seq}. {name}')

print(f'\ntotal: {len(lessons)}')
