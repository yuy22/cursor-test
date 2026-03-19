"""
王永春一本通 — 图片描述生成脚本
=================================
针对本地图片（从 DOCX 提取的 rId*.jpeg/png）添加 Vision 描述。

流水线：
  extract   — 解压 images.zip 到 images/ 目录
  describe  — 调用 Vision API 生成描述，保存到 state JSON
  update    — 将描述写回 MD（替换 [待描述图片] 占位符）
  report    — 生成审核报告（low_res / unreadable）

输入：
  王永春一本通_cleaned.md        — 含 [待描述图片] 占位符的 MD
  images.zip                     — 本地图片压缩包

输出：
  王永春一本通_cleaned.md        — 原地更新（占位符替换为图片描述）
  images/descriptions_wangyongchun.json  — 状态文件（幂等重跑基础）
  images/flagged_report_wangyongchun.md  — 低分辨率/无法辨认图片清单

用法：
  python describe_wangyongchun.py --phase extract
  python describe_wangyongchun.py --phase describe
  python describe_wangyongchun.py --phase update
  python describe_wangyongchun.py --phase report

  完整运行：
  python describe_wangyongchun.py --phase extract
  python describe_wangyongchun.py --phase describe
  python describe_wangyongchun.py --phase update
  python describe_wangyongchun.py --phase report
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path

import requests

# =========================================================================
#  配 置
# =========================================================================

# 工作目录：脚本默认在 claude终端代码/ 下，BASE_DIR 指向上一级（实际数据目录）
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = Path(os.environ.get("WYC_BASE_DIR", str(SCRIPT_DIR.parent)))

MD_FILE = BASE_DIR / "王永春一本通_cleaned.md"
IMG_DIR = BASE_DIR / "images"
ZIP_FILE = BASE_DIR / "images.zip"
STATE_FILE = IMG_DIR / "descriptions_wangyongchun.json"
REPORT_FILE = IMG_DIR / "flagged_report_wangyongchun.md"

# API 配置（可通过环境变量覆盖）
API_BASE = os.environ.get("VISION_API_BASE", "https://www.78code.cc/v1")
API_KEY = os.environ.get("VISION_API_KEY", "sk-B8XHQFWviEGCqC2kytY2WBTIwlua3kJsslmOlcWBGMiL77NH")
VISION_MODEL = os.environ.get("VISION_MODEL", "claude-opus-4-6")

MAX_RETRIES = 5
SAVE_INTERVAL = 20  # 每处理 N 张保存一次 state

# 代理（如需要）
PROXY = os.environ.get("HTTPS_PROXY", os.environ.get("HTTP_PROXY", ""))

# =========================================================================
#  Vision Prompt
# =========================================================================

VISION_PROMPT = r"""你是一位有二三十年教龄的小学数学名师，正在为《小学数学教材一本通》（王永春著，小学1-6年级综合自学读本）的每张图片撰写描述。

这些描述将替换 Markdown 文档中的 [待描述图片] 占位符，供后续备课、RAG检索使用。
目标：让完全看不到图片的读者，仅凭文字描述就能准确理解图片在教什么、怎么教。

---

## 第一步：先读上下文，定位这张图的教学位置

阅读下方提供的图片前后文本，判断：
1. 这一段在讲哪个数学概念/方法/规律？
2. 这张图承担什么教学功能？（从下方选一个）
   - 【引入情境】：用生活场景引出数学问题
   - 【核心说理】：用直观模型解释数学本质（如分数模型、面积模型）
   - 【算法示范】：展示计算步骤（如竖式、列表）
   - 【练习题图】：供学生练习的题目图
   - 【结论呈现】：总结规律、公式、结论
   - 【装饰插图】：无数学内容的装饰性图片

---

## 第二步：用数学教师的眼光读图

观察图片时，必须完整识别以下内容（凡图中出现的，一律转录，不得省略）：

**数字和符号**
- 所有数字（包括角标、分子分母、坐标值）原文转录
- 所有数学符号（$+$、$-$、$\times$、$\div$、$=$、$\square$、箭头）

**文字标注**
- 图中出现的所有汉字（题目语、提示语、标签、图注）原文引用
- 不能用"文字说明了…"代替，要原文写出来

