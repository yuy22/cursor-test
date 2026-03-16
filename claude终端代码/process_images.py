"""
RAG 知识库图片处理脚本
======================
六阶段流水线：下载 → Vision 描述 → 更新 MD → 审核报告 → 修复 alt → base64 内嵌

处理两本教材的 textin.com 外部图片链接：
  - 下载到本地
  - 用 Vision API 生成数学内容描述（LaTeX 格式）
  - 用绝对路径替换 MD 中的外部链接
  - 标记装饰图和低质量图
  - 修复垃圾 alt text
  - 将本地路径图片转为 base64 data URI（自包含 MD）
"""

import argparse
import base64
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

# =========================================================================
#  配 置 常 量
# =========================================================================

BASE_DIR = Path(r"C:\Users\b886855456ly\Desktop\Claude结果")
IMG_DIR = BASE_DIR / "images"
CODE_DIR = Path(r"C:\Users\b886855456ly\Desktop\claude终端代码")

BOOKS = {
    "book1": {
        "md": BASE_DIR / "北师大版4年级数学下册教师用书(1)_RAG优化.md",
        "img_dir": IMG_DIR / "book1",
    },
    "book2": {
        "md": BASE_DIR / "四年级+整合与拓展_RAG优化.md",
        "img_dir": IMG_DIR / "book2",
    },
}

STATE_FILE = IMG_DIR / "descriptions.json"

API_BASE = "https://www.78code.cc/v1"
API_KEY = "sk-B8XHQFWviEGCqC2kytY2WBTIwlua3kJsslmOlcWBGMiL77NH"
VISION_MODEL = "claude-sonnet-4-6"
VISION_MODEL_FALLBACK = "claude-opus-4-6"

DOWNLOAD_WORKERS = 10
DESCRIBE_WORKERS = 1
SAVE_INTERVAL = 20
MAX_RETRIES = 5

PROXY = "http://127.0.0.1:7890"

# 图片 URL 正则（两种格式）
RE_MD_IMG = re.compile(
    r'!\[([^\]]*)\]\((https://web-api\.textin\.com/ocr_image/external/[a-f0-9]+\.jpg)\)'
)
RE_HTML_IMG = re.compile(
    r'<img\s+src="(https://web-api\.textin\.com/ocr_image/external/[a-f0-9]+\.jpg)"[^>]*>'
)
RE_ANY_URL = re.compile(
    r'https://web-api\.textin\.com/ocr_image/external/[a-f0-9]+\.jpg'
)

# =========================================================================
#  Vision Prompt 模板
# =========================================================================

