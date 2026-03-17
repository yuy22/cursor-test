"""
# ============================================================
# B站AI字幕下载器 - 单课时验证版
# 目标: 《买菜》BV1t4PGemEhw, CID: 28579139459
# 策略: SESSDATA手动输入 → API获取字幕URL → 下载转MD
# ============================================================
"""

import json
import os
import sys
from pathlib import Path
import requests

# ============================================================
# 配置
# ============================================================
BVID = "BV1t4PGemEhw"
CID = 28579139459
TITLE = "《买菜》张静老师"
# 输出路径：环境变量 BILI_OUTPUT 或 当前目录/output
OUTPUT = os.environ.get("BILI_OUTPUT", str(Path.cwd() / "output" / "《买菜》张静老师.md"))

API_URL = "https://api.bilibili.com/x/player/wbi/v2"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": f"https://www.bilibili.com/video/{BVID}/",
}

# ============================================================
# SESSDATA获取
# ============================================================
SESSDATA_FILE = os.path.join(os.path.dirname(__file__), ".bili_sessdata")


def get_sessdata():
    """获取SESSDATA: 环境变量 > 缓存文件 > 手动输入"""
    # 环境变量优先
    val = os.environ.get("BILI_SESSDATA", "").strip()
    if val:
        return val

    # 缓存文件
    if os.path.exists(SESSDATA_FILE):
        with open(SESSDATA_FILE, "r") as f:
            val = f.read().strip()
        if val:
            print(f"[OK] 从缓存读取SESSDATA")
            return val

    # 手动输入
    print("=" * 50)
    print("需要B站SESSDATA (获取方法):")
    print("  1. Chrome打开 bilibili.com")
    print("  2. F12 → Application → Cookies")
    print("  3. 找到 .bilibili.com 下的 SESSDATA")
    print("  4. 复制其值粘贴到下方")
    print("=" * 50)
    val = input("SESSDATA: ").strip()
    if not val:
        raise RuntimeError("SESSDATA不能为空")

    # 缓存供下次使用
    with open(SESSDATA_FILE, "w") as f:
        f.write(val)
    print("[OK] SESSDATA已缓存")
    return val


def fetch_subtitle_info(sessdata):
    """调用player API获取字幕列表"""
    cookies = {"SESSDATA": sessdata}
    params = {"bvid": BVID, "cid": CID}
    resp = requests.get(
        API_URL, params=params, headers=HEADERS, cookies=cookies
    )
    resp.raise_for_status()
    data = resp.json()

    if data["code"] != 0:
        raise RuntimeError(f"API错误: {data['code']} - {data.get('message', '')}")

    subtitles = data["data"].get("subtitle", {}).get("subtitles", [])
    if not subtitles:
        raise RuntimeError("无字幕数据 — 确认视频有AI字幕且SESSDATA有效")

    # 优先中文字幕
    for sub in subtitles:
        if "zh" in sub.get("lan", ""):
            return sub["subtitle_url"]
    return subtitles[0]["subtitle_url"]


def download_subtitle(url):
    """下载字幕JSON"""
    if url.startswith("//"):
        url = "https:" + url
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


import re

# ============================================================
# 标点恢复: 利用字幕时间间隔 + 语境规则推断标点
# ============================================================
QUESTION_TAILS = re.compile(
    r"(吗|呢|吧|啊|呀|么|嘛|没|不|谁|什么|怎么|怎样|哪|"
    r"几|多少|为什么|为啥|是不是|对不对|好不好|能不能|"
    r"行不行|可不可以|有没有|对吗|是吧|懂了没|明白了吗|"
    r"听懂了吗|听明白了|看懂了吗)$"
)


def add_punctuation(body):
    """根据时间间隔和末尾词为每条字幕添加标点"""
    results = []
    for i, item in enumerate(body):
        text = item["content"].strip()
        if not text:
            continue

        # 计算与下一条的间隔
        if i < len(body) - 1:
            gap = body[i + 1]["from"] - item["to"]
        else:
            gap = 999  # 最后一条视为长停顿

        # 已有标点则保留
        if text[-1] in "。！？，、；：…—":
            results.append(text)
            continue

        # 短停顿(<0.3s): 同一句内, 加逗号
        # 中停顿(0.3-0.8s): 句间, 判断问号/句号
        # 长停顿(>0.8s): 段落级, 判断问号/句号/感叹号
        if gap < 0.3:
            text += "，"
        elif QUESTION_TAILS.search(text):
            text += "？"
        elif text.endswith(("好", "对", "棒", "厉害", "漂亮", "真棒")):
            text += "！" if gap >= 0.5 else "，"
        elif gap >= 0.8:
            text += "。"
        else:
            text += "，"

        results.append(text)
    return results


def subtitle_to_markdown(subtitle_json, title):
    """字幕JSON → 带标点纯文本MD, 按时间间隔分段"""
    body = subtitle_json.get("body", [])
    if not body:
        raise RuntimeError("字幕body为空")

    # 先为每条字幕添加标点
    punctuated = add_punctuation(body)

    # 按时间间隔分段 (停顿>1.2s为段落边界)
    GAP_THRESHOLD = 1.2
    paragraphs = []
    buf = [punctuated[0]]
    for i in range(1, len(body)):
        gap = body[i]["from"] - body[i - 1]["to"]
        if gap >= GAP_THRESHOLD:
            paragraphs.append("".join(buf))
            buf = []
        if i < len(punctuated):
            buf.append(punctuated[i])
    if buf:
        paragraphs.append("".join(buf))

    lines = [f"# {title}\n"]
    for p in paragraphs:
        p = p.strip()
        if p:
            lines.append(p)
            lines.append("")

    return "\n".join(lines)


def main():
    print(f"=== B站字幕下载: {TITLE} ===\n")

    # 支持命令行传入SESSDATA
    if len(sys.argv) > 1:
        sessdata = sys.argv[1]
    else:
        sessdata = get_sessdata()

    print(f"[..] 请求字幕信息: {BVID} / {CID}")
    sub_url = fetch_subtitle_info(sessdata)
    print(f"[OK] 字幕URL: {sub_url[:80]}...")

    print("[..] 下载字幕JSON...")
    sub_json = download_subtitle(sub_url)
    count = len(sub_json.get("body", []))
    print(f"[OK] 字幕条目数: {count}")

    md_content = subtitle_to_markdown(sub_json, TITLE)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\n[DONE] 已保存: {OUTPUT}")
    print(f"[INFO] 文件大小: {len(md_content)} 字符")


if __name__ == "__main__":
    main()
