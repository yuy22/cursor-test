"""
OCR 公式乱码清洗
================
修复 TextIn OCR 产出的数学符号乱码：
  1. ∘ (U+2218 环运算符) → ° (U+00B0 度号)
  2. ∘° 双符号 → °
  3. 特定已知乱码公式修复
  4. 温度 ∘C → °C
  5. 报告无法自动修复的可疑内容
"""

import os
import re
import sys
from pathlib import Path

_base = Path(os.environ.get("MATH_TOOLKIT_BASE", str(Path.cwd())))
MD_PATH = _base / "四年级+整合与拓展_RAG优化.md"
if not MD_PATH.exists():
    MD_PATH = _base / "input" / "四年级+整合与拓展_RAG优化.md"

def main():
    dry_run = "--dry-run" in sys.argv
    text = MD_PATH.read_text(encoding="utf-8")
    original = text
    fixes = []

    # =====================================================================
    #  规则 1：∘° → °（双符号，先处理）
    # =====================================================================
    count = text.count("∘°")
    if count:
        text = text.replace("∘°", "°")
        fixes.append(f"∘° → °: {count} 处")

    # =====================================================================
    #  规则 2：∘C → °C（温度）
    # =====================================================================
    count = text.count("∘C")
    if count:
        text = text.replace("∘C", "°C")
        fixes.append(f"∘C → °C: {count} 处")

    # =====================================================================
    #  规则 3：数字∘ → 数字°（角度，核心修复）
    #  匹配：30∘  0∘  180∘  89.9∘  0.001∘
    # =====================================================================
    pattern = re.compile(r"(\d)∘")
    count = len(pattern.findall(text))
    if count:
        text = pattern.sub(r"\1°", text)
        fixes.append(f"数字∘ → 数字°: {count} 处")

    # =====================================================================
    #  规则 4：∠X=数字∘ 已被规则3处理，检查残留
    # =====================================================================

    # =====================================================================
    #  规则 5：特定已知乱码修复
    # =====================================================================

    # "1∘=1=5⋅1∘" → 这是OCR乱码，原意是 "5°=5×1°"
    # 但上下文是 "把圆平均分成360份，每一份所对的角的大小就是1°"
    # 乱码 "1∘=1=5⋅1∘" 紧跟在后面，应该是公式图片OCR失败
    old_garbled = "1°=1=5⋅1°"  # 规则3已把∘换成°
    if old_garbled in text:
        # 根据DOCX原文，这段只需要 "1°"，乱码部分直接删除
        text = text.replace(old_garbled, "1°")
        fixes.append(f"乱码公式 '1°=1=5⋅1°' → '1°': 1 处")

    # "演示1180°" → "演示: 180°"（多了个1）
    if "演示1180°" in text:
        text = text.replace("演示1180°", "演示：180°")
        fixes.append(f"'演示1180°' → '演示：180°': 1 处")

    # /∘C → /°C（统计图轴标签）
    if "/∘" in text:
        count = text.count("/∘")
        text = text.replace("/∘", "/°")
        fixes.append(f"/∘ → /°: {count} 处")

    # =====================================================================
    #  规则 6：清理残留的孤立 ∘
    # =====================================================================
    remaining = text.count("∘")
    if remaining:
        fixes.append(f"残留 ∘ 符号: {remaining} 处（未自动修复，需人工审查）")

    # =====================================================================
    #  规则 7：⋅ (点乘号) 检查
    # =====================================================================
    dot_count = text.count("⋅")
    if dot_count:
        fixes.append(f"残留 ⋅ (点乘号): {dot_count} 处")

    # =====================================================================
    #  统 计
    # =====================================================================
    total_changed = sum(c != o for c, o in zip(text, original))

    print(f"{'[DRY-RUN] ' if dry_run else ''}OCR 公式清洗结果:")
    print(f"{'=' * 50}")
    for fix in fixes:
        print(f"  {fix}")
    print(f"{'=' * 50}")

    if not dry_run and text != original:
        MD_PATH.write_text(text, encoding="utf-8")
        print(f"已保存到: {MD_PATH}")
    elif dry_run:
        print("未写入文件，去掉 --dry-run 执行")

if __name__ == "__main__":
    main()
