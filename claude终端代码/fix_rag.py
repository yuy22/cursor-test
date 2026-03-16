#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 _rag.md 三类问题：
  1. 删除页眉行（数学教师教学用书 / 四年级下册 / 关于教师教学用书的使用说明）
  2. 去掉 #### 段落的 ' 前缀，还原被误替换的逗号（ ' → ，）
  3. 合并被页眉截断的碎片段落
"""

import re, sys
sys.stdout.reconfigure(encoding='utf-8')

INPUT  = r'C:\Users\b886855456ly\Desktop\四年级下册\word\教师用书_md_v2\北师大版4年级数学下册教师用书_rag.md'
OUTPUT = r'C:\Users\b886855456ly\Desktop\四年级下册\word\教师用书_md_v2\北师大版4年级数学下册教师用书_rag_fixed.md'

# ── 页眉模式 ─────────────────────────────────────────────────────
# 处理三种形式：合并一行 / 单独"数学教师教学用书" / 单独"四年级下册"
PAGE_HEADER = re.compile(
    r'^#{0,6}\s*(?:'
    r'数学\s+教师教学用书(?:\s+四年级\s+下册)?|'
    r'四年级\s+下册|'
    r'关于教师教学用书的使用说明'
    r')\s*$'
)

# ── 章节标题特征（不可被合并进去） ──────────────────────────────
HEADING_START = re.compile(
    r'^(?:'
    r'\([一二三四五六七八九十百零]+\)|'   # (一)(二)
    r'[一二三四五六七八九十]+\s*[、，]|'  # 一、二、（含空格）
    r'\d+[\.、]\s|'                       # 1. 2、
    r'第[一二三四五六七八九十\d]+|'       # 第一
    r'\([0-9]+\)\s'                       # (1) (10)
    r')'
)

SENT_END = set('。！？…')


def is_page_header(line: str) -> bool:
    return bool(PAGE_HEADER.match(line.strip()))


def is_heading(s: str) -> bool:
    return bool(HEADING_START.match(s.strip()))


def mid_cut(s: str) -> bool:
    """末尾无句号，句子未完"""
    c = s.rstrip()
    return bool(c) and c[-1] not in SENT_END and c[-1] not in '）】」\'"'


def strip_quotes(s: str):
    """去掉开头的 ' 前缀，返回 (数量, 干净文本)"""
    c, n = s.lstrip(), 0
    while c.startswith("'"):
        c, n = c[1:].lstrip(), n + 1
    return n, c


def fix_inline_quotes(s: str) -> str:
    """把正文中间的 ' 还原为中文逗号"""
    return re.sub(r" ' ", "，", s)


# ── 主流程 ────────────────────────────────────────────────────────
def process():
    lines = open(INPUT, encoding='utf-8').read().splitlines()

    # ── 第一遍：删页眉，解析每行类型 ─────────────────────────────
    # type: 'h4' | 'other' | 'blank'
    parsed = []
    for line in lines:
        if is_page_header(line):
            continue
        if line.startswith('####'):
            raw = line[4:].lstrip()
            n, clean = strip_quotes(raw)
            clean = fix_inline_quotes(clean).strip()
            if clean:
                parsed.append(('h4', clean, n > 0))
        elif line.strip():
            parsed.append(('other', line, False))
        else:
            parsed.append(('blank', '', False))

    # ── 辅助：判断 other 行是否是正文内容（非图描述元数据）──────
    IMG_META = re.compile(
        r'^(?:\*\*|\bMATH\b|\bDIAGRAM\b|\bTEXT_IMAGE\b|\bFRAMEWORK\b|'
        r'\bDECORATIVE\b|>\s*\*\*\[图|•|【|[#]{1,3}\s)'
    )

    def is_content_other(s: str) -> bool:
        """other 行是正文片段（有足量中文且非图描述元数据）"""
        s = s.strip()
        if len(s) < 15 or IMG_META.match(s):
            return False
        return sum(1 for c in s if '\u4e00' <= c <= '\u9fff') >= 5

    # ── 第二遍：合并碎片 ─────────────────────────────────────────
    out = []        # [(type, content)]
    last_h4 = None  # out 中最后一个 h4 的下标
    last_midcut_other = None  # 最近一个末尾截断的正文 other 行下标

    for typ, content, was_cont in parsed:
        if typ != 'h4':
            out.append((typ, content))
            if typ == 'other':
                if is_content_other(content):
                    if mid_cut(content):
                        last_midcut_other = len(out) - 1
                    # 内容型 other 行：不重置 last_h4，让后面的 #### 仍可合并
                else:
                    # 图描述元数据等：不重置，只是中间的噪声
                    pass
            continue

        merge = False
        merge_target = None  # out 中合并目标的下标

        # 选出最近一个可合并的上文：last_h4 或 last_midcut_other 取更新的
        candidates = []
        if last_h4 is not None:
            candidates.append(last_h4)
        if last_midcut_other is not None:
            candidates.append(last_midcut_other)

        best = max(candidates) if candidates else None

        if best is not None:
            prev_typ, prev_content = out[best]
            prev_ok = not is_heading(prev_content)
            curr_ok = not is_heading(content)
            if was_cont and prev_ok:
                merge, merge_target = True, best
            elif mid_cut(prev_content) and prev_ok and curr_ok:
                merge, merge_target = True, best

        if merge and merge_target is not None:
            out[merge_target] = (out[merge_target][0], out[merge_target][1] + content)
            last_h4 = merge_target
            last_midcut_other = None
        else:
            out.append(('h4', content))
            last_h4 = len(out) - 1
            last_midcut_other = None

    # ── 第三遍：输出 ─────────────────────────────────────────────
    result = []
    for typ, content in out:
        if typ == 'h4':
            result.append(f'#### {content}')
            result.append('')
        elif typ == 'blank':
            result.append('')
        else:
            result.append(content)

    text = '\n'.join(result)
    text = re.sub(r'\n{3,}', '\n\n', text).strip() + '\n'
    open(OUTPUT, 'w', encoding='utf-8').write(text)

    # ── 统计 ────────────────────────────────────────────────────
    h4_in  = sum(1 for t, *_ in parsed if t == 'h4')
    h4_out = sum(1 for t, _ in out    if t == 'h4')
    print(f'✓ 完成')
    print(f'  删除页眉行: {len(lines) - len(parsed) - sum(1 for t,*_ in parsed if t=="blank")} 行（估算）')
    print(f'  输入 #### 段落: {h4_in}')
    print(f'  输出 #### 段落: {h4_out}  （合并碎片: {h4_in - h4_out} 个）')
    print(f'  输出文件: {OUTPUT}')


process()
