#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站字幕下载 + 完整标点恢复 + MD输出
遵循操作手册步骤4：标点恢复算法
"""
import requests
import json
import re
import os
import time
from pathlib import Path
from urllib.parse import quote

# 读取SESSDATA
SESSDATA_FILE = str(Path(__file__).resolve().parent / ".bili_sessdata")
with open(SESSDATA_FILE, "r") as f:
    SESSDATA = f.read().strip()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Accept": "application/json",
}

COOKIES = {"SESSDATA": SESSDATA}

# ============ 标点恢复规则（操作手册步骤4） ============

# 疑问词尾表
QUESTION_TAILS = re.compile(
    r"(吗|呢|吧|啊|呀|么|嘛|没|不|谁|什么|怎么|怎样|哪|"
    r"几|多少|为什么|为啥|是不是|对不对|好不好|能不能|"
    r"行不行|可不可以|有没有|对吗|是吧|懂了没|明白了吗|"
    r"听懂了吗|听明白了|看懂了吗)$"
)

# 感叹词尾表
EXCLAMATION_WORDS = {"好", "对", "棒", "厉害", "漂亮", "真棒"}

def get_cid(bvid):
    """从BV号获取CID"""
    url = "https://api.bilibili.com/x/player/pagelist"
    params = {"bvid": bvid}

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = resp.json()

        if data["code"] == 0 and data.get("data"):
            return data["data"][0]["cid"]
        else:
            return None
    except Exception as e:
        print(f"  [ERROR] 获取CID: {e}")
        return None

def get_subtitle(bvid, cid):
    """获取字幕JSON"""
    url = "https://api.bilibili.com/x/player/wbi/v2"
    params = {"bvid": bvid, "cid": cid}

    try:
        resp = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=10)
        data = resp.json()

        if data["code"] == 0:
            subtitles = data.get("data", {}).get("subtitle", {}).get("subtitles", [])

            if not subtitles:
                return None

            # 优先中文字幕
            subtitle_url = None
            for sub in subtitles:
                if "zh" in sub.get("lan", ""):
                    subtitle_url = sub.get("subtitle_url")
                    break

            if not subtitle_url:
                subtitle_url = subtitles[0].get("subtitle_url")

            if subtitle_url.startswith("//"):
                subtitle_url = "https:" + subtitle_url

            # 下载字幕JSON
            resp2 = requests.get(subtitle_url, timeout=10)
            return resp2.json()
        else:
            return None
    except Exception as e:
        print(f"  [ERROR] 获取字幕: {e}")
        return None

def add_punctuation(body):
    """
    按操作手册步骤4规则，为字幕添加标点

    规则优先级：
    1. 已有标点 → 保留
    2. 间隔 < 0.3秒 → ，
    3. 末尾匹配疑问词 → ？
    4. 末尾是感叹词 + 间隔≥0.5秒 → ！
    5. 间隔 ≥ 0.8秒 → 。
    6. 其他（0.3-0.8秒） → ，
    """
    if not body:
        return []

    result = []

    for i, item in enumerate(body):
        content = item.get("content", "").strip()

        if not content:
            continue

        # 规则1：已有标点则保留
        if re.search(r"[。！？，、；：…—]", content):
            result.append(content)
            continue

        # 计算与下一句的时间间隔
        if i < len(body) - 1:
            time_gap = body[i + 1].get("from", 0) - item.get("to", 0)
        else:
            time_gap = 1.5

        # 规则2-6：判定标点
        if time_gap < 0.3:
            punct = "，"
        elif QUESTION_TAILS.search(content):
            punct = "？"
        elif content[-1] in EXCLAMATION_WORDS and time_gap >= 0.5:
            punct = "！"
        elif time_gap >= 0.8:
            punct = "。"
        else:
            punct = "，"

        result.append(content + punct)

    return result

def build_md_with_paragraphs(body):
    """
    将句子转为带段落和标点的Markdown
    分段规则：时间间隔 ≥ 1.2秒 → 新段落
    """
    if not body:
        return ""

    # 先加标点
    sentences = add_punctuation(body)

    lines = []
    current_para = []

    for i, item in enumerate(body):
        content = item.get("content", "").strip()

        if not content:
            continue

        # 判定是否需要分段（间隔≥1.2秒）
        if i > 0:
            time_gap = item.get("from", 0) - body[i - 1].get("to", 0)
            if time_gap >= 1.2:
                if current_para:
                    lines.append("".join(current_para))
                    current_para = []

        # 用带标点的sentence
        if i < len(sentences):
            current_para.append(sentences[i])

    if current_para:
        lines.append("".join(current_para))

    return "\n\n".join(lines)

def download_and_add_punctuation(videos, output_base=None):
    """下载视频字幕、加标点并保存"""
    if output_base is None:
        output_base = str(Path.cwd() / "output")

    # 创建文件夹结构
    output_dir = os.path.join(output_base, "逐字稿", "第八课_歌手大赛")
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n[输出目录] {output_dir}\n")

    saved_videos = []

    for idx, video in enumerate(videos, 1):
        bvid = video["bvid"]
        author = video["author"]
        title = video["title"].replace("<em class='keyword'>", "").replace("</em>", "")

        print(f"[{idx}] [{bvid}] {author} - {title[:50]}")

        # 步骤2：获取CID
        cid = get_cid(bvid)
        if not cid:
            print(f"  [SKIP] 无法获取CID")
            continue

        time.sleep(1)

        # 步骤3：获取字幕JSON
        subtitle_json = get_subtitle(bvid, cid)
        if not subtitle_json:
            print(f"  [SKIP] 无AI字幕")
            continue

        # 提取字幕体
        body = subtitle_json.get("body", [])
        if not body:
            print(f"  [SKIP] 字幕体为空")
            continue

        # 步骤4：标点恢复
        md_text = build_md_with_paragraphs(body)

        # 步骤5：生成文件名和保存
        filename = f"{idx:02d}_{author}_{title[:30]}.md"
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)

        filepath = os.path.join(output_dir, filename)

        # 写入MD文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(f"**UP主**: {author}\n\n")
            f.write(f"**视频链接**: https://www.bilibili.com/video/{bvid}\n\n")
            f.write("---\n\n")
            f.write(md_text)

        print(f"  [OK] 已保存: {filename}")
        saved_videos.append({
            "bvid": bvid,
            "author": author,
            "title": title,
            "filename": filename
        })

        time.sleep(1)

    print(f"\n[完成] 共下载 {len(saved_videos)} 个视频的字幕（已加标点）\n")

    return saved_videos

if __name__ == "__main__":
    videos = [
        {
            "bvid": "BV1Dv4y167Go",
            "author": "舒梁韵鸣",
            "title": "北师大版小学数学四年级下册《歌手大赛》含课件教案优质公开课"
        },
        {
            "bvid": "BV16D4y1J7Sx",
            "author": "舒梁韵鸣",
            "title": "北师大版小学数学四年级下册《歌手大赛》含课件教案优质公开课"
        },
        {
            "bvid": "BV18hXGYREjf",
            "author": "邱老师的数学课",
            "title": "北师大小学数学四年级下册10节《歌手大赛》"
        },
        {
            "bvid": "BV1qc411j7wN",
            "author": "优秀老师",
            "title": "北师大版小学数学四年级下册《歌手大赛》现场课教学视频"
        }
    ]

    download_and_add_punctuation(videos)