VISION_PROMPT = r"""你是一位数学教育专家，正在为四年级数学教材的图片编写 RAG 检索用的文字描述。

## 核心描述流程（必须严格遵守）

1. 先独立观察图片，识别图片本身的内容（形状、文字、标注、数学符号）
2. 再阅读下方的上下文，判断上下文是否与图片内容相关
3. 如果相关（如上下文提到"计数器"而图片确实是计数器），将上下文信息融入描述
4. 如果不相关，不强行关联
5. 禁止脱离上下文单独猜测图片的教学用途

## 图片文字规则

图片中出现的所有文字（标题、标注、数值、标签）必须融入描述语句中，说明它们在图中的位置和含义。
- ✅ "一个60度的锐角，图片上方写着'我想画60度的角'"
- ❌ "一个 度的角"（留空白）

如果图片中的文字或细节看不清，直接写"（此处文字模糊，请参看原图）"。
- ✅ "从左到右标注了4个数值（文字模糊，请参看原图）"
- ❌ "从左到右标注为、、、"（留空白）
- ❌ 猜测看不清的内容

## 数学公式格式

所有数学表达式用 LaTeX：
- 行内：$\frac{3}{10}$、$0.1$、$\square$、$90°$
- 独立：$$2.22+0.49=\square$$
- 分数：$\frac{1}{10}$  填空：$\square$  乘除：$\times$ $\div$

## 图片上下文

该图片前后的教材文本：
---
{context}
---

## 输出要求

输出严格 JSON（不要 markdown 代码块包裹）：
{{"description": "对图片内容的详细描述，数学内容用 LaTeX", "category": "math_diagram / exercise / table / illustration / decorative", "quality": "clear / low_res / unreadable"}}

### description 要求
- 计数器/算盘：说清有几档、每档珠子数、赋值规则
- 数学图：说清数学对象。如"正方形被平均分成10份，其中3份涂色，表示 $\frac{{3}}{{10}}=0.3$"
- 数轴图：写明范围和关键刻度
- 竖式图：写出完整算式
- 练习题图：转录题目文字和数学符号
- 几何图：说明图形类型、标注的边长/角度
- 量角器/测量图：说清操作步骤和读数
- 统计图：说明图表类型、轴标签、关键数据
- 思维导图：说明中心主题和各分支内容
- 装饰图：标记为 decorative，description 写"装饰图"

### category 定义
- math_diagram：数轴、分数模型、几何图形、面积模型、计算竖式、计数器等
- exercise：练习题、样题、填空题
- table：数据表格
- illustration：有教学意义的场景插图（购物、测量等）
- decorative：无教学信息的装饰（花边、分隔线、无内容卡通）

### quality 定义
- clear：文字和图形清晰可辨
- low_res：能看大意但细节模糊
- unreadable：无法辨认"""

# =========================================================================
#  代 理 设 置
# =========================================================================

def setup_proxy():
    """注入代理环境变量"""
    os.environ.setdefault("HTTP_PROXY", PROXY)
    os.environ.setdefault("HTTPS_PROXY", PROXY)
    os.environ.setdefault("http_proxy", PROXY)
    os.environ.setdefault("https_proxy", PROXY)


# =========================================================================
#  状 态 管 理
# =========================================================================

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"book1": {}, "book2": {}}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    tmp.replace(STATE_FILE)


# =========================================================================
#  提 取 图 片 URL + 上 下 文
# =========================================================================

def extract_images(book_key):
    """
    从 MD 文件提取所有图片 URL，返回:
      urls_ordered: [(url, line_no, context_str), ...] 按出现顺序（含重复）
      unique_urls:  [url, ...] 去重、按首次出现顺序
    """
    md_path = BOOKS[book_key]["md"]
    lines = md_path.read_text(encoding="utf-8").splitlines()

    urls_ordered = []
    seen = set()
    unique_urls = []

    for i, line in enumerate(lines):
        found = RE_ANY_URL.findall(line)
        if not found:
            continue

        # 上下文：前后各 5 行
        start = max(0, i - 5)
        end = min(len(lines), i + 6)
        ctx = "\n".join(lines[start:end])

        for url in found:
            urls_ordered.append((url, i + 1, ctx))
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

    return urls_ordered, unique_urls


# =========================================================================
#  阶 段 ①  下 载
# =========================================================================

def download_one(url, local_path):
    """下载单张图片，已存在则跳过"""
    if local_path.exists() and local_path.stat().st_size > 0:
        return "skip"
    local_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            local_path.write_bytes(r.content)
            return "ok"
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return f"error: {e}"
            time.sleep(2 ** attempt)
    return "error: max retries"


