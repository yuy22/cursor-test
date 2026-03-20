"""
王永春一本通 - 批量图片描述 + 审查文档生成
用法: python add_image_descriptions.py [--dry-run]
"""
import argparse
import json
import re
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MD_FILE = BASE_DIR / "王永春一本通_cleaned.md"
REVIEW_FILE = BASE_DIR / "图片审查.md"
KNOWN_JSON = Path("/tmp/known_descriptions.json")
ANALYSIS_JSON = Path("/tmp/image_analysis.json")

RE_PENDING = re.compile(r"^\[待描述图片\]$")
RE_IMG_LINE = re.compile(r"^!\[(?:[^\]]*)\]\((images/rId\d+\.(?:jpeg|jpg|png))\)$")
RE_HEADING = re.compile(r"^#{1,4}\s+.+")


def find_heading(lines, idx):
    for i in range(idx - 1, max(-1, idx - 200), -1):
        if RE_HEADING.match(lines[i].strip()):
            return lines[i].strip()
    return ""


def get_context(lines, ph_idx, img_idx):
    heading = find_heading(lines, ph_idx)
    before, after = [], []
    for k in range(ph_idx - 1, max(-1, ph_idx - 40), -1):
        ln = lines[k].strip()
        if not ln or RE_PENDING.match(ln) or RE_IMG_LINE.match(ln): continue
        before.insert(0, ln)
        if len(before) >= 5: break
    for k in range(img_idx, min(len(lines), img_idx + 40)):
        ln = lines[k].strip()
        if not ln or RE_PENDING.match(ln) or RE_IMG_LINE.match(ln): continue
        after.append(ln)
        if len(after) >= 5: break
    return heading, "\n".join(before), "\n".join(after)


def template_desc(img_path, analysis, heading, before, after):
    """为未人工核实的图片生成诚实的模板描述"""
    info = analysis.get(img_path, {})
    img_type = info.get("type", "unknown")
    w = info.get("w", 0)
    h = info.get("h", 0)
    brightness = info.get("brightness", 128.0)
    ctx = ((before + " " + after).strip())[:120]
    hdg = heading.lstrip("#").strip()[:35]

    if img_type == "blank":
        return (
            f"【待人工审查】扫描区域近白（亮度{brightness:.0f}/255），未见有效内容，"
            f"可能是版面空白区、分隔页或OCR空白段。章节：{hdg}。",
            "decorative", "clear", True
        )
    if img_type == "thin_strip":
        if brightness < 80:
            hint = "深色细长条带"
        elif brightness > 220:
            hint = "浅色/白色细长条带"
        else:
            hint = "彩色细长条带（疑为装饰分隔条）"
        return (
            f"【待人工审查】{hint}（{w}x{h}像素）。章节：{hdg}。",
            "decorative", "clear", True
        )
    if img_type == "tiny":
        if brightness < 30:
            hint = "极深色小图，疑为实心圆点/黑色符号"
        elif brightness > 240:
            hint = "近白色极小图，疑为空白填写框碎片"
        else:
            hint = f"小型图片碎片（亮度{brightness:.0f}），疑为装饰图标或数学符号"
        return (
            f"【待人工审查】{hint}（{w}x{h}像素）。章节：{hdg}。",
            "decorative", "clear", True
        )
    if img_type == "small":
        if brightness < 50:
            hint = "深色图案（可能为实心图标、深色符号或深色实物图片）"
        elif brightness > 230:
            hint = "浅色图形（可能为几何图形线框、空白方格或浅色插图）"
        else:
            hint = "彩色图片（可能为插图、实物照片或数学图形）"
        ctx_hint = f"上下文：「{ctx}」" if ctx else ""
        return (
            f"【待人工审查】小图（{w}x{h}像素），{hint}。"
            f"章节：{hdg}。{ctx_hint}",
            "illustration", "low_res", True
        )
    # medium / large / unknown
    if brightness < 50:
        hint = "深色图片（照片/深色图标）"
    elif brightness > 230:
        hint = "浅色图形（线框图/空白填写区）"
    else:
        hint = "彩色图片（插图/实物照片/数学图形）"
    ctx_hint = f"上下文：「{ctx}」" if ctx else ""
    return (
        f"【待人工审查】{hint}（{w}x{h}像素）。"
        f"章节：{hdg}。{ctx_hint}",
        "illustration", "low_res", True
    )


