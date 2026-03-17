# -*- coding: utf-8 -*-
"""
俞正强《低头找幸福》OCR DOCX → Markdown 数据清洗 v2
标题识别：优先字号映射（来自四年级下册数据清洗提示词），其次文本正则
图片分类：面积/长宽比/亮度三级过滤
"""
import sys, re, os, zipfile
sys.stdout.reconfigure(encoding='utf-8')
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table
from pathlib import Path
from lxml import etree

# ╔══════════════════════════════════════╗
# ║            配置                       ║
# ╚══════════════════════════════════════╝
SCRIPT_DIR = Path(__file__).parent
INPUT   = SCRIPT_DIR / "俞正强：低头找幸福(OCR).docx"
OUT_DIR = SCRIPT_DIR / "output" / "低头找幸福_cleaned"
OUT_MD  = OUT_DIR / "低头找幸福_cleaned.md"
IMG_DIR = OUT_DIR / "images"

SMALL_AREA   = 5000
WHITE_THRESH = 230

REL_NS  = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
A_BLIP  = '{http://schemas.openxmlformats.org/drawingml/2006/main}blip'
VML_IMG = '{urn:schemas-microsoft-com:vml}imagedata'
R_EMBED = f'{{{REL_NS}}}embed'
R_ID    = f'{{{REL_NS}}}id'

# ╔══════════════════════════════════════╗
# ║  字号 → Markdown 标题级别映射         ║
# ║  来源：四年级下册数据清洗提示词.md      ║
# ╚══════════════════════════════════════╝
SIZE_TO_HEADING = {
    23.5: 2,   # 教育是一门艺术（4次）
    23.0: 2,   # 我看名师成长（13次）
    22.0: 2,   # 第八章（2次）
    21.5: 2,   # 面向实践，提升
    20.5: 2,   # 引  言
    16.0: 3,   # 1998—2002 忽如一夜春风来（2次）
    15.5: 3,   # 1986—1998 平平淡淡才是真（1次）
    15.0: 3,   # 2."举一反三" 教学设计
    14.5: 4,   # 分数准备课教学设计 / ◎ 学生对我影响很大（27次）
    13.5: 4,   # 访谈手记（33次）
    13.0: 4,   # 二、预设生成 / ◎ 我主要思考课堂问题（7次）
}

# 这些字号确认为页眉/页脚/碎片，直接按字号过滤（不看文字）
NOISE_FONT_SIZES = {4.0, 5.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5}

def get_para_font_size(para):
    """取段落第一个有字号的 run 的字号（pt）"""
    for run in para.runs:
        if run.font.size:
            return round(run.font.size.pt, 1)
    return None