def phase_download():
    state = load_state()

    for book_key in BOOKS:
        _, unique_urls = extract_images(book_key)
        img_dir = BOOKS[book_key]["img_dir"]
        img_dir.mkdir(parents=True, exist_ok=True)

        # 构建 URL → filename 映射
        tasks = []
        for idx, url in enumerate(unique_urls, 1):
            fname = f"{book_key}_{idx:03d}.jpg"
            local = img_dir / fname
            abs_path = str(local)

            # 写入 state（保留已有数据）
            if url not in state[book_key]:
                state[book_key][url] = {
                    "filename": fname,
                    "local_path": abs_path,
                    "status": "pending",
                }
            elif "local_path" not in state[book_key][url]:
                state[book_key][url]["filename"] = fname
                state[book_key][url]["local_path"] = abs_path

            tasks.append((url, local))

        print(f"[{book_key}] 待下载: {len(tasks)} 张唯一图片")

        done, skip, fail = 0, 0, 0
        with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
            futures = {
                pool.submit(download_one, url, lp): url
                for url, lp in tasks
            }
            for fut in as_completed(futures):
                result = fut.result()
                if result == "skip":
                    skip += 1
                elif result == "ok":
                    done += 1
                else:
                    fail += 1
                    url = futures[fut]
                    state[book_key][url]["status"] = "download_error"
                    state[book_key][url]["error"] = result
                total = done + skip + fail
                if total % 50 == 0:
                    print(f"  进度: {total}/{len(tasks)}")

        print(f"  完成: 新下载 {done}, 跳过 {skip}, 失败 {fail}")

    save_state(state)
    print("下载阶段完成，state 已保存")


# =========================================================================
#  阶 段 ②  Vision 描 述
# =========================================================================