def main(dry_run=False):
    lines = MD_FILE.read_text(encoding="utf-8").splitlines()
    known = json.loads(KNOWN_JSON.read_text(encoding="utf-8")) if KNOWN_JSON.exists() else {}
    analysis = json.loads(ANALYSIS_JSON.read_text(encoding="utf-8")).get("results", {}) if ANALYSIS_JSON.exists() else {}

    print(f"已知描述: {len(known)} 条  |  PIL分析: {len(analysis)} 条")

    # 收集所有待处理项
    tasks = []
    i = 0
    while i < len(lines):
        if RE_PENDING.match(lines[i].strip()):
            for j in range(i + 1, min(i + 3, len(lines))):
                m = RE_IMG_LINE.match(lines[j].strip())
                if m:
                    tasks.append((i, j, m.group(1)))
                    break
        i += 1
    print(f"待处理图片: {len(tasks)} 张")

    # 生成描述
    results = {}
    review_items = []
    for ph_idx, img_idx, img_path in tasks:
        heading, before, after = get_context(lines, ph_idx, img_idx)
        if img_path in known:
            entry = known[img_path]
            desc = entry["description"]
            cat = entry.get("category", "illustration")
            qual = entry.get("quality", "clear")
            needs_review = "【待人工审查】" in desc
        else:
            desc, cat, qual, needs_review = template_desc(img_path, analysis, heading, before, after)
        results[img_path] = desc
        if needs_review:
            review_items.append({
                "path": img_path,
                "type": analysis.get(img_path, {}).get("type", "unknown"),
                "w": analysis.get(img_path, {}).get("w", 0),
                "h": analysis.get(img_path, {}).get("h", 0),
                "brightness": analysis.get(img_path, {}).get("brightness", 0),
                "heading": heading, "before": before[:80], "after": after[:80],
                "desc": desc, "ph_line": ph_idx + 1,
            })

    known_count = sum(1 for p, _ in [(p, d) for p, d in results.items() if p in known])
    template_count = len(results) - known_count
    print(f"  已知描述: {known_count} | 模板描述: {template_count} | 待审查: {len(review_items)}")

    if dry_run:
        print("\n[DRY RUN] 前5条预览：")
        for img_path, desc in list(results.items())[:5]:
            print(f"  {img_path}:\n    {desc[:100]}...")
        return

    # 更新 MD（从后往前）
    new_lines = lines[:]
    done = 0
    for ph_idx, img_idx, img_path in reversed(tasks):
        if img_path in results:
            new_lines[ph_idx] = f"[图片描述：{results[img_path]}]"
            done += 1
    MD_FILE.write_text("\n".join(new_lines), encoding="utf-8")
    remaining = sum(1 for l in new_lines if "[待描述图片]" in l)
    print(f"✅ MD 更新完成：替换 {done} 条，剩余占位符 {remaining} 个")

    # 生成审查文档
    write_review(review_items)


def write_review(items):
    by_type = {}
    for item in items:
        by_type.setdefault(item["type"], []).append(item)

    total_counts = {
        t: len(by_type.get(t, [])) for t in
        ["medium", "large", "small", "blank", "thin_strip", "tiny", "unknown"]
    }

    out = [
        "# 王永春一本通 — 图片审查清单",
        "",
        f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M')}  总待审查：{len(items)} 张",
        "",
        "## 使用说明",
        "",
        "1. 每条图片都附有当前描述和所在章节位置",
        "2. 如果描述准确，不需要做任何操作",
        "3. 如果描述不准确，在【您的修改】处填写正确描述，告知 AI 统一回写",
        "4. 如果图片确实没有教学内容，可标注「可删除」",
        "",
        "## 分类统计",
        "",
        "| 分类 | 数量 | 说明 |",
        "|------|:----:|------|",
        f"| medium（中图） | {total_counts.get('medium', 0)} | 有可能有数学内容，需确认 |",
        f"| large（大图） | {total_counts.get('large', 0)} | 明确标待审查的大图 |",
        f"| small（小图） | {total_counts.get('small', 0)} | 面积<30000px²，内容待确认 |",
        f"| blank（扫描空白） | {total_counts.get('blank', 0)} | 亮度>240，近白 |",
        f"| thin_strip（细条） | {total_counts.get('thin_strip', 0)} | 宽高比>10:1，装饰条带 |",
        f"| tiny（极小碎片） | {total_counts.get('tiny', 0)} | 面积<3000px²，可能是OCR碎片 |",
        f"| **合计** | **{len(items)}** | |",
        "",
        "---",
        "",
    ]

    for type_name, type_label in [
        ("medium", "中图（需确认内容）"),
        ("large", "大图（含【待人工审查】标记）"),
        ("small", "小图"),
        ("blank", "扫描空白区域"),
        ("thin_strip", "细长装饰条"),
        ("tiny", "极小碎片"),
        ("unknown", "未分类"),
    ]:
        type_items = by_type.get(type_name, [])
        if not type_items:
            continue
        out += [f"## {type_label}（{len(type_items)} 张）", ""]
        for item in type_items:
            out += [
                f"### `{item['path']}` — 原文第{item['ph_line']}行",
                "",
                f"- 尺寸：{item['w']}×{item['h']}  亮度：{item['brightness']:.0f}",
                f"- 章节：{item['heading'].lstrip('#').strip()[:50]}",
                f"- 前文：{item['before'][:80].replace(chr(10), ' ')}",
                f"- 后文：{item['after'][:80].replace(chr(10), ' ')}",
                f"- 当前描述：{item['desc'][:200]}",
                f"- **【您的修改】**：",
                "",
            ]
        out += ["---", ""]

    REVIEW_FILE.write_text("\n".join(out), encoding="utf-8")
    print(f"✅ 审查文档已生成：{REVIEW_FILE}  ({len(items)} 条)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
