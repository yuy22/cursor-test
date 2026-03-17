#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站字幕直接下载（无搜索）- 使用预设视频列表
【改进】检查视频时长、防止重复
"""
import requests
import json
import re
import os
import time
from pathlib import Path

SESSDATA_FILE = str(Path(__file__).resolve().parent / ".bili_sessdata")
with open(SESSDATA_FILE, "r") as f:
    SESSDATA = f.read().strip()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}

COOKIES = {"SESSDATA": SESSDATA}

QUESTION_TAILS = re.compile(
    r"(吗|呢|吧|啊|呀|么|嘛|没|不|谁|什么|怎么|怎样|哪|"
    r"几|多少|为什么|为啥|是不是|对不对|好不好|能不能|"
    r"行不行|可不可以|有没有|对吗|是吧|懂了没|明白了吗|"
    r"听懂了吗|听明白了|看懂了吗)$"
)

EXCLAMATION_WORDS = {"好", "对", "棒", "厉害", "漂亮", "真棒"}

def get_video_duration(bvid):
    """获取视频实际时长（秒）"""
    url = "https://api.bilibili.com/x/web-interface/view"
    params = {"bvid": bvid}

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = resp.json()

        if data["code"] == 0:
            duration = data.get("data", {}).get("duration", 0)
            return duration
        return 0
    except:
        return 0

def get_cid(bvid):
    """从BV号获取CID"""
    url = "https://api.bilibili.com/x/player/pagelist"
    params = {"bvid": bvid}

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        data = resp.json()

        if data["code"] == 0 and data.get("data"):
            return data["data"][0]["cid"]
        return None
    except:
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

            subtitle_url = None
            for sub in subtitles:
                if "zh" in sub.get("lan", ""):
                    subtitle_url = sub.get("subtitle_url")
                    break

            if not subtitle_url:
                subtitle_url = subtitles[0].get("subtitle_url")

            if subtitle_url.startswith("//"):
                subtitle_url = "https:" + subtitle_url

            resp2 = requests.get(subtitle_url, timeout=10)
            return resp2.json()
        return None
    except:
        return None

def add_punctuation(body):
    """为字幕添加标点"""
    if not body:
        return []

    result = []

    for i, item in enumerate(body):
        content = item.get("content", "").strip()

        if not content:
            continue

        if re.search(r"[。！？，、；：…—]", content):
            result.append(content)
            continue

        if i < len(body) - 1:
            time_gap = body[i + 1].get("from", 0) - item.get("to", 0)
        else:
            time_gap = 1.5

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
    """将句子转为带段落和标点的Markdown"""
    if not body:
        return ""

    sentences = add_punctuation(body)

    lines = []
    current_para = []

    for i, item in enumerate(body):
        content = item.get("content", "").strip()

        if not content:
            continue

        if i > 0:
            time_gap = item.get("from", 0) - body[i - 1].get("to", 0)
            if time_gap >= 1.2:
                if current_para:
                    lines.append("".join(current_para))
                    current_para = []

        if i < len(sentences):
            current_para.append(sentences[i])

    if current_para:
        lines.append("".join(current_para))

    return "\n\n".join(lines)

def download_videos(videos, output_base=None, max_success=3):
    """
    下载视频列表
    【改进】：检查时长≥1380秒（23分钟）、防止重复标题
    """
    if output_base is None:
        output_base = str(Path.cwd() / "output")

    output_dir = os.path.join(output_base, "逐字稿", "北师大歌手大赛公开课")
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n[输出目录] {output_dir}\n")

    success_count = 0
    skipped_count = 0
    downloaded_titles = set()  # 防重复

    for idx, video in enumerate(videos, 1):
        if success_count >= max_success:
            print(f"\n[完成] 已下载 {success_count} 个，停止扫描")
            break

        bvid = video["bvid"]
        author = video["author"]
        title = video["title"]

        # 【检查1】重复标题
        if title in downloaded_titles:
            print(f"[{idx}] [{bvid}] {author} - {title[:40]}")
            print(f"  [SKIP] 重复视频（标题已下载）")
            skipped_count += 1
            continue

        # 【检查2】获取实际时长
        duration = get_video_duration(bvid)
        mins = duration // 60
        secs = duration % 60

        print(f"[{idx}] [{bvid}] {author} | 时长:{mins:02d}:{secs:02d} - {title[:35]}")

        # 【检查3】时长过滤（≥23分钟=1380秒）
        if duration < 1380:
            print(f"  [SKIP] 时长不足23分钟（仅{mins}分{secs}秒）")
            skipped_count += 1
            continue

        # 获取CID
        cid = get_cid(bvid)
        if not cid:
            print(f"  [SKIP] 无法获取CID")
            skipped_count += 1
            continue

        time.sleep(1)

        # 获取字幕
        subtitle_json = get_subtitle(bvid, cid)
        if not subtitle_json:
            print(f"  [SKIP] 无AI字幕")
            skipped_count += 1
            continue

        body = subtitle_json.get("body", [])
        if not body:
            print(f"  [SKIP] 字幕体为空")
            skipped_count += 1
            continue

        # 标点恢复 + 分段
        md_text = build_md_with_paragraphs(body)

        # 生成文件名
        filename = f"{success_count + 1:02d}_{author}_{title[:25]}.md"
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)

        filepath = os.path.join(output_dir, filename)

        # 写文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(f"**UP主**: {author}\n\n")
            f.write(f"**视频链接**: https://www.bilibili.com/video/{bvid}\n\n")
            f.write(f"**时长**: {mins}分{secs}秒\n\n")
            f.write("---\n\n")
            f.write(md_text)

        print(f"  [OK] 已保存: {filename}")
        success_count += 1
        downloaded_titles.add(title)

        time.sleep(1)

    print(f"\n[统计]")
    print(f"  成功下载: {success_count}")
    print(f"  被跳过: {skipped_count}")

    return success_count

if __name__ == "__main__":
    # 【播放量前10，需要验证时长】
    videos = [
        {"bvid": "BV1gj411y7SS", "author": "Jason-老湿", "title": "教你如何在校园歌手大赛中拿下第一？"},
        {"bvid": "BV1b3411L7EL", "author": "Taylorllllll", "title": "北师大音乐教授课堂清唱"},
        {"bvid": "BV13z4y1k75z", "author": "北京师范大学学生会", "title": "北师大2020校园歌手大赛复赛"},
        {"bvid": "BV1St411q7DE", "author": "北京师范大学学生会", "title": "2018北京师范大学'声而不凡'校园歌手大赛"},
        {"bvid": "BV14w411T7zK", "author": "北京师范大学学生会", "title": "2023北师大校歌赛冠军选手精彩集锦"},
        {"bvid": "BV1Dq4y1a7iR", "author": "下半场秋刀鱼", "title": "北师大版小学四年级数学下册《歌手大赛》-余老师公开优质课"},
        {"bvid": "BV1Aq4y1Y7up", "author": "下半场秋刀鱼", "title": "北师大版小学四年级数学下册《歌手大赛》-米老师公开优质课"},
        {"bvid": "BV1Dv4y167Go", "author": "舒梁韵鸣", "title": "北师大版小学数学四年级下册《歌手大赛》含课件教案优质公开课"},
        {"bvid": "BV16D4y1J7Sx", "author": "舒梁韵鸣", "title": "北师大版小学数学四年级下册《歌手大赛》含课件教案优质公开课"},  # 重复标题
        {"bvid": "BV18hXGYREjf", "author": "邱老师的数学课", "title": "北师大小学数学四年级下册10节《歌手大赛》"},
    ]

    print("[开始] 下载视频（自动检查时长≥23分钟、防重复）\n")
    download_videos(videos, max_success=3)
