#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站字幕智能下载 - 自动搜索+筛选+标点恢复
流程：搜索前10 → 逐个尝试 → 有字幕才下载 → 成功3个就停止
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
}

COOKIES = {"SESSDATA": SESSDATA}

# ============ 标点恢复规则 ============

QUESTION_TAILS = re.compile(
    r"(吗|呢|吧|啊|呀|么|嘛|没|不|谁|什么|怎么|怎样|哪|"
    r"几|多少|为什么|为啥|是不是|对不对|好不好|能不能|"
    r"行不行|可不可以|有没有|对吗|是吧|懂了没|明白了吗|"
    r"听懂了吗|听明白了|看懂了吗)$"
)

EXCLAMATION_WORDS = {"好", "对", "棒", "厉害", "漂亮", "真棒"}

def search_top_10(keyword):
    """搜索前10个播放量最高的视频（仅≥23分钟的完整课程）"""
    url = "https://search.bilibili.com/all"
    params = {
        "keyword": keyword,
        "order": "click",  # 按播放量排序
    }

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"

        # 从HTML提取初始化数据
        match = re.search(r'window\.__INITIAL_STATE__=({.*?});', resp.text)
        if not match:
            print(f"[ERROR] 无法解析页面")
            return []

        json_str = match.group(1)
        data = json.loads(json_str)

        videos = []
        results = data.get("pageData", {}).get("data", {}).get("result", [])

        for item in results:
            if item.get("type") == "video":
                # 【关键】过滤时长：只要≥1380秒（23分钟）的完整课程
                duration = int(item.get("duration", 0)) if isinstance(item.get("duration"), (int, str)) else 0
                if duration < 1380:  # 跳过 <23 分钟的片段
                    continue

                videos.append({
                    "bvid": item.get("bvid", ""),
                    "title": item.get("title", "").replace("<em class='keyword'>", "").replace("</em>", ""),
                    "author": item.get("author", ""),
                    "play": item.get("play", 0),
                    "duration": duration,
                })

        return videos[:10]  # 只返回前10

    except Exception as e:
        print(f"[ERROR] 搜索失败: {e}")
        return []

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

        # 已有标点则保留
        if re.search(r"[。！？，、；：…—]", content):
            result.append(content)
            continue

        # 计算时间间隔
        if i < len(body) - 1:
            time_gap = body[i + 1].get("from", 0) - item.get("to", 0)
        else:
            time_gap = 1.5

        # 标点判定
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

        # 判定是否分段（间隔≥1.2秒）
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

def download_smart(keyword, output_base=None, max_success=3):
    """
    智能下载流程：
    1. 搜索前10
    2. 逐个尝试下载
    3. 跳过无字幕的
    4. 成功3个就停止
    """
    if output_base is None:
        output_base = str(Path.cwd() / "output")

    print(f"\n[搜索] {keyword}...")
    videos = search_top_10(keyword)

    if not videos:
        print("[失败] 搜索无结果")
        return []

    print(f"\n[发现] 前10个视频（≥23分钟）:\n")
    for i, v in enumerate(videos, 1):
        mins = v['duration'] // 60
        secs = v['duration'] % 60
        print(f"  {i:2d}. [{v['bvid']}] {v['author'][:20]:20s} | 播放:{v['play']:>8,} | {mins:02d}:{secs:02d} | {v['title'][:40]}")

    # 创建输出目录
    # 从关键词提取课题名
    topic_name = keyword.split("_")[0] if "_" in keyword else keyword[:15]
    output_dir = os.path.join(output_base, "逐字稿", topic_name)
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n[下载目录] {output_dir}\n")

    success_count = 0
    saved_videos = []
    skipped_count = 0

    for idx, video in enumerate(videos, 1):
        if success_count >= max_success:
            print(f"\n[完成] 已下载 {success_count} 个，停止扫描")
            break

        bvid = video["bvid"]
        author = video["author"]
        title = video["title"]

        print(f"[{idx}] [{bvid}] {author} - {title[:50]}")

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
        filename = f"{success_count + 1:02d}_{author}_{title[:30]}.md"
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)

        filepath = os.path.join(output_dir, filename)

        # 写文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(f"**UP主**: {author}\n\n")
            f.write(f"**视频链接**: https://www.bilibili.com/video/{bvid}\n\n")
            f.write("---\n\n")
            f.write(md_text)

        print(f"  [OK] 已保存: {filename}")
        success_count += 1
        saved_videos.append({
            "bvid": bvid,
            "author": author,
            "title": title,
            "filename": filename
        })

        time.sleep(1)

    print(f"\n[统计]")
    print(f"  成功下载: {success_count}")
    print(f"  被跳过: {skipped_count}")
    print(f"  总扫描: {idx}")

    return saved_videos

if __name__ == "__main__":
    # 【改进】直接用中文关键词，不依赖input()的编码
    keyword = "北师大歌手大赛公开课"
    print(f"使用关键词: {keyword}")

    download_smart(keyword, max_success=3)
