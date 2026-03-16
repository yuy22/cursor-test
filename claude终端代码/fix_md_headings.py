#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# ============================================================
# 教材 Markdown 标题层级修复工具 (RAG 优化)
# ============================================================
# 针对 TextIn OCR 生成的教材 MD 文件，
# 修复标题层级混乱问题，使 RAG 分块能建立正确的层级上下文。
#
# 支持两本教材：
#   1. 北师大版4年级数学下册教师用书
#   2. 四年级 整合与拓展课例精选
# ============================================================
"""

import re
import sys
from pathlib import Path


# ============================================================
# 通用工具
# ============================================================

def parse_heading(line: str):
    """解析标题行，返回 (级别, 内容) 或 None"""
    m = re.match(r'^(#{1,6})\s+(.*)', line)
    if m:
        return len(m.group(1)), m.group(2).strip()
    return None


def make_heading(level: int, text: str) -> str:
    """生成标题行"""
    return '#' * level + ' ' + text


def stat_headings(lines: list[str]) -> dict:
    """统计各级标题数量"""
    counts = {i: 0 for i in range(1, 7)}
    for line in lines:
        h = parse_heading(line)
        if h:
            counts[h[0]] += 1
    return counts


def print_stats(label: str, lines: list[str]):
    """打印标题统计"""
    counts = stat_headings(lines)
    print(f"\n{'=' * 50}")
    print(f"  {label}")
    print(f"{'=' * 50}")
    for lv in range(1, 7):
        if counts[lv] > 0:
            print(f"  H{lv}: {counts[lv]}")
    total = sum(counts.values())
    print(f"  总计: {total}")


# ============================================================
# 文件1：北师大版教师用书 — 标题修复
# ============================================================

# 单元名列表（从目录提取）
BOOK1_UNITS = [
    '小数的意义和加减法',
    '认识三角形和四边形',
    '小数乘法',
    '观察物体',
    '认识方程',
    '数据的表示和分析',
]

# 课节名列表（从目录和正文提取）
BOOK1_LESSONS = [
    # 第一单元
    '小数的意义（一）', '小数的意义（二）', '小数的意义（三）',
    '比大小', '买菜', '比身高',
    '歌手大赛',
    # 第二单元
    '图形分类', '三角形分类',
    '探索与发现：三角形内角和', '探索与发现：三角形边的关系',
    '四边形分类',
    # 第三单元
    '小数点搬家', '街心广场', '包装', '蚕丝', '手拉手',
    # 第四单元
    '看一看', '我说你搭', '搭一搭',
    # 第五单元
    '字母表示数', '等量关系', '方程', '解方程（一）', '解方程（二）',
    '猜数游戏',
    # 第六单元
    '栽蒜苗（一）', '栽蒜苗（二）', '平均数',
    # 数学好玩
    '密铺', '奥运中的数学', '优化',
]

# 拼音噪声模式（全大写英文，OCR 产生的拼音行）
PINYIN_RE = re.compile(r'^#{1,6}\s+[A-Z]{4,}(\s+[A-Z]{4,})*\s*$')

# 匹配单元标号（一～六 或 数字，后面跟空格）
UNIT_NUM_RE = re.compile(
    r'^[一二三四五六七八九十\d]+\s+'
)


def fix_book1(lines: list[str]) -> list[str]:
    """修复教师用书标题层级"""
    out = []
    h1_done = False
    toc_seen = False     # 是否已经过目录区
    in_toc = False       # 正在目录区内

    for i, line in enumerate(lines):
        h = parse_heading(line)

        # 非标题行直接保留
        if h is None:
            out.append(line)
            continue

        level, text = h
        clean = text.strip()

        # ====================================================
        # 规则0：删除拼音噪声行
        # ====================================================
        if PINYIN_RE.match(line):
            continue

        # ====================================================
        # 规则1：H1 — 全书仅一个，封面区域全部跳过
        # ====================================================
        if i < 20:
            if not h1_done and level == 1:
                out.append(make_heading(1, '北师大版四年级数学下册教师教学用书'))
                h1_done = True
            continue

        if not h1_done:
            out.insert(0, make_heading(1, '北师大版四年级数学下册教师教学用书'))
            h1_done = True

        # ====================================================
        # 规则2：目录
        # ====================================================
        if clean == '目录':
            out.append(make_heading(2, '目录'))
            in_toc = True
            continue

        if in_toc:
            if _is_unit_title(clean) and i > 800:
                in_toc = False
                toc_seen = True
            else:
                out.append(line)
                continue

        # ====================================================
        # 前言区（目录之前）: 独立处理
        # ====================================================
        if not toc_seen:
            out.append(_fix_preface_heading(level, clean))
            continue

        # ====================================================
        # 内容区（目录之后）: 单元/课节结构
        # ====================================================
        out.append(_fix_content_heading(level, clean))

    return out


def _fix_preface_heading(level: int, text: str) -> str:
    """前言区域标题层级修复"""
    # 本套教材配套资源 → H2
    if text.startswith('本套教材配套'):
        return make_heading(2, text)
    # 顺应孩子天性 → H2
    if '顺应孩子天性' in text:
        return make_heading(2, text)
    # 中文编号章节（一、xxx ~ 六、xxx）→ H2
    if re.match(r'^[一二三四五六七八九十]+、', text):
        return make_heading(2, text)
    # 中文编号子章节（（一）xxx ~ （五）xxx）→ H3
    if re.match(r'^（[一二三四五六七八九十]+）', text):
        return make_heading(3, text)
    # 数字编号子节（1．xxx）→ H3
    if re.match(r'^\d+[．.]', text):
        return make_heading(3, text)
    # ###### 级别的子项 → H4+
    if re.match(r'^（\d+）', text):
        return make_heading(4, text)
    # · 或 ■ 开头 → H5
    if text.startswith('·') or text.startswith('■'):
        return make_heading(5, text)
    # 保持原有层级，但最小 H3
    return make_heading(max(level, 3), text)


def _fix_content_heading(level: int, text: str) -> str:
    """内容区域（单元/课节）标题层级修复"""
    # ====================================================
    # H2：单元名 / 大板块
    # ====================================================
    if _is_unit_title(text):
        return make_heading(2, text)
    if _is_major_section(text):
        return make_heading(2, text)
    if '数学万花筒' in text:
        return make_heading(2, text)

    # ====================================================
    # H3：练习X / 课节名 / 单元级板块
    # ====================================================
    if re.match(r'^练习[一二三四五六七八九十\d]+', text):
        return make_heading(3, text)
    if _is_lesson_title(text):
        return make_heading(3, text)
    if _is_unit_section(text):
        return make_heading(3, text)
    if _is_standalone_article(text):
        return make_heading(3, text)
    if _is_essay_title(text):
        return make_heading(3, text)

    # ====================================================
    # H4：课节级板块 / 练一练 / 试一试 / 样题X / 板块X
    # ====================================================
    if _is_lesson_section(text):
        return make_heading(4, text)
    if text in ('练一练', '试一试') or text.startswith('你知道吗'):
        return make_heading(4, text)
    if re.match(r'^样题\s*\d+', text):
        return make_heading(4, text)
    if re.match(r'^板块[一二三四五六七八九十\d]+', text):
        return make_heading(4, text)

    # ====================================================
    # H5：第X题 / · ■ 问题串
    # ====================================================
    if re.match(r'^第\s*[\d,，]+\s*题', text):
        return make_heading(5, text)
    if text.startswith('·') or text.startswith('■'):
        return make_heading(5, text)

    # ====================================================
    # H3：数字编号子项（1．xxx 2．xxx）在单元分析下
    # ====================================================
    if re.match(r'^\d+[．.]', text):
        return make_heading(max(level, 3), text)

    # ====================================================
    # H4：中文编号子项（一、xxx）在课例说明下
    # ====================================================
    if re.match(r'^[一二三四五六七八九十]+、', text):
        return make_heading(max(level, 4), text)

    # ====================================================
    # 兜底：保持原有但最小 H3
    # ====================================================
    return make_heading(max(level, 3), text)


def _is_unit_title(text: str) -> bool:
    """判断是否为单元名标题（严格短标题匹配）"""
    # 拒绝：以 · ■ 开头的问题串
    if text.startswith('·') or text.startswith('■'):
        return False
    # 拒绝：以数字编号开头的分析条目
    if re.match(r'^\d+[．.]', text):
        return False
    # 拒绝：长句（单元名通常 < 25 字符）
    if len(text) > 25:
        return False
    for name in BOOK1_UNITS:
        if name in text:
            # 排除课节级内容（如 "小数的意义（一）"）
            if '（' in text and '）' in text:
                return False
            return True
    # 单元编号模式：一 xxx / 二 xxx / ... / 六 xxx
    if re.match(r'^[一二三四五六]\s+\S', text):
        return True
    return False


def _is_major_section(text: str) -> bool:
    """判断是否为整理与复习 / 总复习 / 数学好玩等大板块"""
    keywords = ['整理与复习', '总复习', '数学好玩']
    for kw in keywords:
        if text.startswith(kw):
            return True
    return False


def _is_lesson_title(text: str) -> bool:
    """判断是否为课节名"""
    # 精确匹配课节名列表
    for name in BOOK1_LESSONS:
        if text.startswith(name):
            return True
    # 含括号的课节名模式：xxx（xxx）
    if re.match(r'^.{2,10}（.+）$', text):
        # 排除单元级和板块级
        if not _is_unit_section(text) and not _is_unit_title(text):
            return True
    # "认识xxx" / "探索xxx" 模式
    if re.match(r'^(认识|探索与发现|探索)', text) and len(text) < 20:
        return True
    return False


def _is_unit_section(text: str) -> bool:
    """判断是否为单元级板块标题"""
    patterns = [
        '单元学习目标', '单元学习内容的前后联系',
        '单元学习内容分析', '课时安排建议', '课时安排',
        '知识技能评价要点',
    ]
    for p in patterns:
        if text.startswith(p):
            return True
    return False


def _is_lesson_section(text: str) -> bool:
    """判断是否为课节级板块"""
    patterns = ['学习目标', '编写说明', '教学建议', '教学记录']
    for p in patterns:
        if text == p or text.startswith(p + '（') or text.startswith(p + ' '):
            return True
        # "# 教学建议" 精确匹配
        if text == p:
            return True
    return False


def _is_standalone_article(text: str) -> bool:
    """教学设计等独立文章"""
    keywords = [
        '教学设计', '教学内容', '教学内容分析',
        '课前思考', '课堂写真', '课后解读', '案例研讨',
        '教具准备', '过程预设', '实施要求',
    ]
    for kw in keywords:
        if text.startswith(kw) or text.endswith(kw):
            return True
    if '教学设计' in text or '教学案例' in text:
        return True
    return False


def _is_essay_title(text: str) -> bool:
    """万花筒子文章或教育评论"""
    keywords = [
        '代数学', '什么是代数', '数学家的眼光',
        '有理数运算', '教育新视野', '新课标',
        '小数', '在分类活动',
    ]
    for kw in keywords:
        if text.startswith(kw):
            return True
    return False


# ============================================================
# 文件2：整合与拓展 — 标题修复
# ============================================================

def fix_book2(lines: list[str]) -> list[str]:
    """修复整合与拓展标题层级"""
    out = []
    h1_done = False

    for i, line in enumerate(lines):
        h = parse_heading(line)

        if h is None:
            out.append(line)
            continue

        level, text = h
        clean = text.strip()

        # ====================================================
        # 规则0：删除拼音噪声
        # ====================================================
        if PINYIN_RE.match(line):
            continue

        # ====================================================
        # 规则1：H1 — 全书仅一个，封面区全部跳过
        # ====================================================
        if i < 70:
            if not h1_done:
                if '整合与拓展' in clean:
                    out.append(make_heading(1, '整合与拓展课例精选·四年级'))
                    h1_done = True
            # 跳过所有封面区标题
            continue

        if not h1_done:
            out.insert(0, make_heading(1, '整合与拓展课例精选·四年级'))
            h1_done = True

        # ====================================================
        # 规则2：前言 / 目录 → H2
        # ====================================================
        if re.match(r'^前言', clean) or re.match(r'^目录', clean):
            out.append(make_heading(2, clean))
            continue

        # ====================================================
        # 规则3：上部/下部 → H2
        # ====================================================
        if re.match(r'^上部', clean) or re.match(r'^下部', clean):
            out.append(make_heading(2, clean))
            continue

        # ====================================================
        # 规则4：附录 → H2
        # ====================================================
        if clean.startswith('附录') or clean.startswith('附件'):
            out.append(make_heading(2, clean))
            continue

        # ====================================================
        # 规则5：第X单元 → H3
        # ====================================================
        if re.match(r'^第[一二三四五六七八九十\d]+', clean) and '单元' in clean:
            out.append(make_heading(3, clean))
            continue

        # 第X单元（无"单元"字样但有单元编号模式）
        if re.match(r'^第[一二三四五六七八九十\d]+单元', clean):
            out.append(make_heading(3, clean))
            continue

        # ====================================================
        # 规则6：单元整合说明 → H4
        # ====================================================
        if clean.startswith('单元整合说明'):
            out.append(make_heading(4, clean))
            continue

        # ====================================================
        # 规则7：整合课课例X / 拓展课课例X → H4
        # ====================================================
        if re.match(r'^(整合课课例|拓展课课例)\s*\d*', clean):
            out.append(make_heading(4, clean))
            continue

        # ====================================================
        # 规则8：一/二/三、xxx 说明子节 → H5
        # ====================================================
        if re.match(r'^[一二三四五六七八九十]+、', clean):
            out.append(make_heading(5, clean))
            continue

        # ====================================================
        # 规则9：【环节X】 → H6
        # ====================================================
        if re.match(r'^【环节[一二三四五六七八九十\d]+】', clean):
            out.append(make_heading(6, clean))
            continue

        # ====================================================
        # 规则10：#N 标记（如 #4 #5）→ 删除
        # ====================================================
        if re.match(r'^#\d+$', clean):
            continue

        # ====================================================
        # 规则11：附录内的政策文件标题 → H3
        # ====================================================
        if re.match(r'^\d{2}[．.]', clean):
            out.append(make_heading(3, clean))
            continue

        # ====================================================
        # 规则12：政策文件内的子节（一）/（二） → H4
        # ====================================================
        if re.match(r'^（[一二三四五六七八九十]+）', clean):
            out.append(make_heading(4, clean))
            continue

        # ====================================================
        # 规则13：编号讨论/反馈/思辨 → H6 或保持正文
        # ====================================================
        if _is_discussion_item(clean):
            out.append(make_heading(6, clean))
            continue

        # ====================================================
        # 规则14：教学过程展开举例 → H5
        # ====================================================
        if '教学过程展开举例' in clean or '教学环节展开举例' in clean:
            out.append(make_heading(5, clean))
            continue

        if '活动过程展开举例' in clean:
            out.append(make_heading(5, clean))
            continue

        # ====================================================
        # 规则15：教学目标定位 → H5
        # ====================================================
        if '教学目标定位' in clean:
            out.append(make_heading(5, clean))
            continue

        # ====================================================
        # 规则16：主题内容说明 / 预期目标 / 材料准备 → H5
        # ====================================================
        if re.match(r'^(主题内容说明|主题预期目标|活动材料准备)', clean):
            out.append(make_heading(5, clean))
            continue

        # ====================================================
        # 规则17：编号子项 1./2./3. → H6
        # ====================================================
        if re.match(r'^\d+[．.]', clean):
            out.append(make_heading(6, clean))
            continue

        # ====================================================
        # 兜底：保持但限制最小为 H4
        # ====================================================
        new_level = max(level, 4)
        out.append(make_heading(new_level, clean))

    return out


def _is_discussion_item(text: str) -> bool:
    """判断是否为讨论/反馈等子项"""
    patterns = [
        r'^（\d+）', r'^\(\d+\)',
        r'^讨论\d+', r'^思辨\d+', r'^反馈\d+',
        r'^作品\d+',
    ]
    for p in patterns:
        if re.match(p, text):
            return True
    return False


# ============================================================
# 阶段2：OCR 噪声清理
# ============================================================

# 出版信息关键词
PUBLISHER_KEYWORDS = [
    '微信公众号', '电子课本大全', 'ISBN', '邮购', '印制管理部',
    '反盗版', '侵权举报', '营销中心电话', '学科编辑电话',
    '基础教育教材网址', '电子邮箱', '通信地址', '配套资源电话',
    '教材编写组', '印 刷', '经 销', '印 张', '字 数',
    '版 次', '印 次', '定 价', '责任编辑', '装帧设计',
    '责任校对', '版权所有', '出版发行', '邮政编码',
    '图书在版编目', 'CIP数据', '中国版本图书馆',
    '责任印制', '封面设计', '责任编辑',
]

# 纯装饰性/噪声行模式
NOISE_PATTERNS = [
    re.compile(r'^[A-Z]{4,}(\s+[A-Z]{4,})+\s*$'),     # 拼音行
    re.compile(r'^\*\*传\*\*$'),                         # 断裂的 "传真"
    re.compile(r'^\*\*真\*\*\s+\d{3}'),                  # 断裂的 "真 010-xxx"
    re.compile(r'^开本：'),                               # 出版规格
    re.compile(r'^丛书编委'),                             # 编委名单
    re.compile(r'^微信扫描二维码'),                       # 二维码提示
    re.compile(r'^＊编者注'),                             # 编者注
]


def clean_noise(lines: list[str], book_type: str) -> list[str]:
    """清理 OCR 噪声"""
    out = []
    skip_block = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # ------------------------------------------------
        # 跳过出版信息块（文件末尾的 CIP 数据等）
        # ------------------------------------------------
        if '图书在版编目' in stripped or ('CIP' in stripped and '数据' in stripped):
            skip_block = True
        if skip_block:
            continue

        # ------------------------------------------------
        # 跳过非 H1 的书名页眉（OCR 抓取的装饰性页眉）
        # ------------------------------------------------
        h = parse_heading(line)
        if h and h[0] > 1:
            book_name = BOOK_NAMES.get(book_type, '')
            if book_name and book_name in h[1]:
                continue

        # ------------------------------------------------
        # 跳过出版信息行
        # ------------------------------------------------
        if _is_publisher_line(stripped):
            continue

        # ------------------------------------------------
        # 跳过拼音/噪声行
        # ------------------------------------------------
        if _is_noise_line(stripped):
            continue

        # ------------------------------------------------
        # 跳过孤立页码行（纯数字，1~4位，前后是空行）
        # ------------------------------------------------
        if _is_page_number(stripped, i, lines):
            continue

        out.append(line)

    return out


def _is_publisher_line(text: str) -> bool:
    """判断是否为出版信息行"""
    plain = text.replace('**', '').strip()
    for kw in PUBLISHER_KEYWORDS:
        if kw in plain:
            return True
    return False


def _is_noise_line(text: str) -> bool:
    """判断是否为噪声行"""
    for pat in NOISE_PATTERNS:
        if pat.match(text):
            return True
    return False


def _is_page_number(text: str, idx: int, lines: list[str]) -> bool:
    """判断是否为孤立页码（纯数字，且前后为空行或文件边界）"""
    if not re.match(r'^\d{1,3}$', text):
        return False
    # 检查前后行是否为空
    prev_empty = (idx == 0) or lines[idx - 1].strip() == ''
    next_empty = (idx >= len(lines) - 1) or lines[idx + 1].strip() == ''
    return prev_empty and next_empty


# ============================================================
# 阶段3：课节结构标准化
# ============================================================

# 文件2 标题变体统一映射
BOOK2_NORMALIZE = {
    '三、教学环节展开举例': '三、教学过程展开举例',
    '活动过程展开举例': '三、活动过程展开举例',
}


def standardize_structure(lines: list[str], book_type: str) -> list[str]:
    """标准化课节子标题命名"""
    out = []
    for line in lines:
        h = parse_heading(line)
        if h:
            level, text = h
            # 统一变体标题
            if book_type == 'book2':
                for old, new in BOOK2_NORMALIZE.items():
                    if old in text:
                        line = make_heading(level, text.replace(old, new))
                        break
        out.append(line)
    return out


# ============================================================
# 阶段4：元数据前缀注入
# ============================================================

BOOK_NAMES = {
    'book1': '北师大版四年级数学下册教师教学用书',
    'book2': '整合与拓展课例精选·四年级',
}


def add_metadata_prefix(lines: list[str], book_type: str) -> list[str]:
    """在每个标题后注入面包屑路径，供 RAG 分块时携带上下文"""
    book_name = BOOK_NAMES.get(book_type, '')
    out = []

    # 面包屑层级追踪
    crumbs = {i: '' for i in range(1, 7)}

    for line in lines:
        h = parse_heading(line)
        if h:
            level, text = h
            # 更新当前层级
            crumbs[level] = text
            # 清除所有下级
            for lv in range(level + 1, 7):
                crumbs[lv] = ''

            out.append(line)

            # 构造面包屑路径（从 H2 开始，H1 是书名不需要重复）
            parts = [book_name]
            for lv in range(2, level + 1):
                if crumbs[lv]:
                    parts.append(crumbs[lv])

            # 只对 H2~H5 注入元数据（H1 是书名，H6 太细）
            if 2 <= level <= 5 and len(parts) > 1:
                breadcrumb = ' > '.join(parts)
                out.append(f'> {breadcrumb}')
                out.append('')
        else:
            out.append(line)

    return out


# ============================================================
# 主入口
# ============================================================

def process_file(input_path: Path, fix_func, output_dir: Path, book_type: str):
    """处理单个文件：标题修复 → 噪声清理 → 结构标准化 → 元数据前缀"""
    print(f"\n读取: {input_path}")
    text = input_path.read_text(encoding='utf-8')
    lines = text.splitlines()

    print_stats('修复前', lines)

    # 阶段1：标题层级修复
    fixed = fix_func(lines)
    print_stats('标题修复后', fixed)

    # 阶段2：OCR 噪声清理
    cleaned = clean_noise(fixed, book_type)
    noise_removed = len(fixed) - len(cleaned)
    print(f"  噪声清理: 删除 {noise_removed} 行")

    # 阶段3：课节结构标准化
    standardized = standardize_structure(cleaned, book_type)

    # 阶段4：元数据前缀注入
    final = add_metadata_prefix(standardized, book_type)

    print_stats('最终结果', final)

    # 输出文件
    stem = input_path.stem
    out_path = output_dir / f"{stem}_RAG优化.md"
    out_path.write_text('\n'.join(final), encoding='utf-8')
    print(f"\n输出: {out_path}")


def main():
    output_dir = Path(r'C:\Users\b886855456ly\Desktop\Claude结果')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 文件1：教师用书
    book1 = Path(r'C:\Users\b886855456ly\Downloads\北师大版4年级数学下册教师用书(1).md')
    if book1.exists():
        process_file(book1, fix_book1, output_dir, 'book1')
    else:
        print(f"文件不存在: {book1}")

    # 文件2：整合与拓展
    book2 = Path(r'C:\Users\b886855456ly\Downloads\四年级+整合与拓展.md')
    if book2.exists():
        process_file(book2, fix_book2, output_dir, 'book2')
    else:
        print(f"文件不存在: {book2}")

    print("\n完成！")


if __name__ == '__main__':
    main()
