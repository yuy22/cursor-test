"""
低分辨率图片处理
================
1. 导出55张低分辨率图片到独立文件夹
2. 生成人工审查清单（含PDF页码、MD行号、当前描述）
3. 更新MD中的alt text为"图片模糊"提示
"""

import json
import math
import re
import shutil
from pathlib import Path

# =========================================================================
#  路 径
# =========================================================================

BASE = Path(r"C:\Users\b886855456ly\Desktop\Claude结果")
BOOK2_DIR = BASE / "images" / "book2"
STATE_FILE = BASE / "images" / "descriptions.json"
MD_PATH = BASE / "四年级+整合与拓展_RAG优化.md"
PDF_PATH = Path(r"E:\四下资料\pdf\四年级+整合与拓展(OCR).pdf")

# 输出
EXPORT_DIR = BASE / "images" / "低分辨率_待人工审查"
CHECKLIST_PATH = EXPORT_DIR / "人工审查清单.md"

# =========================================================================
#  加 载
# =========================================================================

state = json.load(open(STATE_FILE, encoding="utf-8"))
md_text = MD_PATH.read_text(encoding="utf-8")
md_lines = md_text.splitlines()

# =========================================================================
#  收 集 低 分 辨 率 非 装 饰 图
# =========================================================================

low_res = {}
for url, entry in state["book2"].items():
    q = entry.get("quality", "").strip()
    cat = entry.get("category", "").strip()
    desc = entry.get("description", "")
    if q != "low_res":
        continue
    if "decorative" in cat or desc.startswith("装饰图"):
        continue
    fname = entry.get("filename", "")
    low_res[fname] = {"url": url, "entry": entry}

# 找 MD 行号 + 章节
for i, line in enumerate(md_lines):
    for fname in low_res:
        if fname in line:
            low_res[fname]["md_line"] = i + 1
            # 往上找章节
            for j in range(i, max(0, i - 50), -1):
                l = md_lines[j]
                if l.startswith("###") and not l.startswith("######"):
                    low_res[fname]["section"] = l.lstrip("#").strip()[:80]
                    break
                elif l.startswith(">") and ">" in l[1:]:
                    parts = l.split(">")
                    low_res[fname]["section"] = parts[-1].strip()[:80]
                    break

# =========================================================================
#  推 算 PDF 页 码
# =========================================================================
# 目录结构: 前言=1页, 目录≈5页, 上部起始≈第7页
# 每个课例约4-6页
# 用MD行号占比推算: line / total_lines * total_pages

TOTAL_LINES = len(md_lines)
TOTAL_PAGES = 262

for fname, info in low_res.items():
    ml = info.get("md_line", 0)
    if ml > 0:
        estimated_page = max(1, math.ceil(ml / TOTAL_LINES * TOTAL_PAGES))
        info["est_page"] = estimated_page

# =========================================================================
#  导 出 图 片
# =========================================================================

EXPORT_DIR.mkdir(parents=True, exist_ok=True)

exported = 0
for fname in sorted(low_res.keys()):
    src = BOOK2_DIR / fname
    if src.exists():
        shutil.copy2(src, EXPORT_DIR / fname)
        exported += 1

print(f"已导出 {exported} 张图片到: {EXPORT_DIR}")

# =========================================================================
#  从 PDF 提 取 对 应 页 面 截 图
# =========================================================================

import fitz

doc = fitz.open(str(PDF_PATH))
rendered_pages = set()

for fname in sorted(low_res.keys()):
    info = low_res[fname]
    est_page = info.get("est_page", 0)
    if est_page < 1 or est_page > doc.page_count or est_page in rendered_pages:
        continue

    page = doc[est_page - 1]
    mat = fitz.Matrix(150 / 72, 150 / 72)
    pix = page.get_pixmap(matrix=mat)
    pix.save(str(EXPORT_DIR / f"PDF_第{est_page}页.png"))
    rendered_pages.add(est_page)

doc.close()
print(f"PDF 对应页面截图已导出: {len(rendered_pages)} 页")

# =========================================================================
#  生 成 审 查 清 单
# =========================================================================

lines_out = []
lines_out.append("# 低分辨率图片 — 人工审查清单\n")
lines_out.append(f"> 共 {len(low_res)} 张图片需要您填写描述")
lines_out.append(f"> 图片文件在本文件夹中，PDF对应页面截图也在\n")
lines_out.append("## 使用方法\n")
lines_out.append("1. 打开本文件夹中的图片文件（book2_xxx.jpg）")
lines_out.append("2. 对照同文件夹中的 PDF 页面截图（PDF_pXXX_book2_xxx.png）看上下文")
lines_out.append("3. 在每张图片下方的【您的描述】处填写正确的图片描述")
lines_out.append("4. 填完后把这个文件给我，我自动回写到MD中\n")
lines_out.append("---\n")

for idx, fname in enumerate(sorted(low_res.keys()), 1):
    info = low_res[fname]
    entry = info["entry"]
    ml = info.get("md_line", "?")
    section = info.get("section", "未知章节")
    est_page = info.get("est_page", "?")
    desc = entry.get("description", "")
    cat = entry.get("category", "")

    lines_out.append(f"### {idx}. {fname}")
    lines_out.append(f"- **MD行号**: {ml}")
    lines_out.append(f"- **所在章节**: {section}")
    lines_out.append(f"- **PDF估计页码**: 第{est_page}页")
    lines_out.append(f"- **分类**: {cat}")
    lines_out.append(f"- **当前AI描述**: {desc[:200]}")
    lines_out.append(f"- **PDF参考截图**: PDF_第{est_page}页.png")
    lines_out.append(f"\n**【您的描述】**: \n")
    lines_out.append("---\n")

CHECKLIST_PATH.write_text("\n".join(lines_out), encoding="utf-8")
print(f"审查清单已生成: {CHECKLIST_PATH}")

# =========================================================================
#  更 新 MD：低 分 辨 率 图 片 alt text
# =========================================================================

updated = 0
for fname, info in low_res.items():
    entry = info["entry"]
    local_path = entry.get("local_path", "")
    est_page = info.get("est_page", "?")

    if not local_path:
        continue

    # 匹配 ![任意alt](这张图的路径)
    escaped_path = re.escape(local_path)
    pattern = re.compile(r"!\[[^\]]*\]\(" + escaped_path + r"\)")

    new_alt = f"【图片模糊，请参看原PDF第{est_page}页】"
    replacement = f"![{new_alt}]({local_path})"

    new_text, n = pattern.subn(lambda _: replacement, md_text)
    if n > 0:
        md_text = new_text
        updated += n

MD_PATH.write_text(md_text, encoding="utf-8")
print(f"MD已更新: {updated} 处 alt text 改为图片模糊提示")

# =========================================================================
#  汇 总
# =========================================================================

print(f"\n{'=' * 50}")
print(f"  导出图片: {exported} 张")
print(f"  审查清单: {CHECKLIST_PATH}")
print(f"  MD更新:   {updated} 处")
print(f"  输出目录: {EXPORT_DIR}")
print(f"{'=' * 50}")
