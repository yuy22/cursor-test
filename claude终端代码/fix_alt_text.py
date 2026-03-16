"""
修复 MD 文件中的坏 alt text（v2 - 支持多行 alt text）
"""
import json
import re
from pathlib import Path

BASE_DIR = Path(r"C:\Users\b886855456ly\Desktop\Claude结果")
STATE_FILE = BASE_DIR / "images" / "descriptions.json"

BOOKS = [
    BASE_DIR / "北师大版4年级数学下册教师用书(1)_RAG优化.md",
    BASE_DIR / "四年级+整合与拓展_RAG优化.md",
]

BAD_PREFIXES = ("I'll", "I will", "I need", "Let me", "我来", "```", '{"description')

# 多行匹配：.*? 非贪婪跨行，到第一个 ]( 为止
RE_MD_IMG = re.compile(r"!\[(.*?)\]\(([^)]+)\)", re.DOTALL)

d = json.load(open(STATE_FILE, "r", encoding="utf-8"))

# local_path -> entry
path_map = {}
for bk in d:
    for url, entry in d[bk].items():
        lp = entry.get("local_path", "")
        if lp:
            path_map[lp] = entry

for md_path in BOOKS:
    text = md_path.read_text(encoding="utf-8")
    counts = {"replaced": 0, "deleted": 0}

    def do_replace(m):
        alt = m.group(1).strip()
        path = m.group(2)

        entry = path_map.get(path)
        if not entry:
            return m.group(0)

        is_bad = any(alt.startswith(p) for p in BAD_PREFIXES)
        if not is_bad:
            return m.group(0)

        cat = entry.get("category", "").strip()
        desc = entry.get("description", "")
        quality = entry.get("quality", "clear")

        if "decorative" in cat:
            counts["deleted"] += 1
            return ""

        if "unreadable" in quality:
            new_alt = "图片无法辨认"
        else:
            new_alt = desc[:200] if desc else ""

        counts["replaced"] += 1
        return f"![{new_alt}]({path})"

    new_text = RE_MD_IMG.sub(do_replace, text)

    if counts["replaced"] > 0 or counts["deleted"] > 0:
        md_path.write_text(new_text, encoding="utf-8")

    print(f"{md_path.name}: 替换 {counts['replaced']}, 删除装饰图 {counts['deleted']}")

print("Done!")