# ╔══════════════════════════════════════╗
# ║       1. 噪声过滤规则                 ║
# ╚══════════════════════════════════════╝
NOISE_PATTERNS = [
    re.compile(r'[仅供个人科研教学使用！!]{4,}'),
    re.compile(r'供个人科研教学'),
    re.compile(r'人科研教学使用'),
    re.compile(r'^\d{1,4}$'),
    re.compile(r'^[A-Z\s]{10,}$'),
    re.compile(r'^(出版人|策划编辑|责任编辑|责任美编|封面设计|版式设计|责任校对|责任印制|项目统筹)'),
    re.compile(r'^(ISBN|CIP|图书在版编目|中国版本图书馆)'),
    re.compile(r'^(定价|传\s*真|邮\s*编|网\s*址|市场部电话|编辑部电话|社\s*址)'),
    re.compile(r'^(出版发行|印\s*刷|经\s*销|制\s*作|开\s*本|印\s*张|字\s*数|印\s*次|版\s*次|印\s*数)'),
    re.compile(r'(教育科学出版社|北京师范大学出版|人民教育出版社|华东师范大学出版)'),
    re.compile(r'^[·\s]+[\u4e00-\u9fff\s]+[·\s]+$'),
    re.compile(r'^[\u4e00-\u9fff]\s{1,3}[\u4e00-\u9fff]\s{1,3}[\u4e00-\u9fff]?\s*$'),
    re.compile(r'如有印装质量问题'),
    re.compile(r'到所购图书销售'),
    re.compile(r'^([A-Z]{2,}\s+){3,}'),
    re.compile(r'教育家[书書]院丛书'),
    re.compile(r'(出版人|策划编辑).*(责任编辑|项目统筹)'),
    re.compile(r'^[\u4e00-\u9fff]{1,5}(\s+[\u4e00-\u9fff]{1,5}){1,5}\s*$'),
    re.compile(r'更多教学好书请加微信'),
    re.compile(r'扫码关注'),
    re.compile(r'版权所有\s*[，,]?\s*翻印必究'),
    re.compile(r'未经许可.{0,10}不得'),
    re.compile(r'保留所有权利'),
    # 页眉：单独一行的书名重复（正文内容中的）
    re.compile(r'^低头找幸福\s*$'),
    re.compile(r'^俞正强\s*$'),
    # 丛书编委会
    re.compile(r'^名师成长轨迹访谈录\s+丛书编委会\s*$'),
    re.compile(r'^学术顾问[：:]\s*顾明远'),
    re.compile(r'^主\s+任[：:]\s*张斌贤'),
    re.compile(r'^委\s+员\s*[（\(]按音序排列[）\)]'),
    re.compile(r'^丛立新\s*郭华\s*楼世洲'),
]

PUBLISHER_TABLE_KW = {'出版发行', '社址', '社   址', '出版 发行', '印刷', '经销', '制作'}


def is_noise(text):
    t = text.strip()
    if not t:
        return True
    return any(p.search(t) for p in NOISE_PATTERNS)


# ╔══════════════════════════════════════╗
# ║       2. 文本修复                     ║
# ╚══════════════════════════════════════╝
def _is_spaced_chinese(text):
    chinese = re.findall(r'[\u4e00-\u9fff]', text)
    if len(chinese) < 4:
        return False
    ratio = len(chinese) / max(len(text.replace(' ', '')), 1)
    spaced = re.findall(r'[\u4e00-\u9fff] [\u4e00-\u9fff]', text)
    return ratio > 0.5 and len(spaced) >= 2


def fix_text(text):
    t = text.strip()
    t = re.sub(r'\s*[\|｜]\s*\d{1,4}\s*$', '', t)
    if _is_spaced_chinese(t):
        t = re.sub(r'(?<=[\u4e00-\u9fff，。！？、『』【】…])\s+(?=[\u4e00-\u9fff，。！？、『』【】…])', '', t)
    t = re.sub(r'[ \t]{2,}', ' ', t)
    if re.search(r'[\u4e00-\u9fff]', t):
        t = t.replace(',', '，')
        t = t.replace('?', '？')
        t = t.replace('!', '！')
        t = t.replace('(', '（').replace(')', '）')
    return t


# ╔══════════════════════════════════════╗
# ║       3. 标题检测（字号优先）          ║
# ╚══════════════════════════════════════╝
# 文本正则作为补充（无字号时使用）
H1_PAT   = re.compile(r'^[一二三四五六七八九十]+[、.．]\s*.{2,30}$')
H3_PAT   = re.compile(r'^[（\(][一二三四五六七八九\d]+[）\)]\s*.+$')


def detect_heading(text, font_size):
    """返回 (markdown前缀, 清洁文本)"""
    t = text.strip()

    # 优先：字号映射
    if font_size and font_size in SIZE_TO_HEADING:
        level = SIZE_TO_HEADING[font_size]
        return '#' * level + ' ', t

    # 次优：文本正则
    if H1_PAT.match(t):
        return '## ', t
    if H3_PAT.match(t):
        return '#### ', t
    if t.startswith('——') or t.startswith('— —'):
        return '> ', t
    if t.startswith('—') and len(t) < 40:
        return '> ', t

    return '', t