def extract_json(text):
    """从可能包含前导文本的 API 响应中提取 JSON 对象"""
    # 清理 markdown 代码块
    cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip())
    cleaned = re.sub(r'\s*```$', '', cleaned)

    # 直接尝试解析
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 从文本中提取第一个 {...} 块
    match = re.search(r'\{[^{}]*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def describe_one(url, local_path, context, model=None):
    """调用 Vision API 描述单张图片，支持指定模型"""
    img_bytes = Path(local_path).read_bytes()
    b64 = base64.b64encode(img_bytes).decode()

    prompt = VISION_PROMPT.replace("{context}", context)
    use_model = model or VISION_MODEL

    payload = {
        "model": use_model,
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
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}",
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                f"{API_BASE}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=120,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()

            data = extract_json(text)
            if data and "description" in data:
                desc = data["description"]
                # 检测废话前导语
                preambles = ("I'll", "I will", "I need", "Let me",
                             "我来", "让我", "查看", "```")
                if desc.startswith(preambles):
                    raise ValueError("preamble response, retrying")

                quality = data.get("quality", "clear").strip()

                # Sonnet 判断 low_res/unreadable → 用 Opus 兜底
                if quality in ("low_res", "unreadable") and use_model != VISION_MODEL_FALLBACK:
                    print(f"    Sonnet 判断 {quality}，升级 Opus 重试")
                    return describe_one(url, local_path, context, model=VISION_MODEL_FALLBACK)

                return {
                    "status": "done",
                    "description": desc,
                    "category": data.get("category", "illustration").strip(),
                    "quality": quality,
                    "model_used": use_model,
                }

            # 无 JSON 且是废话——强制重试
            if text and (text.startswith("I'll") or text.startswith("I will") or text.startswith("I need") or text.startswith("Let me") or text.startswith("我来") or text.startswith("```")):
                raise ValueError("preamble response, retrying")

            # JSON 解析失败但有中文文本——用原文做描述（二次防御：拒绝乱码）
            if text:
                # 验证中文可读性：至少 10 个 CJK 字符
                cjk = sum(1 for c in text[:200] if '\u4e00' <= c <= '\u9fff')
                if cjk < 10:
                    raise ValueError(f"garbled response (only {cjk} CJK chars), retrying")
                return {
                    "status": "done",
                    "description": text[:500],
                    "category": "illustration",
                    "quality": "clear",
                }

            # 空响应，重试
            raise ValueError("empty response")
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return {"status": "error", "error": str(e)}
            wait = 3 * (2 ** attempt)  # 3s → 6s → 12s → 24s → 48s
            print(f"    重试 {attempt+1}/{MAX_RETRIES}，等待 {wait}s: {e}")
            time.sleep(wait)

    return {"status": "error", "error": "max retries"}


def phase_describe(book_filter=None):
    state = load_state()
    setup_proxy()

    target_books = {book_filter: BOOKS[book_filter]} if book_filter and book_filter in BOOKS else BOOKS
    for book_key in target_books:
        # 从 MD 收集上下文（如果 URL 还在的话）
        urls_ordered, unique_urls = extract_images(book_key)
        first_ctx = {}
        for url, _line, ctx in urls_ordered:
            if url not in first_ctx:
                first_ctx[url] = ctx

        # 过滤需要描述的：从 state 里找非 done 的
        pending = []
        for url, entry in state[book_key].items():
            if entry.get("status") == "done":
                continue
            local = entry.get("local_path", "")
            if not local or not Path(local).exists():
                continue
            ctx = first_ctx.get(url, "（上下文不可用）")
            pending.append((url, local, ctx))

        total = len(pending)
        print(f"[{book_key}] 待描述: {total} 张")
        if not total:
            continue

        done_count = 0
        with ThreadPoolExecutor(max_workers=DESCRIBE_WORKERS) as pool:
            futures = {
                pool.submit(describe_one, url, lp, ctx): url
                for url, lp, ctx in pending
            }
            for fut in as_completed(futures):
                url = futures[fut]
                result = fut.result()

                # 合并结果到 state
                if url in state[book_key]:
                    state[book_key][url].update(result)
                else:
                    state[book_key][url] = result

                done_count += 1
                status = result.get("status", "?")
                cat = result.get("category", "")
                if status == "error":
                    print(f"  [{done_count}/{total}] ERROR: {url}")
                else:
                    print(f"  [{done_count}/{total}] {cat}: {url[-20:]}")

                # 定期保存
                if done_count % SAVE_INTERVAL == 0:
                    save_state(state)
                    print(f"  -- 自动保存 ({done_count}/{total})")

    save_state(state)
    print("描述阶段完成，state 已保存")


# =========================================================================
#  阶 段 ③  更 新 Markdown
# =========================================================================

def phase_update():
    state = load_state()

    for book_key in BOOKS:
        md_path = BOOKS[book_key]["md"]
        lines = md_path.read_text(encoding="utf-8").splitlines()

        book_state = state[book_key]
        new_lines = []
        replaced, deleted, flagged = 0, 0, 0

        for line in lines:
            urls_in_line = RE_ANY_URL.findall(line)

            if not urls_in_line:
                new_lines.append(line)
                continue

            # 处理本行所有图片 URL
            skip_line = False
            result_line = line

            for url in urls_in_line:
                entry = book_state.get(url, {})
                cat = entry.get("category", "").strip()
                quality = entry.get("quality", "clear").strip()
                desc = entry.get("description", "")
                local = entry.get("local_path", "")

                if not local:
                    continue

                # 装饰图：标记删除整行
                if "decorative" in cat:
                    skip_line = True
                    deleted += 1
                    break

                # 构建替换后的 alt 文本
                if "unreadable" in quality:
                    alt = "图片无法辨认"
                    flagged += 1
                else:
                    alt = desc[:200] if desc else ""
                    if "low_res" in quality:
                        flagged += 1

                md_img = f"![{alt}]({local})"

                # 替换 markdown 格式: ![...](url)
                md_pattern = re.compile(
                    r'!\[[^\]]*\]\(' + re.escape(url) + r'\)'
                )
                if md_pattern.search(result_line):
                    result_line = md_pattern.sub(lambda _: md_img, result_line)
                    replaced += 1
                    continue

                # 替换 HTML img 格式: <img src="url"...>
                html_pattern = re.compile(
                    r'<img\s+src="' + re.escape(url) + r'"[^>]*>'
                )
                if html_pattern.search(result_line):
                    result_line = html_pattern.sub(lambda _: md_img, result_line)
                    replaced += 1

            if skip_line:
                continue

            new_lines.append(result_line)

            # low_res 注释（仅对单图片行）
            if len(urls_in_line) == 1:
                url0 = urls_in_line[0]
                e = book_state.get(url0, {})
                if "low_res" in e.get("quality", ""):
                    new_lines.append("<!-- 低分辨率，建议人工核查 -->")

        # 写回文件
        md_path.write_text("\n".join(new_lines), encoding="utf-8")
        print(
            f"[{book_key}] 替换: {replaced}, "
            f"删除装饰图: {deleted}, 需人工复查: {flagged}"
        )

    print("Markdown 更新完成")


# =========================================================================
#  阶 段 ④  审 核 报 告
# =========================================================================

def phase_report():
    state = load_state()
    report_path = IMG_DIR / "flagged_report.md"

    sections = []
    sections.append("# 图片质量审核报告\n")

    for book_key in BOOKS:
        md_path = BOOKS[book_key]["md"]
        lines = md_path.read_text(encoding="utf-8").splitlines()

        # URL → 行号映射
        url_lines = {}
        for i, line in enumerate(lines):
            for url in RE_ANY_URL.findall(line):
                url_lines.setdefault(url, []).append(i + 1)

        flagged = []
        for url, entry in state[book_key].items():
            q = entry.get("quality", "clear").strip()
            if q in ("low_res", "unreadable"):
                flagged.append((url, entry, url_lines.get(url, [])))

        if not flagged:
            sections.append(f"## {book_key}\n\n无需人工复查的图片。\n")
            continue

        sections.append(f"## {book_key}（{len(flagged)} 张需复查）\n")
        for url, entry, line_nos in flagged:
            lp = entry.get("local_path", "未知")
            desc = entry.get("description", "无描述")
            q = entry.get("quality", "")
            loc = ", ".join(str(n) for n in line_nos) if line_nos else "未知"

            sections.append(f"### {Path(lp).name}\n")
            sections.append(f"- **路径**: `{lp}`")
            sections.append(f"- **质量**: `{q}`")
            sections.append(f"- **行号**: {loc}")
            sections.append(f"- **描述**: {desc}")
            sections.append("")

    # 统计摘要
    total, decorative, low, unread, done = 0, 0, 0, 0, 0
    for bk in state:
        for entry in state[bk].values():
            total += 1
            cat = entry.get("category", "").strip()
            q = entry.get("quality", "").strip()
            if "decorative" in cat:
                decorative += 1
            if "low_res" in q:
                low += 1
            if "unreadable" in q:
                unread += 1
            if entry.get("status") == "done":
                done += 1

    summary = [
        "\n## 统计摘要\n",
        f"| 指标 | 数量 |",
        f"|------|------|",
        f"| 总图片数 | {total} |",
        f"| 描述完成 | {done} |",
        f"| 装饰图（已删除） | {decorative} |",
        f"| 低分辨率 | {low} |",
        f"| 无法辨认 | {unread} |",
    ]
    sections.extend(summary)

    report_path.write_text("\n".join(sections), encoding="utf-8")
    print(f"审核报告已生成: {report_path}")


# =========================================================================
#  阶 段 ⑤  修 复 垃 圾 alt text
# =========================================================================

def phase_fix_alt():
    """修复 MD 中已替换但 alt text 是垃圾的图片行（支持跨行）"""
    state = load_state()

    # 建立 local_path → 好描述 的映射
    path_to_desc = {}
    for book_key in BOOKS:
        for url, entry in state[book_key].items():
            if entry.get("status") != "done":
                continue
            lp = entry.get("local_path", "")
            desc = entry.get("description", "")
            cat = entry.get("category", "").strip()
            quality = entry.get("quality", "clear").strip()
            if lp and desc:
                path_to_desc[lp] = {
                    "description": desc,
                    "category": cat,
                    "quality": quality,
                }

    # 跨行匹配 ![...](本地路径)，alt text 里可能含换行
    img_dir_escaped = re.escape(str(IMG_DIR))
    re_multiline_img = re.compile(
        r'!\[([\s\S]*?)\]\((' + img_dir_escaped + r'[^)]+)\)',
        re.MULTILINE,
    )

    for book_key in BOOKS:
        md_path = BOOKS[book_key]["md"]
        text = md_path.read_text(encoding="utf-8")
        fixed, skipped = 0, 0

        def replacer(m):
            nonlocal fixed, skipped
            old_alt = m.group(1)
            img_path = m.group(2)

            is_garbage = (
                "```" in old_alt
                or old_alt.lstrip().startswith("{")
                or "\\u" in old_alt[:50]
            )
            if not is_garbage:
                skipped += 1
                return m.group(0)

            info = path_to_desc.get(img_path, {})
            new_desc = info.get("description", "")
            quality = info.get("quality", "clear")

            if not new_desc:
                skipped += 1
                return m.group(0)

            if "unreadable" in quality:
                new_alt = "图片无法辨认"
            else:
                new_alt = new_desc[:200]

            fixed += 1
            return f"![{new_alt}]({img_path})"

        text = re_multiline_img.sub(replacer, text)
        md_path.write_text(text, encoding="utf-8")
        print(f"[{book_key}] 修复垃圾 alt: {fixed}, 跳过正常: {skipped}")

    print("alt text 修复完成")


# =========================================================================
#  阶 段 ⑥  Base64 内 嵌
# =========================================================================

# MIME 类型映射
_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}

