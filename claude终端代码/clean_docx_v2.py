# -*- coding: utf-8 -*-
"""
种子课 DOCX → Markdown 数据清洗 v2
基于 clean_docx.py 文本规则 + docx_to_md.py 图片能力 + 讨论改进
改进点：图片提取分类、格式标准化、去重
"""
import sys, re, os, zipfile
sys.stdout.reconfigure(encoding='utf-8')
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table
from pathlib import Path
from lxml import etree

# ╔══════════════════════════════════════╗
# ║            配置（跨平台）              ║
# ╚══════════════════════════════════════╝
_base = Path(os.environ.get("MATH_TOOLKIT_BASE", str(Path.cwd())))
INPUT = _base / "input" / "俞正强种子课      一个数学特级教师的思与行.docx"
if not INPUT.exists():
    INPUT = _base / "俞正强种子课      一个数学特级教师的思与行.docx"
OUT_DIR = _base / "output" / "种子课_cleaned_v2"
OUT_MD = OUT_DIR / "俞正强种子课_cleaned.md"
IMG_DIR = OUT_DIR / "images"

# 图片分类阈值
TINY_AREA   = 2000    # <2000px² 直接删（1px线条、点）
SMALL_AREA  = 5000    # <5000px² 大概率碎片，跳过
WHITE_THRESH = 240    # 平均亮度>240 判定为空白扫描页

# XML 命名空间
REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
A_BLIP = '{http://schemas.openxmlformats.org/drawingml/2006/main}blip'
VML_IMG = '{urn:schemas-microsoft-com:vml}imagedata'
R_EMBED = f'{{{REL_NS}}}embed'
R_ID    = f'{{{REL_NS}}}id'

# ╔══════════════════════════════════════╗
# ║       1. 噪声过滤规则                ║
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
    re.compile(r'(教育科学出版社|北京师范大学出版|人民教育出版社)'),
    re.compile(r'^[IⅠⅡⅢ\u2160-\u2169][\.\s·①②]'),
    re.compile(r'^[·\s]+[\u4e00-\u9fff\s]+[·\s]+$'),
    re.compile(r'^[\u4e00-\u9fff]\s{1,3}[\u4e00-\u9fff]\s{1,3}[\u4e00-\u9fff]?\s*$'),
    re.compile(r'如有印装质量问题'),
    re.compile(r'到所购图书销售'),
    re.compile(r'^([A-Z]{2,}\s+){3,}'),
    re.compile(r'教育家[书書]院丛书'),
    re.compile(r'(出版人|策划编辑).*(责任编辑|项目统筹)'),
    re.compile(r'^[\u4e00-\u9fff]{1,5}(\s+[\u4e00-\u9fff]{1,5}){1,5}\s*$'),
]

PUBLISHER_TABLE_KW = {'出版发行', '社址', '社   址', '出版 发行', '印刷', '经销', '制作'}


def is_noise(text):
    t = text.strip()
    if not t:
        return True
    return any(p.search(t) for p in NOISE_PATTERNS)


# ╔══════════════════════════════════════╗
# ║       2. 文本修复 + 格式标准化        ║
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
    # 去尾部页码
    t = re.sub(r'\s*[\|｜]\s*\d{1,4}\s*$', '', t)
    # 压缩 OCR 汉字间空格
    if _is_spaced_chinese(t):
        t = re.sub(r'(?<=[\u4e00-\u9fff，。！？、『』【】…])\s+(?=[\u4e00-\u9fff，。！？、『』【】…])', '', t)
    # 压缩多余空格
    t = re.sub(r'[ \t]{2,}', ' ', t)
    # 格式标准化：统一标点（半角→全角，中文语境）
    t = t.replace(',', '，') if re.search(r'[\u4e00-\u9fff]', t) else t
    t = t.replace('?', '？') if re.search(r'[\u4e00-\u9fff]', t) else t
    t = t.replace('!', '！') if re.search(r'[\u4e00-\u9fff]', t) else t
    t = t.replace('(', '（').replace(')', '）') if re.search(r'[\u4e00-\u9fff]', t) else t
    return t


# ╔══════════════════════════════════════╗
# ║       3. 标题检测                     ║
# ╚══════════════════════════════════════╝
H1_PAT = re.compile(r'^[一二三四五六七八九十]+[、.．]\s*.{2,30}$')
H2_SHORT = re.compile(r'^[·*＊\*]\s*(.+)$')
H3_PAT = re.compile(r'^[（\(][一二三四五六七八九\d]+[）\)]\s*.+$')


