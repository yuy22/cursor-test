# -*- coding: utf-8 -*-
"""
北师大版4年级数学下册教师用书 → Markdown 转换器
功能：文本提取 + 图片提取 + OCR + 内联图片嵌入
"""

import os
import re
import zipfile
import shutil
from pathlib import Path
from PIL import Image
import pytesseract
from docx import Document
from lxml import etree

# ============================================================
# 配置
# ============================================================
TESSERACT_CMD  = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
TESSDATA_DIR   = r'C:\Users\b886855456ly\tessdata'
SRC_DOCX       = r'C:\Users\b886855456ly\Desktop\四年级下册\word\北师大版4年级数学下册教师用书.docx'
OUT_DIR        = r'C:\Users\b886855456ly\Desktop\四年级下册\word\教师用书_md'
IMAGES_SUBDIR  = 'images'

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
os.environ['TESSDATA_PREFIX'] = TESSDATA_DIR

W_NS   = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
M_NS   = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
R_NS   = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

# ============================================================
# 图片提取
# ============================================================
def extract_images_from_docx(docx_path: str, images_dir: str) -> dict[str, str]:
    """解压 docx，提取所有图片到 images_dir，返回 {rId: 本地路径}"""
    os.makedirs(images_dir, exist_ok=True)
    rId_to_path = {}

    with zipfile.ZipFile(docx_path) as z:
        # 读取关系表
        with z.open('word/_rels/document.xml.rels') as f:
            rels_tree = etree.parse(f)

        for rel in rels_tree.findall('{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
            rtype = rel.get('Type', '')
            if 'image' not in rtype.lower():
                continue
            target = rel.get('Target', '')
            rid    = rel.get('Id', '')
            src    = f'word/{target}' if not target.startswith('/') else target.lstrip('/')
            ext    = Path(target).suffix.lower()

            if src in z.namelist():
                dst_name = f'{rid}{ext}'
                dst_path = os.path.join(images_dir, dst_name)
                with z.open(src) as img_file, open(dst_path, 'wb') as out:
                    out.write(img_file.read())
                rId_to_path[rid] = dst_path

    return rId_to_path


# ============================================================
# OCR 判断与识别
# ============================================================
def is_formula_image(img_path: str) -> bool:
    """
    判断是否为公式/符号小图（不是教学图）
    文档中图片普遍很小，用面积区分：
    - 面积 < 5000px²（约 70x70 以下）→ 公式/符号碎片
    - 面积 >= 5000px²              → 教学插图（OCR 嵌入原图）
    """
    try:
        with Image.open(img_path) as img:
            w, h = img.size
            return (w * h) < 5000
    except Exception:
        return False


def ocr_image(img_path: str) -> str:
    """对图片 OCR，返回识别文本；优先中文+英文，失败时返回空"""
    ext = Path(img_path).suffix.lower()
    # WMF/EMF 无法直接读取，跳过
    if ext in ('.wmf', '.emf'):
        return ''
    try:
        img = Image.open(img_path)
        # 放大小图提高识别率
        if img.width < 200:
            scale = 200 // img.width + 1
            img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)

        cfg = f'--psm 6 --tessdata-dir "{TESSDATA_DIR}"'
        lang = 'chi_sim+eng'
        try:
            text = pytesseract.image_to_string(img, lang=lang, config=cfg).strip()
        except Exception:
            text = pytesseract.image_to_string(img, lang='eng', config=f'--psm 6').strip()
        return text
    except Exception:
        return ''


def convert_wmf_to_png(wmf_path: str) -> str | None:
    """尝试用 Pillow 转换 WMF/EMF，失败返回 None"""
    try:
        png_path = wmf_path.rsplit('.', 1)[0] + '.png'
        img = Image.open(wmf_path)
        img.save(png_path)
        return png_path
    except Exception:
        return None


# ============================================================
# OMML 公式文本提取
# ============================================================
def extract_math_text(elem) -> str:
    """从 OMML 元素中提取数学文本"""
    texts = [t.text for t in elem.iter(f'{{{M_NS}}}t') if t.text]
    return ''.join(texts) or '[数学公式]'


# ============================================================
# 段落 → Markdown 行
# ============================================================
A_BLIP   = '{http://schemas.openxmlformats.org/drawingml/2006/main}blip'
VML_IMG  = '{urn:schemas-microsoft-com:vml}imagedata'
R_EMBED  = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed'
R_ID     = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def _extract_rid(elem) -> str:
    """从 blip 或 imagedata 元素提取 rId"""
    return elem.get(R_EMBED) or elem.get(R_ID) or ''


def _process_run(run_elem, rId_to_md: dict, parts: list):
    """处理 w:r，提取文本或图片（drawing 嵌套在 run 里）"""
    has_drawing = False
    for child in run_elem:
        local = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if local == 'drawing':
            has_drawing = True
            for blip in child.iter(A_BLIP):
                rid = _extract_rid(blip)
                if rid in rId_to_md:
                    parts.append(rId_to_md[rid])
                    break
        elif local == 'pict':
            has_drawing = True
            for imgdata in child.iter(VML_IMG):
                rid = _extract_rid(imgdata)
                if rid in rId_to_md:
                    parts.append(rId_to_md[rid])
                    break
    if not has_drawing:
        for t in run_elem.iter(f'{{{W_NS}}}t'):
            if t.text:
                parts.append(t.text)