# ╔══════════════════════════════════════╗
# ║       4. 表格转 Markdown              ║
# ╚══════════════════════════════════════╝
def table_to_md(table):
    rows = []
    for row in table.rows:
        cells = [c.text.strip().replace('\n', ' ') for c in row.cells]
        rows.append(cells)
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        return ''
    first_cell = rows[0][0] if rows[0] else ''
    if any(kw in first_cell for kw in PUBLISHER_TABLE_KW):
        return ''
    all_text = [c for r in rows for c in r if c.strip()]
    if len(all_text) < 3:
        return ''
    col_count = max(len(r) for r in rows)
    md_rows = []
    for row in rows:
        while len(row) < col_count:
            row.append('')
        md_rows.append('| ' + ' | '.join(row) + ' |')
    sep = '| ' + ' | '.join(['---'] * col_count) + ' |'
    return '\n'.join([md_rows[0], sep] + md_rows[1:])


# ╔══════════════════════════════════════╗
# ║       5. 图片提取与分类               ║
# ╚══════════════════════════════════════╝
def extract_and_classify_images(docx_path, images_dir):
    os.makedirs(images_dir, exist_ok=True)
    rid_to_path = {}
    stats = {'deleted': 0, 'kept': 0, 'blank': 0}

    with zipfile.ZipFile(docx_path) as z:
        rels_file = 'word/_rels/document.xml.rels'
        if rels_file not in z.namelist():
            return {}, stats
        with z.open(rels_file) as f:
            rels_tree = etree.parse(f)
        for rel in rels_tree.findall('{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
            if 'image' not in rel.get('Type', '').lower():
                continue
            target = rel.get('Target', '')
            rid = rel.get('Id', '')
            src = f'word/{target}' if not target.startswith('/') else target.lstrip('/')
            if src in z.namelist():
                ext = Path(target).suffix.lower()
                dst = os.path.join(images_dir, f'{rid}{ext}')
                with z.open(src) as img_src, open(dst, 'wb') as out:
                    out.write(img_src.read())
                rid_to_path[rid] = dst

    rid_to_md = {}
    try:
        from PIL import Image
        has_pil = True
    except ImportError:
        has_pil = False

    for rid, path in rid_to_path.items():
        fname = os.path.basename(path)
        rel_path = f'images/{fname}'

        if not has_pil:
            rid_to_md[rid] = f'\n![图片]({rel_path})\n'
            stats['kept'] += 1
            continue

        try:
            img = Image.open(path)
            w, h = img.size
            area = w * h
            ratio = max(w, h) / max(min(w, h), 1)

            if area < SMALL_AREA:
                img.close(); os.remove(path); stats['deleted'] += 1; continue
            if ratio > 8:
                img.close(); os.remove(path); stats['deleted'] += 1; continue

            gray = img.convert('L')
            pixels = list(gray.getdata())
            avg = sum(pixels) / len(pixels)
            img.close()

            if avg > WHITE_THRESH:
                os.remove(path); stats['blank'] += 1; continue
            if avg < 10 and area < 50000:
                os.remove(path); stats['deleted'] += 1; continue

            rid_to_md[rid] = f'\n![图片]({rel_path})\n'
            stats['kept'] += 1
        except Exception:
            if os.path.exists(path):
                os.remove(path)
            stats['deleted'] += 1

    return rid_to_md, stats


def get_para_image_rids(para_elem):
    rids = []
    for blip in para_elem.iter(A_BLIP):
        rid = blip.get(R_EMBED) or blip.get(R_ID)
        if rid:
            rids.append(rid)
    for imgdata in para_elem.iter(VML_IMG):
        rid = imgdata.get(R_ID) or imgdata.get(R_EMBED)
        if rid:
            rids.append(rid)
    return rids


# ╔══════════════════════════════════════╗
# ║       6. 主处理流程                   ║
# ╚══════════════════════════════════════╝
def convert():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print('步骤 1/4：提取并分类图片...')
    rid_to_md, img_stats = extract_and_classify_images(INPUT, IMG_DIR)
    print(f'  保留: {img_stats["kept"]}  删除(碎片): {img_stats["deleted"]}  删除(空白): {img_stats["blank"]}')

    print('步骤 2/4：提取文本并清洗（字号优先识别标题）...')
    doc = Document(INPUT)
    body = doc.element.body
    lines = []
    prev_line = ''
    seen_lines = set()

    for child in body:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

        if tag == 'p':
            para = Paragraph(child, doc)
            raw = para.text
            font_size = get_para_font_size(para)

            # 字号确认为页眉/页脚碎片 → 直接跳过（但保留图片）
            if font_size and font_size in NOISE_FONT_SIZES:
                img_rids = get_para_image_rids(child)
                for rid in img_rids:
                    if rid in rid_to_md:
                        lines.append(rid_to_md[rid])
                continue

            if is_noise(raw):
                img_rids = get_para_image_rids(child)
                for rid in img_rids:
                    if rid in rid_to_md:
                        lines.append(rid_to_md[rid])
                continue

            text = fix_text(raw)
            if not text:
                continue
            if is_noise(text):
                continue

            text_key = text.strip().lower()
            if text_key in seen_lines and len(text_key) > 10:
                continue
            seen_lines.add(text_key)

            prefix, text = detect_heading(text, font_size)
            line = prefix + text

            if line == prev_line:
                continue

            lines.append(line)
            prev_line = line

            img_rids = get_para_image_rids(child)
            for rid in img_rids:
                if rid in rid_to_md:
                    lines.append(rid_to_md[rid])

        elif tag == 'tbl':
            table = Table(child, doc)
            md_table = table_to_md(table)
            if md_table:
                lines.append('')
                lines.append(md_table)
                lines.append('')
                prev_line = ''

    print('步骤 3/4：后处理...')
    output_lines = []
    blank_count = 0
    for line in lines:
        if line.strip() == '':
            blank_count += 1
            if blank_count <= 1:
                output_lines.append('')
        else:
            blank_count = 0
            output_lines.append(line)

    header = "# 低头找幸福\n\n**作者：俞正强**\n\n---\n"
    content = header + '\n'.join(output_lines).strip() + '\n'

    print('步骤 4/4：写入文件...')
    OUT_MD.write_text(content, encoding='utf-8')

    h1 = sum(1 for l in output_lines if l.startswith('# ') and not l.startswith('## '))
    h2 = sum(1 for l in output_lines if l.startswith('## '))
    h3 = sum(1 for l in output_lines if l.startswith('### '))
    h4 = sum(1 for l in output_lines if l.startswith('#### '))
    img_refs = sum(1 for l in output_lines if '![图片]' in l)
    tbl_lines = sum(1 for l in output_lines if l.startswith('|'))

    print(f'\n{"="*50}')
    print('数据清洗报告')
    print(f'{"="*50}')
    print(f'输入段落数:    {len(doc.paragraphs)}')
    print(f'输出行数:      {len(output_lines)}')
    print(f'## 章节:       {h2}')
    print(f'### 小节:      {h3}')
    print(f'#### 子节:     {h4}')
    print(f'图片引用:      {img_refs}')
    print(f'表格行数:      {tbl_lines}')
    print(f'图片保留:      {img_stats["kept"]}')
    print(f'图片删除:      {img_stats["deleted"] + img_stats["blank"]}')
    print(f'输出文件:      {OUT_MD}')
    print(f'图片目录:      {IMG_DIR}')


if __name__ == '__main__':
    if not INPUT.exists():
        print(f'输入文件不存在: {INPUT}')
        sys.exit(1)
    convert()