def detect_structure(text):
    t = text.strip()
    if H1_PAT.match(t):
        return '## ', t
    m = H2_SHORT.match(t)
    if m:
        inner = m.group(1).strip()
        if len(re.findall(r'[\u4e00-\u9fff]', inner)) >= 2:
            return '### ', inner
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
    """提取图片，分类，返回 {rId: img_md_text} 和统计"""
    os.makedirs(images_dir, exist_ok=True)
    rid_to_path = {}
    stats = {'deleted': 0, 'kept': 0, 'blank': 0}

    # 从 rels 文件建立 rId → 图片路径映射
    with zipfile.ZipFile(docx_path) as z:
        with z.open('word/_rels/document.xml.rels') as f:
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

    # 分类每张图片
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

            # 过滤1：面积太小（碎片、点）
            if area < SMALL_AREA:
                img.close()
                os.remove(path)
                stats['deleted'] += 1
                continue

            # 过滤2：极端长宽比（分隔线、边框线）
            if ratio > 8:
                img.close()
                os.remove(path)
                stats['deleted'] += 1
                continue

            # 过滤3：高亮度图（水印残片、空白扫描页）
            gray = img.convert('L')
            pixels = list(gray.getdata())
            avg_brightness = sum(pixels) / len(pixels)
            img.close()

            if avg_brightness > 230:
                os.remove(path)
                stats['blank'] += 1
                continue

            # 过滤4：纯黑小图（黑色装饰块）
            if avg_brightness < 10 and area < 50000:
                os.remove(path)
                stats['deleted'] += 1
                continue

            # 有内容的图片：保留
            rid_to_md[rid] = f'\n![图片]({rel_path})\n'
            stats['kept'] += 1
        except Exception as e:
            # 打开失败的直接删
            if os.path.exists(path):
                os.remove(path)
            stats['deleted'] += 1

    return rid_to_md, stats


def get_para_image_rids(para_elem):
    """从段落 XML 中提取所有图片的 rId"""
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
    os.makedirs(OUT_DIR, exist_ok=True)

    # 第一步：提取并分类图片
    print('步骤 1/4：提取并分类图片...')
    rid_to_md, img_stats = extract_and_classify_images(INPUT, IMG_DIR)
    print(f'  保留: {img_stats["kept"]}  删除(碎片): {img_stats["deleted"]}  删除(空白): {img_stats["blank"]}')

    # 第二步：打开文档，遍历内容
    print('步骤 2/4：提取文本并清洗...')
    doc = Document(INPUT)
    body = doc.element.body
    lines = []
    prev_line = ''
    seen_lines = set()  # 去重用

    for child in body:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

        if tag == 'p':
            para = Paragraph(child, doc)
            raw = para.text

            # 噪声过滤
            if is_noise(raw):
                # 即使文字是噪声，也检查是否有有价值的图片
                img_rids = get_para_image_rids(child)
                for rid in img_rids:
                    if rid in rid_to_md:
                        lines.append(rid_to_md[rid])
                continue

            # 文本修复 + 标准化
            text = fix_text(raw)
            if not text:
                continue
            # 二次噪声检测
            if is_noise(text):
                continue

            # 去重
            text_key = text.strip().lower()
            if text_key in seen_lines and len(text_key) > 10:
                continue
            seen_lines.add(text_key)

            # 结构识别
            prefix, text = detect_structure(text)
            line = prefix + text

            # 避免连续重复行
            if line == prev_line:
                continue

            lines.append(line)
            prev_line = line

            # 段落中的图片（文字之后）
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

    # 第三步：后处理
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

    # 添加文档标题
    header = "# 种子课——一个数学特级教师的思与行\n\n**作者：俞正强**\n\n---\n"
    content = header + '\n'.join(output_lines).strip() + '\n'

    # 第四步：写入文件
    print('步骤 4/4：写入文件...')
    Path(OUT_MD).write_text(content, encoding='utf-8')

    # 统计
    h2 = sum(1 for l in output_lines if l.startswith('## '))
    h3 = sum(1 for l in output_lines if l.startswith('### '))
    h4 = sum(1 for l in output_lines if l.startswith('#### '))
    img_refs = sum(1 for l in output_lines if '![图片]' in l)
    tbl_lines = sum(1 for l in output_lines if l.startswith('|'))

    print(f'\n{"="*50}')
    print(f'数据清洗报告')
    print(f'{"="*50}')
    print(f'输入段落数:    {len(doc.paragraphs)}')
    print(f'输出行数:      {len(output_lines)}')
    print(f'章节(##):      {h2}')
    print(f'小节(###):     {h3}')
    print(f'子节(####):    {h4}')
    print(f'图片引用:      {img_refs}')
    print(f'表格行数:      {tbl_lines}')
    print(f'图片保留:      {img_stats["kept"]}')
    print(f'图片删除:      {img_stats["deleted"] + img_stats["blank"]}')
    print(f'输出文件:      {OUT_MD}')
    print(f'图片目录:      {IMG_DIR}')


if __name__ == '__main__':
    if not INPUT.exists():
        print(f"输入文件不存在: {INPUT}")
        sys.exit(1)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    convert()