def para_to_md(para, rId_to_md: dict[str, str]) -> str:
    """将 docx 段落转换为 Markdown 文本，内联图片引用"""
    parts = []
    for child in para._element:
        local = child.tag.split('}')[-1] if '}' in child.tag else child.tag

        if local == 'r':
            _process_run(child, rId_to_md, parts)

        elif local == 'hyperlink':
            for run in child:
                if run.tag.split('}')[-1] == 'r':
                    _process_run(run, rId_to_md, parts)

        elif local in ('oMath', 'oMathPara'):
            math_text = extract_math_text(child)
            parts.append(f'`{math_text}`')

        elif local == 'drawing':
            # drawing 直接挂在 w:p 下（少数情况）
            for blip in child.iter(A_BLIP):
                rid = _extract_rid(blip)
                if rid in rId_to_md:
                    parts.append(rId_to_md[rid])
                    break

        elif local == 'pict':
            for imgdata in child.iter(VML_IMG):
                rid = _extract_rid(imgdata)
                if rid in rId_to_md:
                    parts.append(rId_to_md[rid])
                    break

    text = ''.join(parts).strip()
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text


# ============================================================
# 标题级别判断
# ============================================================
def get_heading_level(para) -> int:
    """返回 1-6 表示标题级别，0 表示普通段落"""
    style_name = para.style.name if para.style else ''
    if 'Heading 1' in style_name or '标题 1' in style_name:
        return 1
    if 'Heading 2' in style_name or '标题 2' in style_name:
        return 2
    if 'Heading 3' in style_name or '标题 3' in style_name:
        return 3
    # 根据字体大小判断（pPr 中的 sz）
    outline = para._element.find(f'.//{{{W_NS}}}outlineLvl')
    if outline is not None:
        lvl = int(outline.get(f'{{{W_NS}}}val', '9'))
        if lvl < 6:
            return lvl + 1
    return 0


# ============================================================
# 主流程
# ============================================================
def table_to_md(table, rId_to_md: dict[str, str]) -> list[str]:
    """将表格转换为 Markdown 行（简化：逐行逐格输出）"""
    lines = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            cell_parts = []
            for para in cell.paragraphs:
                t = para_to_md(para, rId_to_md).strip()
                if t:
                    cell_parts.append(t)
            cells.append(' '.join(cell_parts))
        lines.append('| ' + ' | '.join(cells) + ' |')
    # 在标题行后插入分隔线
    if len(lines) > 1:
        lines.insert(1, '| ' + ' | '.join(['---'] * len(table.rows[0].cells)) + ' |')
    return lines


def convert(src: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    images_dir = os.path.join(out_dir, IMAGES_SUBDIR)

    print('Step 1/4: 提取图片...')
    rId_to_path = extract_images_from_docx(src, images_dir)
    print(f'  共提取 {len(rId_to_path)} 张图片')

    print('Step 2/4: OCR 识别图片...')
    rId_to_md: dict[str, str] = {}
    stats = {'formula': 0, 'diagram': 0, 'skipped': 0}

    for rid, img_path in rId_to_path.items():
        ext = Path(img_path).suffix.lower()
        rel_path = f'{IMAGES_SUBDIR}/{os.path.basename(img_path)}'

        if ext in ('.wmf', '.emf'):
            png_path = convert_wmf_to_png(img_path)
            if png_path:
                img_path = png_path
                rel_path = f'{IMAGES_SUBDIR}/{os.path.basename(png_path)}'
            else:
                rId_to_md[rid] = f'\n\n![公式图片]({rel_path})\n\n'
                stats['skipped'] += 1
                continue

        if is_formula_image(img_path):
            ocr_text = ocr_image(img_path)
            if ocr_text:
                # 单行公式用行内代码，多行用图片
                if '\n' not in ocr_text.strip():
                    rId_to_md[rid] = f' `{ocr_text.strip()}` '
                else:
                    rId_to_md[rid] = f'\n\n```\n{ocr_text.strip()}\n```\n\n'
                stats['formula'] += 1
            else:
                rId_to_md[rid] = f'![公式]({rel_path})'
                stats['skipped'] += 1
        else:
            rId_to_md[rid] = f'\n\n![教材插图]({rel_path})\n\n'
            stats['diagram'] += 1

    print(f'  公式识别: {stats["formula"]}  图表嵌入: {stats["diagram"]}  跳过: {stats["skipped"]}')

    print('Step 3/4: 转换文档...')
    doc = Document(src)
    md_lines = []
    prev_blank = 0

    # 按文档顺序处理段落和表格
    body = doc.element.body
    for child in body:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

        if tag == 'p':
            from docx.text.paragraph import Paragraph
            para = Paragraph(child, doc)
            text = para_to_md(para, rId_to_md)
            if not text:
                if prev_blank < 2:
                    md_lines.append('')
                    prev_blank += 1
                continue
            prev_blank = 0
            level = get_heading_level(para)
            if level > 0:
                md_lines.append(f'{"#" * level} {text}')
            else:
                md_lines.append(text)

        elif tag == 'tbl':
            from docx.table import Table
            table = Table(child, doc)
            if prev_blank < 1:
                md_lines.append('')
            md_lines.extend(table_to_md(table, rId_to_md))
            md_lines.append('')
            prev_blank = 1

    # 收尾：去首尾空行
    while md_lines and md_lines[0] == '':
        md_lines.pop(0)
    while md_lines and md_lines[-1] == '':
        md_lines.pop()

    out_md = os.path.join(out_dir, '北师大版4年级数学下册教师用书.md')
    with open(out_md, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))

    print(f'Step 4/4: 完成')
    print(f'  输出 MD: {out_md}')
    print(f'  图片目录: {images_dir}')
    print(f'  总行数: {len(md_lines)}')


if __name__ == '__main__':
    convert(SRC_DOCX, OUT_DIR)
