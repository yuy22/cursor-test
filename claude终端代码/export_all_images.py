# -*- coding: utf-8 -*-
"""
提取《低头找幸福》全部图片，按保留/删除原因分类，打包供人工审查
"""
import sys, zipfile, os, io
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from lxml import etree
from PIL import Image

DOCX      = Path(__file__).parent / "俞正强：低头找幸福(OCR).docx"
OUT_DIR   = Path(__file__).parent / "output" / "低头找幸福_图片审查"
ZIP_OUT   = Path(__file__).parent / "低头找幸福_图片审查.zip"

SMALL_AREA   = 5000
WHITE_THRESH = 230

# 从 docx 提取所有图片
with zipfile.ZipFile(DOCX) as z:
    with z.open('word/_rels/document.xml.rels') as f:
        rels_tree = etree.parse(f)
    imgs = {}
    for rel in rels_tree.findall(
            '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
        if 'image' not in rel.get('Type', '').lower():
            continue
        target = rel.get('Target', '')
        rid    = rel.get('Id', '')
        src    = f'word/{target}' if not target.startswith('/') else target.lstrip('/')
        if src in z.namelist():
            imgs[rid] = (target, z.open(src).read())

print(f'共提取 {len(imgs)} 张图片，开始分类...\n')

kept    = []   # (rid, fname, data, reason_detail)
deleted = []   # (rid, fname, data, reason, w, h, area, ratio, avg)

for rid, (target, data) in imgs.items():
    ext   = Path(target).suffix.lower()
    fname = f'{rid}{ext}'
    try:
        img  = Image.open(io.BytesIO(data))
        w, h = img.size
        area = w * h
        ratio = max(w, h) / max(min(w, h), 1)
        gray  = img.convert('L')
        pixels = list(gray.getdata())
        avg   = sum(pixels) / len(pixels)
        img.close()

        if area < SMALL_AREA:
            deleted.append((rid, fname, data, f'小碎片(面积{area}px²<5000)', w, h, area, round(ratio,1), round(avg,1)))
        elif ratio > 8:
            deleted.append((rid, fname, data, f'分隔线(长宽比{round(ratio,1)}>8)', w, h, area, round(ratio,1), round(avg,1)))
        elif avg > WHITE_THRESH:
            deleted.append((rid, fname, data, f'空白/水印(亮度{round(avg,1)}>230)', w, h, area, round(ratio,1), round(avg,1)))
        elif avg < 10 and area < 50000:
            deleted.append((rid, fname, data, f'纯黑装饰块(亮度{round(avg,1)}<10)', w, h, area, round(ratio,1), round(avg,1)))
        else:
            kept.append((rid, fname, data, f'{w}×{h}  亮度{round(avg,1)}'))
    except Exception as e:
        deleted.append((rid, fname, data, f'打开失败:{e}', 0, 0, 0, 0, 0))

print(f'保留: {len(kept)} 张')
print(f'删除: {len(deleted)} 张')

# ── 生成审查用 HTML 报告 ─────────────────────────────────────
html_rows_del = ''
for rid, fname, data, reason, w, h, area, ratio, avg in deleted:
    b64_tag = ''
    try:
        import base64
        ext = Path(fname).suffix.lower()
        mime = 'image/png' if ext == '.png' else 'image/jpeg'
        b64 = base64.b64encode(data).decode()
        b64_tag = f'<img src="data:{mime};base64,{b64}" style="max-width:120px;max-height:120px;border:1px solid #ccc">'
    except Exception:
        b64_tag = '(无法显示)'
    html_rows_del += f'<tr><td>{rid}</td><td>{b64_tag}</td><td>{w}×{h}</td><td style="color:red">{reason}</td></tr>\n'

html_rows_kept = ''
for rid, fname, data, detail in kept:
    b64_tag = ''
    try:
        import base64
        ext = Path(fname).suffix.lower()
        mime = 'image/png' if ext == '.png' else 'image/jpeg'
        b64 = base64.b64encode(data).decode()
        b64_tag = f'<img src="data:{mime};base64,{b64}" style="max-width:120px;max-height:120px;border:1px solid #ccc">'
    except Exception:
        b64_tag = '(无法显示)'
    html_rows_kept += f'<tr><td>{rid}</td><td>{b64_tag}</td><td style="color:green">{detail}</td></tr>\n'

html = f"""<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8">
<title>低头找幸福 图片审查报告</title>
<style>
body{{font-family:sans-serif;margin:20px}}
h2{{margin-top:30px}}
table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ddd;padding:6px;vertical-align:middle}}
th{{background:#f5f5f5}}
</style>
</head>
<body>
<h1>《低头找幸福》图片审查报告</h1>
<p>共 {len(imgs)} 张图片，<span style="color:green">保留 {len(kept)} 张</span>，<span style="color:red">删除 {len(deleted)} 张</span></p>

<h2>✅ 保留的 {len(kept)} 张图片</h2>
<table>
<tr><th>ID</th><th>预览</th><th>尺寸/亮度</th></tr>
{html_rows_kept}
</table>

<h2>🗑️ 删除的 {len(deleted)} 张图片（请逐一确认）</h2>
<table>
<tr><th>ID</th><th>预览</th><th>尺寸</th><th>删除原因</th></tr>
{html_rows_del}
</table>
</body></html>"""

# ── 打包 zip ────────────────────────────────────────────────
print('\n打包 zip...')
with zipfile.ZipFile(ZIP_OUT, 'w', zipfile.ZIP_DEFLATED) as zf:
    # HTML 审查报告（内嵌图片，单文件打开）
    zf.writestr('审查报告.html', html.encode('utf-8'))

    # 保留的图片
    for rid, fname, data, detail in kept:
        zf.writestr(f'01_保留({len(kept)}张)/{fname}', data)

    # 删除：按原因分子文件夹
    for rid, fname, data, reason, *_ in deleted:
        if '小碎片' in reason:
            folder = f'02_删除_小碎片'
        elif '分隔线' in reason:
            folder = f'03_删除_分隔线'
        elif '空白' in reason or '水印' in reason:
            folder = f'04_删除_空白水印'
        elif '纯黑' in reason:
            folder = f'05_删除_纯黑装饰'
        else:
            folder = f'06_删除_其他'
        zf.writestr(f'{folder}/{fname}', data)

print(f'\n完成！')
print(f'ZIP 文件：{ZIP_OUT}  ({ZIP_OUT.stat().st_size // 1024} KB)')
print(f'\n解压后打开 "审查报告.html"，所有图片内嵌在里面，浏览器直接查看。')