# 匹配 ![alt](本地绝对路径)，alt 可跨行
_RE_LOCAL_IMG = re.compile(
    r'!\[([\s\S]*?)\]\(([A-Za-z]:\\[^)]+)\)',
)


def phase_embed():
    """将 MD 中本地路径图片转为 base64 data URI，生成自包含 MD"""
    for book_key in BOOKS:
        md_path = BOOKS[book_key]["md"]
        text = md_path.read_text(encoding="utf-8")
        embedded, missing = 0, 0

        def replacer(m):
            nonlocal embedded, missing
            alt, img_path = m.group(1), m.group(2)
            p = Path(img_path)
            if not p.exists():
                missing += 1
                print(f"  WARN: {img_path} 不存在，保留原路径")
                return m.group(0)
            mime = _MIME.get(p.suffix.lower(), "image/jpeg")
            b64 = base64.b64encode(p.read_bytes()).decode()
            embedded += 1
            return f"![{alt}](data:{mime};base64,{b64})"

        text = _RE_LOCAL_IMG.sub(replacer, text)
        out = md_path.with_name(md_path.stem + "_base64.md")
        out.write_text(text, encoding="utf-8")

        size_mb = out.stat().st_size / (1024 * 1024)
        print(f"[{book_key}] 内嵌: {embedded}, 缺失: {missing}, "
              f"输出: {out.name} ({size_mb:.1f} MB)")

    print("base64 内嵌完成")


# =========================================================================
#  入 口
# =========================================================================

PHASES = {
    "download": phase_download,
    "describe": phase_describe,
    "update": phase_update,
    "report": phase_report,
    "fix_alt": phase_fix_alt,
    "embed": phase_embed,
}


def main():
    parser = argparse.ArgumentParser(
        description="RAG 知识库图片处理（下载/描述/更新/报告）"
    )
    parser.add_argument(
        "--phase",
        choices=[*PHASES, "all"],
        required=True,
        help="执行阶段: download, describe, update, report, fix_alt, embed, all",
    )
    parser.add_argument(
        "--book",
        choices=["book1", "book2"],
        default=None,
        help="只处理指定的书（默认全部）",
    )
    args = parser.parse_args()

    setup_proxy()

    if args.phase == "all":
        for name, fn in PHASES.items():
            print(f"\n{'='*60}")
            print(f"  阶段: {name}")
            print(f"{'='*60}\n")
            if name == "describe":
                fn(book_filter=args.book)
            else:
                fn()
    else:
        if args.phase == "describe":
            PHASES[args.phase](book_filter=args.book)
        else:
            PHASES[args.phase]()


if __name__ == "__main__":
    main()
