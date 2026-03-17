# coding: utf-8
"""
Apply corrections from corrections.json to descriptions.json and MD files.
"""
import json
import os
import re
from pathlib import Path

_base = Path(os.environ.get("MATH_TOOLKIT_BASE", str(Path.cwd())))
STATE = _base / "images" / "descriptions.json"
MD_BOOK1 = _base / "北师大版4年级数学下册教师用书(1)_RAG优化.md"
MD_BOOK2 = _base / "四年级+整合与拓展_RAG优化.md"
IMG_DIR = _base / "images"
CORRECTIONS = Path(__file__).resolve().parent / "corrections.json"

d = json.load(open(STATE, encoding="utf-8"))
corrections = json.load(open(CORRECTIONS, encoding="utf-8"))

# =============================================
#  Step 1: Apply corrections to descriptions.json
# =============================================
print("=== Step 1: Update descriptions.json ===")

for book_key in ["book1", "book2"]:
    if book_key not in corrections:
        continue
    for num_str, fix in corrections[book_key].items():
        fn = f"{book_key}_{int(num_str):03d}.jpg"
        found = False
        for url, info in d[book_key].items():
            if info.get("filename") == fn:
                for k, v in fix.items():
                    info[k] = v
                print(f"  Updated {fn}: cat={fix.get('category', '-')}")
                found = True
                break
        if not found:
            print(f"  WARNING: {fn} not found!")

with open(STATE, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print("descriptions.json saved.\n")

# =============================================
#  Step 2: Update MD files
# =============================================
print("=== Step 2: Update MD files ===")

# Build local_path -> info mapping
path_to_info = {}
for bk in ["book1", "book2"]:
    for url, info in d[bk].items():
        lp = info.get("local_path", "")
        if lp:
            path_to_info[lp] = info

img_dir_escaped = re.escape(IMG_DIR)
re_img = re.compile(
    r"!\[([\s\S]*?)\]\((" + img_dir_escaped + r"[^)]+)\)",
    re.MULTILINE,
)

for book_key, md_path in [("book1", MD_BOOK1), ("book2", MD_BOOK2)]:
    text = md_path.read_text(encoding="utf-8")
    fixed, removed = 0, 0

    def replacer(m):
        global fixed, removed
        old_alt = m.group(1)
        img_path = m.group(2)
        info = path_to_info.get(img_path, {})
        cat = info.get("category", "").strip()
        desc = info.get("description", "")
        quality = info.get("quality", "clear")

        # Decorative -> remove
        if cat == "decorative":
            removed += 1
            return ""

        # Update alt text if description differs
        if desc and desc != old_alt:
            new_alt = desc[:200]
            if "unreadable" in str(quality):
                new_alt = "图片无法辨认"
            fixed += 1
            return f"![{new_alt}]({img_path})"

        return m.group(0)

    # Can't use nonlocal with nested def in simple way, use list trick
    counters = [0, 0]  # [fixed, removed]

    def replacer2(m):
        old_alt = m.group(1)
        img_path = m.group(2)
        info = path_to_info.get(img_path, {})
        cat = info.get("category", "").strip()
        desc = info.get("description", "")
        quality = info.get("quality", "clear")

        if cat == "decorative":
            counters[1] += 1
            return ""

        if desc and desc != old_alt:
            new_alt = desc[:200]
            if "unreadable" in str(quality):
                new_alt = "图片无法辨认"
            counters[0] += 1
            return f"![{new_alt}]({img_path})"

        return m.group(0)

    text = re_img.sub(replacer2, text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    md_path.write_text(text, encoding="utf-8")
    print(f"[{book_key}] Updated alt: {counters[0]}, Removed decorative: {counters[1]}")

print("\nDone!")