**视觉设计的数学含义**
- 涂色/阴影区域：说明代表什么（如"左半部分阴影表示 $\frac{1}{2}$"）
- 箭头/虚线：说明方向和含义
- 分割线：说明平均分成几份
- 括号/大括号：说明对应关系

**如果图中文字或数字看不清**：写"（此处文字模糊，请参看原图）"，禁止猜测。

---

## 第三步：写描述——让不看图的人也能理解

描述结构（按顺序写，可根据图片类型调整）：

```
【教学功能】这张图的教学功能是：___（引入情境/核心说理/算法示范/练习题图/结论呈现）

【图片内容】___（具体描述图中的每个要素，见下方各类型要求）

【与上下文的关系】配合上文"___"（引用上下文关键语句），直观说明___
```

---

## 各类型图片的具体描述要求

**分数/小数模型（涂色格、圆形分割、面积模型）**
- 说清图形类型（正方形/圆形/长方形）、总份数、涂色份数
- 写出对应的分数/小数表达：如"正方形平均分成10份，3份涂色，表示 $\frac{{3}}{{10}}=0.3$"

**数轴图**
- 写明范围（起点、终点）、刻度间隔代表的单位
- 写出所有标注的点及其值
- 如有箭头或标记，说明含义

**计算竖式**
- 逐行写出每个数字：被加数、加数、进位符号、结果
- 如"竖式：$35+48$，个位 $5+8=13$，写3进1；十位 $3+4+1=8$；结果 $83$"

**几何图形**
- 图形类型、标注的边长/角度（原文转录数值）
- 有无辅助线/虚线，说明用途
- 如有阴影，说明阴影区域的含义

**计数器/算盘**
- 有几档、各档代表的数位（个位/十位/百位…）
- 每档有几颗珠子
- 整体表示的数是多少

**统计图（条形图/折线图/饼图）**
- 图表类型、横轴标签、纵轴标签及单位
- 关键数据（最高/最低/某项的值）原文转录

**练习题图**
- 完整转录题目文字和数学符号
- 如有填空格（$\square$）、括号，标明位置

**思维导图/结构图**
- 中心主题 + 所有分支（层级关系、内容）

**场景插图（购物、测量等）**
- 场景内容 + 图中出现的数字/价格/数量标注（原文）
- 配合上下文说明教学意图

**装饰图**
- 无数学内容（如花边、分隔线、卡通人物）→ category 选 decorative，description 写"装饰图，无数学内容"

---

## 数学公式格式（LaTeX）

- 行内：$\frac{{3}}{{10}}$、$0.1$、$\square$、$90°$、$\times$、$\div$
- 独立公式：$$2.22+0.49=\square$$
- 不等式：$3>\frac{{1}}{{2}}$

---

## 图片前后的教材上下文

（这是图片在教材中的位置，帮助你判断图片的教学功能和数学含义。若图片与上下文不符，以图片为准。）

---
{context}
---

---

## 输出格式

