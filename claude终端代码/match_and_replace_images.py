"""
低分辨率图片匹配与替换
========================
从 DOCX 提取的清晰图片中，找到与 book2 低分辨率图片对应的版本并替换。

匹配策略：感知哈希（pHash）+ 文件大小对比
"""

import json
import shutil
import sys
from pathlib import Path

from PIL import Image

# =========================================================================
#  路 径 配 置
# =========================================================================

BASE_DIR = Path(r"C:\Users\b886855456ly\Desktop\Claude结果")
BOOK2_IMG_DIR = BASE_DIR / "images" / "book2"
DOCX_IMG_DIR = BASE_DIR / "images" / "docx_extracted"
STATE_FILE = BASE_DIR / "images" / "descriptions.json"
BACKUP_DIR = BASE_DIR / "images" / "book2_lowres_backup"

# =========================================================================
#  感 知 哈 希（简化版 pHash）
# =========================================================================

def phash(img_path, hash_size=16):
    """计算图片的感知哈希值"""
    try:
        img = Image.open(img_path).convert("L")
        img = img.resize((hash_size, hash_size), Image.LANCZOS)
        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)
        return tuple(1 if p > avg else 0 for p in pixels)
    except Exception:
        return None


def hamming(h1, h2):
    """汉明距离"""
    return sum(a != b for a, b in zip(h1, h2))

# =========================================================================
#  主 流 程
# =========================================================================

def main():
    dry_run = "--dry-run" in sys.argv

    # 加载状态
    state = json.load(open(STATE_FILE, encoding="utf-8"))

    # 收集低分辨率非装饰图
    low_res = []
    for url, entry in state["book2"].items():
        quality = entry.get("quality", "").strip()
        cat = entry.get("category", "").strip()
        desc = entry.get("description", "")
        if quality != "low_res":
            continue
        if "decorative" in cat or desc.startswith("装饰图"):
            continue
        fname = entry.get("filename", "")
        lp = Path(entry.get("local_path", ""))
        if lp.exists():
            low_res.append((fname, lp, url, entry))

    print(f"待匹配: {len(low_res)} 张低分辨率图片")
    print(f"DOCX 图片库: {len(list(DOCX_IMG_DIR.glob('*')))} 张\n")

    # 预计算 DOCX 图片哈希
    print("正在计算 DOCX 图片哈希...")
    docx_hashes = {}
    for img_path in sorted(DOCX_IMG_DIR.glob("*")):
        h = phash(img_path)
        if h:
            docx_hashes[img_path] = h
    print(f"  有效哈希: {len(docx_hashes)} 张\n")

    # 匹配
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    matched = []
    unmatched = []

    for fname, lp, url, entry in sorted(low_res):
        h1 = phash(lp)
        if not h1:
            unmatched.append((fname, "无法计算哈希"))
            continue

        # 找最佳匹配
        best_path = None
        best_dist = 999

        for docx_path, h2 in docx_hashes.items():
            dist = hamming(h1, h2)
            if dist < best_dist:
                best_dist = dist
                best_path = docx_path

        # 阈值：16x16 = 256 位，距离 < 40 认为匹配
        threshold = 40
        old_size = lp.stat().st_size
        new_size = best_path.stat().st_size if best_path else 0

        if best_dist < threshold and new_size > old_size:
            ratio = new_size / old_size if old_size > 0 else 0
            matched.append((fname, best_path.name, best_dist, old_size, new_size, ratio))

            if not dry_run:
                # 备份原图
                shutil.copy2(lp, BACKUP_DIR / fname)
                # 替换
                shutil.copy2(best_path, lp)
                # 更新状态
                entry["quality"] = "clear"
                entry["replaced_from"] = str(best_path)
                entry["original_size"] = old_size
        else:
            reason = f"距离={best_dist}" if best_dist >= threshold else f"DOCX更小({new_size}<{old_size})"
            unmatched.append((fname, reason))

    # 保存状态
    if not dry_run and matched:
        tmp = STATE_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        tmp.replace(STATE_FILE)

    # 报告
    print("=" * 60)
    print(f"  匹配成功: {len(matched)} 张")
    print(f"  未匹配:   {len(unmatched)} 张")
    print("=" * 60)

    if matched:
        print(f"\n{'已替换' if not dry_run else '将替换'}:")
        for fname, docx_name, dist, old_s, new_s, ratio in matched:
            print(f"  {fname} ← {docx_name}  "
                  f"(距离={dist}, {old_s:,}→{new_s:,}B, {ratio:.1f}x)")

    if unmatched:
        print(f"\n未匹配（需人工审查）:")
        for fname, reason in unmatched:
            print(f"  {fname}  原因: {reason}")

    if dry_run:
        print("\n[DRY-RUN] 未实际替换，加 --apply 执行替换")


if __name__ == "__main__":
    main()
