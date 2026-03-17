import json
import os
import re
from pathlib import Path

_base = Path(os.environ.get("MATH_TOOLKIT_BASE", str(Path.cwd())))
for name, path in [
    ("book1", str(_base / "北师大版4年级数学下册教师用书(1)_RAG优化.md")),
    ("book2", str(_base / "四年级+整合与拓展_RAG优化.md")),
]:
    text = open(path, encoding="utf-8").read()
    textin = len(re.findall(r"textin\.com", text))
    garbage = len(re.findall(r"!\[```", text))
    preamble = len(re.findall(r"!\[(I'll|Let me|Looking at)", text))
    print(f"{name}:")
    print(f"  textin URL: {textin}")
    print(f"  ``` garbage alt: {garbage}")
    print(f"  preamble alt: {preamble}")
    print()

print("=== descriptions.json ===")
d = json.load(open(_base / "images" / "descriptions.json", encoding="utf-8"))
for book in ["book1", "book2"]:
    done = sum(1 for v in d[book].values() if v.get("status") == "done")
    total = len(d[book])
    print(f"{book}: {done}/{total} done")