输出严格 JSON，不要 markdown 代码块包裹，直接以 {{ 开头：

{{
  "description": "按上方三步结构写的完整图片描述",
  "category": "math_diagram 或 exercise 或 table 或 illustration 或 decorative",
  "quality": "clear 或 low_res 或 unreadable"
}}

**category 定义**
- math_diagram：数轴、分数/小数模型、几何图、面积模型、计算竖式、计数器、思维导图等
- exercise：练习题、样题、填空题（含题目文字）
- table：数据表格、统计表
- illustration：有教学内容的场景插图（购物、测量、故事情境、实物图）
- decorative：无教学信息的装饰（花边、分隔线、纯装饰卡通）

**quality 定义**
- clear：文字和图形清晰可辨
- low_res：能看大意但细节模糊（部分数字/文字需靠上下文补充）
- unreadable：无法辨认任何内容"""


# =========================================================================
#  状 态 管 理
# =========================================================================

def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    tmp.replace(STATE_FILE)


# =========================================================================
#  提 取 图 片 路 径 + 上 下 文
# =========================================================================

# 匹配 [待描述图片] 后紧跟的 ![图片](images/rId*.jpeg) 行
RE_PENDING = re.compile(
    r"^\[待描述图片\]$"
)
RE_IMG_LINE = re.compile(
    r"^!\[(?:[^\]]*)\]\((images/rId\d+\.(?:jpeg|jpg|png))\)$"
)
# 匹配任意已有描述的图片行（用于 update 阶段替换整行）
RE_IMG_ANY = re.compile(
    r"^!\[[^\]]*\]\((images/rId\d+\.(?:jpeg|jpg|png))\)$"
)


RE_HEADING = re.compile(r"^#{1,4}\s+.+")


def find_nearest_heading(lines: list[str], before_idx: int) -> str:
    """往上找最近的 Markdown 标题（## ~ ####），最多回溯 200 行"""
    for i in range(before_idx - 1, max(-1, before_idx - 200), -1):
        if RE_HEADING.match(lines[i].strip()):
            return lines[i].strip()
    return ""


def extract_images_from_md() -> list[dict]:
    """
    扫描 MD 文件，提取所有待描述图片的信息。

    返回：
      [{"path": "images/rId5.jpeg", "placeholder_line": 6, "img_line": 7, "context": "..."}]

    上下文构成：
      - 最近的章节标题（往上最多找 200 行）
      - 图片前 8 行有效文本
      - 图片后 8 行有效文本
    """
    lines = MD_FILE.read_text(encoding="utf-8").splitlines()
    results = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not RE_PENDING.match(stripped):
            continue

        # 找紧跟的图片行（允许有一行空行间隔）
        img_path = None
        img_line_no = -1
        for j in range(i + 1, min(i + 3, len(lines))):
            m = RE_IMG_LINE.match(lines[j].strip())
            if m:
                img_path = m.group(1)
                img_line_no = j + 1  # 1-indexed
                break

        if not img_path:
            continue

        # --- 构建富上下文 ---

        # 1. 最近章节/小节标题
        nearest_heading = find_nearest_heading(lines, i)

        # 2. 图片前 8 行有效文本（跳过空行、占位符、图片行）
        before_lines = []
        for k in range(i - 1, max(-1, i - 40), -1):
            ln = lines[k].strip()
            if not ln:
                continue
            if RE_PENDING.match(ln) or RE_IMG_LINE.match(ln):
                continue
            before_lines.insert(0, ln)
            if len(before_lines) >= 8:
                break

        # 3. 图片后 8 行有效文本
        after_lines = []
        for k in range(img_line_no, min(len(lines), img_line_no + 40)):
            ln = lines[k].strip()
            if not ln:
                continue
            if RE_PENDING.match(ln) or RE_IMG_LINE.match(ln):
                continue
            after_lines.append(ln)
            if len(after_lines) >= 8:
                break

        # 拼合上下文，突出章节标题位置
        ctx_parts = []
        if nearest_heading:
            ctx_parts.append(f"【当前章节】{nearest_heading}")
        if before_lines:
            ctx_parts.append("【图片前文】\n" + "\n".join(before_lines))
        if after_lines:
            ctx_parts.append("【图片后文】\n" + "\n".join(after_lines))
        context = "\n\n".join(ctx_parts)

        results.append({
            "path": img_path,
            "placeholder_line": i + 1,
            "img_line": img_line_no,
            "context": context,
        })

    return results


# =========================================================================
#  Vision API 调 用
# =========================================================================

def encode_image(img_path: Path) -> str:
    """读取图片文件，返回 base64 字符串"""
    with open(img_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def get_data_uri(img_path: Path) -> str:
    """生成 data URI（OpenAI image_url 格式）"""
    ext = img_path.suffix.lower()
    mime = {
        ".jpeg": "image/jpeg",
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")
    b64 = encode_image(img_path)
    return f"data:{mime};base64,{b64}"


def extract_json(text: str) -> dict | None:
    """从可能含前导文本的响应中提取 JSON 对象"""
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


def call_vision_api(img_path: Path, context: str) -> dict:
    """
    调用 Vision API（OpenAI 兼容格式），返回解析后的 JSON dict。
    失败时返回 {"error": "..."} 。
    """
    prompt = VISION_PROMPT.format(context=context or "（无上下文）")
    data_uri = get_data_uri(img_path)

    payload = {
        "model": VISION_MODEL,
        "max_tokens": 2048,
        "messages": [
            {
                "role": "system",
                "content": "你只输出 JSON，不要任何解释、前言、markdown包裹。直接以 { 开头。",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_uri},
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    proxies = {"http": PROXY, "https": PROXY} if PROXY else None

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                f"{API_BASE}/chat/completions",
                json=payload,
                headers=headers,
                timeout=120,
                proxies=proxies,
            )
            resp.raise_for_status()
            raw_text = resp.json()["choices"][0]["message"]["content"].strip()

            result = extract_json(raw_text)
            if result and "description" in result:
                return result
            return {"error": f"JSON解析失败，原始响应: {raw_text[:200]}"}

        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt
                print(f"  网络错误，{wait}s 后重试: {e}")
                time.sleep(wait)
            else:
                return {"error": f"网络错误: {e}"}

    return {"error": "超过最大重试次数"}


# =========================================================================
#  阶 段 ①  解 压
# =========================================================================

def phase_extract():
    """解压 images.zip 到 images/ 目录"""
    if not ZIP_FILE.exists():
        print(f"❌ images.zip 不存在: {ZIP_FILE}")
        sys.exit(1)

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"解压 {ZIP_FILE} → {IMG_DIR} ...")

    with zipfile.ZipFile(ZIP_FILE, "r") as zf:
        members = zf.namelist()
        total = len(members)
        for i, member in enumerate(members, 1):
            target = IMG_DIR.parent / member  # images/rId5.jpeg → BASE_DIR/images/rId5.jpeg
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(target, "wb") as dst:
                dst.write(src.read())
            if i % 200 == 0:
                print(f"  {i}/{total} 已解压...")

    # 统计
    extracted = list(IMG_DIR.glob("rId*.*"))
    print(f"✅ 解压完成：{len(extracted)} 张图片在 {IMG_DIR}")


# =========================================================================
#  阶 段 ②  描 述
# =========================================================================

def phase_describe():
    """逐张调用 Vision API，生成描述，保存到 state JSON"""
    state = load_state()
    images_info = extract_images_from_md()

    total = len(images_info)
    done = sum(1 for v in state.values() if v.get("status") == "done")
    print(f"共 {total} 张图片，已完成 {done} 张，待处理 {total - done} 张")

    processed = 0
    errors = 0

    for idx, info in enumerate(images_info, 1):
        path_key = info["path"]  # "images/rId5.jpeg"

        # 跳过已完成的
        if state.get(path_key, {}).get("status") == "done":
            continue

        img_abs = BASE_DIR / path_key
        if not img_abs.exists():
            print(f"  [{idx}/{total}] ⚠️  图片不存在，跳过: {img_abs}")
            state[path_key] = {"status": "missing", "path": path_key}
            continue

        print(f"  [{idx}/{total}] 描述 {path_key} ...", end=" ", flush=True)
        result = call_vision_api(img_abs, info["context"])

        if "error" in result:
            print(f"❌ {result['error']}")
            state[path_key] = {
                "status": "error",
                "path": path_key,
                "error": result["error"],
            }
            errors += 1
        else:
            description = result.get("description", "")
            category = result.get("category", "unknown")
            quality = result.get("quality", "clear")
            print(f"✅ [{category}/{quality}] {description[:40]}...")
            state[path_key] = {
                "status": "done",
                "path": path_key,
                "description": description,
                "category": category,
                "quality": quality,
                "placeholder_line": info["placeholder_line"],
                "img_line": info["img_line"],
            }

        processed += 1
        if processed % SAVE_INTERVAL == 0:
            save_state(state)
            print(f"  💾 已保存进度（{processed} 张）")

    save_state(state)
    done_now = sum(1 for v in state.values() if v.get("status") == "done")
    print(f"\n✅ 描述阶段完成：{done_now}/{total} 张，错误 {errors} 张")
    print(f"状态文件：{STATE_FILE}")


# =========================================================================
#  阶 段 ③  更 新 MD
# =========================================================================

def phase_update():
    """
    根据 state JSON 更新 MD 文件：
    - 将 [待描述图片] 替换为 [图片描述：...]
    - decorative 图片：删除整个图片块（占位符行 + 图片行）
    - unreadable 图片：描述改为"图片无法辨认，请参看原图"
    - low_res 图片：在图片行下方加 <!-- 低分辨率，建议人工核查 --> 注释
    """
    state = load_state()
    if not state:
        print("❌ state 文件为空，请先运行 --phase describe")
        sys.exit(1)

    lines = MD_FILE.read_text(encoding="utf-8").splitlines()
    total_lines = len(lines)

    # 构建 图片相对路径 → state 的映射
    path_to_state = {k: v for k, v in state.items() if v.get("status") == "done"}

    # 扫描 MD，找到所有 [待描述图片] + 紧跟图片行的位置
    updates = []  # [(placeholder_line_idx, img_line_idx, img_path)]

    i = 0
    while i < total_lines:
        if RE_PENDING.match(lines[i].strip()):
            # 找紧跟的图片行
            for j in range(i + 1, min(i + 3, total_lines)):
                m = RE_IMG_LINE.match(lines[j].strip())
                if m:
                    updates.append((i, j, m.group(1)))
                    break
        i += 1

    print(f"找到 {len(updates)} 个待更新图片块")

    # 从后往前替换（避免行号偏移）
    new_lines = lines[:]
    decorated_removed = 0
    unreadable_marked = 0
    low_res_commented = 0
    described = 0

    for ph_idx, img_idx, img_path in reversed(updates):
        entry = path_to_state.get(img_path)

        if entry is None:
            # 没有描述（未处理或错误），保留占位符不动
            continue

        category = entry.get("category", "")
        quality = entry.get("quality", "clear")
        description = entry.get("description", "")

        img_line = new_lines[img_idx]

        if category == "decorative":
            # 删除占位符行和图片行
            del new_lines[img_idx]
            del new_lines[ph_idx]
            decorated_removed += 1
        elif quality == "unreadable":
            new_lines[ph_idx] = "[图片描述：图片无法辨认，请参看原图]"
            unreadable_marked += 1
            described += 1
        elif quality == "low_res":
            new_lines[ph_idx] = f"[图片描述：{description}]"
            # 在图片行后插入注释（img_idx 因 ph_idx 行未删除，位置不变）
            new_lines.insert(img_idx + 1, "<!-- 低分辨率，建议人工核查 -->")
            low_res_commented += 1
            described += 1
        else:
            new_lines[ph_idx] = f"[图片描述：{description}]"
            described += 1

    MD_FILE.write_text("\n".join(new_lines), encoding="utf-8")
    print(f"✅ MD 更新完成")
    print(f"   描述写入：{described} 张")
    print(f"   装饰图删除：{decorated_removed} 张")
    print(f"   无法辨认：{unreadable_marked} 张")
    print(f"   低分辨率注释：{low_res_commented} 张")
    print(f"   输出文件：{MD_FILE}")


# =========================================================================
#  阶 段 ④  审 核 报 告
# =========================================================================

def phase_report():
    """生成 flagged_report.md，列出 low_res / unreadable / error 图片"""
    state = load_state()
    if not state:
        print("❌ state 文件为空，请先运行 --phase describe")
        sys.exit(1)

    low_res = [(k, v) for k, v in state.items() if v.get("quality") == "low_res"]
    unreadable = [(k, v) for k, v in state.items() if v.get("quality") == "unreadable"]
    errors = [(k, v) for k, v in state.items() if v.get("status") == "error"]
    missing = [(k, v) for k, v in state.items() if v.get("status") == "missing"]
    done = sum(1 for v in state.values() if v.get("status") == "done")
    total = len(state)

    lines = [
        "# 王永春一本通 — 图片质量审核报告",
        "",
        f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 统计",
        "",
        f"| 指标 | 数量 |",
        f"|------|:----:|",
        f"| 总图片数 | {total} |",
        f"| Vision 描述完成 | {done} |",
        f"| 低分辨率（low_res） | {len(low_res)} |",
        f"| 无法辨认（unreadable） | {len(unreadable)} |",
        f"| 图片缺失 | {len(missing)} |",
        f"| API 错误 | {len(errors)} |",
        "",
    ]

    if low_res:
        lines += [
            "## 低分辨率图片（建议人工核查）",
            "",
            "| 图片路径 | 描述预览 |",
            "|---------|---------|",
        ]
        for path, v in low_res:
            desc = v.get("description", "")[:60]
            lines.append(f"| `{path}` | {desc} |")
        lines.append("")

    if unreadable:
        lines += [
            "## 无法辨认图片",
            "",
            "| 图片路径 |",
            "|---------|",
        ]
        for path, v in unreadable:
            lines.append(f"| `{path}` |")
        lines.append("")

    if errors:
        lines += [
            "## API 错误（需重新描述）",
            "",
            "| 图片路径 | 错误信息 |",
            "|---------|---------|",
        ]
        for path, v in errors:
            err = v.get("error", "")[:80]
            lines.append(f"| `{path}` | {err} |")
        lines.append("")

    if missing:
        lines += [
            "## 图片文件缺失",
            "",
            "| 图片路径 |",
            "|---------|",
        ]
        for path, v in missing:
            lines.append(f"| `{path}` |")
        lines.append("")

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ 审核报告生成：{REPORT_FILE}")
    print(f"   低分辨率：{len(low_res)} 张")
    print(f"   无法辨认：{len(unreadable)} 张")
    print(f"   API 错误：{len(errors)} 张")
    print(f"   图片缺失：{len(missing)} 张")


# =========================================================================
#  统 计 命 令
# =========================================================================

def phase_status():
    """显示当前处理进度"""
    images_info = extract_images_from_md()
    state = load_state()

    total = len(images_info)
    done = sum(1 for v in state.values() if v.get("status") == "done")
    errors = sum(1 for v in state.values() if v.get("status") == "error")
    missing = sum(1 for v in state.values() if v.get("status") == "missing")
    pending = total - done - errors - missing

    # 统计分类
    categories = {}
    qualities = {}
    for v in state.values():
        if v.get("status") == "done":
            c = v.get("category", "unknown")
            q = v.get("quality", "unknown")
            categories[c] = categories.get(c, 0) + 1
            qualities[q] = qualities.get(q, 0) + 1

    print(f"\n王永春一本通 图片描述进度")
    print(f"{'='*40}")
    print(f"总图片数：    {total}")
    print(f"已完成：      {done} ({done/total*100:.1f}%)" if total else f"已完成：      {done}")
    print(f"待处理：      {pending}")
    print(f"API 错误：    {errors}")
    print(f"图片缺失：    {missing}")
    print()
    if categories:
        print("分类分布：")
        for cat, cnt in sorted(categories.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {cnt}")
        print()
    if qualities:
        print("质量分布：")
        for q, cnt in sorted(qualities.items(), key=lambda x: -x[1]):
            print(f"  {q}: {cnt}")

    # 检查 MD 中还有多少未更新的占位符
    remaining = 0
    if MD_FILE.exists():
        text = MD_FILE.read_text(encoding="utf-8")
        remaining = text.count("[待描述图片]")
    print(f"\nMD 中剩余 [待描述图片] 占位符：{remaining}")


# =========================================================================
#  入 口
# =========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="王永春一本通 — 图片描述生成脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
阶段说明：
  extract   解压 images.zip 到 images/ 目录（仅需运行一次）
  describe  调用 Vision API 生成描述（可断点续跑）
  update    将描述写回 MD 文件（可重复运行）
  report    生成质量审核报告
  status    显示当前处理进度

典型工作流：
  python describe_wangyongchun.py --phase extract
  python describe_wangyongchun.py --phase describe
  python describe_wangyongchun.py --phase update
  python describe_wangyongchun.py --phase report

环境变量：
  WYC_BASE_DIR      数据目录（默认：脚本的上级目录）
  VISION_API_BASE   API 地址（默认：https://www.78code.cc/v1）
  VISION_API_KEY    API Key
  VISION_MODEL      模型名（默认：claude-opus-4-6）
  HTTPS_PROXY       代理地址（如：http://127.0.0.1:7890）
        """,
    )
    parser.add_argument(
        "--phase",
        required=True,
        choices=["extract", "describe", "update", "report", "status"],
        help="运行阶段",
    )
    args = parser.parse_args()

    print(f"\n[王永春一本通 图片描述] 阶段：{args.phase}")
    print(f"数据目录：{BASE_DIR}")
    print(f"MD 文件：{MD_FILE}")
    print(f"图片目录：{IMG_DIR}")
    print()

    if args.phase == "extract":
        phase_extract()
    elif args.phase == "describe":
        phase_describe()
    elif args.phase == "update":
        phase_update()
    elif args.phase == "report":
        phase_report()
    elif args.phase == "status":
        phase_status()


if __name__ == "__main__":
    main()
