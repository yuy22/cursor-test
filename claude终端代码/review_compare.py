"""
根据用户手动复查结果，批量对比并更新图片描述
"""
import json

from pathlib import Path
_base = Path(os.environ.get("MATH_TOOLKIT_BASE", str(Path.cwd())))
path = _base / "images" / "descriptions.json"
d = json.load(open(path, encoding="utf-8"))

# =============================================
# 取出需要检查的图片当前描述
# =============================================
check_book1 = [
    20, 26, 27, 40, 42, 48, 54, 55, 90, 145, 160, 176, 275, 298, 300,
    303, 306, 313, 343, 347, 374, 450, 470, 489, 491, 505, 508, 513,
    531, 532, 564, 568, 569, 571, 609,
]
check_book2 = [
    4, 8, 20, 40, 41, 42, 48, 73, 94, 99, 156, 164, 175, 322, 325,
    343, 344, 457,
]

out = []
for num in check_book1:
    fn = f"book1_{num:03d}.jpg"
    for url, info in d["book1"].items():
        if info.get("filename") == fn:
            out.append(f"[book1] #{num} ({fn}) cat={info.get('category','')} q={info.get('quality','')}")
            out.append(f"  DESC: {info.get('description','')[:200]}")
            out.append("")
            break

for num in check_book2:
    fn = f"book2_{num:03d}.jpg"
    for url, info in d["book2"].items():
        if info.get("filename") == fn:
            out.append(f"[book2] #{num} ({fn}) cat={info.get('category','')} q={info.get('quality','')}")
            out.append(f"  DESC: {info.get('description','')[:200]}")
            out.append("")
            break

with open(_base / "review_compare.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print(f"Wrote {len(out)} lines")
