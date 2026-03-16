"""Debug: 检查为什么替换不生效"""
import json, re
from pathlib import Path

BASE_DIR = Path(r"C:\Users\b886855456ly\Desktop\Claude结果")
d = json.load(open(BASE_DIR / "images" / "descriptions.json", "r", encoding="utf-8"))

path_map = {}
for bk in d:
    for url, entry in d[bk].items():
        lp = entry.get("local_path", "")
        if lp:
            path_map[lp] = entry

BAD_PREFIXES = ("I'll", "I will", "I need", "Let me", "我来", "```", '{"description')

md = BASE_DIR / "北师大版4年级数学下册教师用书(1)_RAG优化.md"
text = md.read_text(encoding="utf-8")

RE = re.compile(r"!\[(.*?)\]\(([^)]+)\)", re.DOTALL)

count = 0
for m in RE.finditer(text):
    alt = m.group(1).strip()
    path = m.group(2)
    is_bad = any(alt.startswith(p) for p in BAD_PREFIXES)
    if is_bad and count < 3:
        found = path in path_map
        print(f"ALT: {repr(alt[:80])}")
        print(f"PATH: {repr(path[:80])}")
        print(f"IN MAP: {found}")
        if found:
            e = path_map[path]
            print(f"DESC: {e.get('description','')[:60]}")
        else:
            # 试试找相似的 key
            fn = Path(path).name
            for k in path_map:
                if fn in k:
                    print(f"SIMILAR KEY: {repr(k[:80])}")
                    break
        print("---")
        count += 1
