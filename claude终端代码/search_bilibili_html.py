#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站搜索页面解析 - 从HTML初始化数据提取视频信息
"""
import requests
import json
import re
from urllib.parse import quote

def fetch_bilibili_search(keyword, page=1):
    """
    直接获取B站搜索页HTML，从__INITIAL_STATE__中提取视频列表
    """
    url = "https://www.bilibili.com/search/search"

    params = {
        "keyword": keyword,
        "page": page,
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.encoding = "utf-8"

        # 从HTML中提取JSON初始化数据
        match = re.search(r'window\.__INITIAL_STATE__=({.*?});', resp.text)
        if not match:
            print(f"[ERROR] 未找到__INITIAL_STATE__")
            return []

        json_str = match.group(1)
        data = json.loads(json_str)

        # 导航到搜索结果
        videos = []
        results = data.get("pageData", {}).get("data", {}).get("result", [])

        for item in results:
            if item.get("type") == "video":
                videos.append({
                    "title": item.get("title", ""),
                    "bvid": item.get("bvid", ""),
                    "play": item.get("play", 0),  # 播放量
                    "danmaku": item.get("danmaku", 0),  # 弹幕数
                    "author": item.get("author", ""),  # UP主名字
                    "pubdate": item.get("pubdate", 0),
                    "duration": item.get("duration", ""),
                })

        return videos

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 网络请求失败: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON解析失败: {e}")
        return []

def main():
    keywords = ["歌手大赛", "音乐 歌唱 比赛"]
    all_videos = []

    for kw in keywords:
        print(f"\n[搜索] {kw}...")
        print("=" * 80)

        videos = fetch_bilibili_search(kw)

        if videos:
            all_videos.extend(videos)
            for i, v in enumerate(videos[:10], 1):
                title = v["title"].replace("<em class='keyword'>", "").replace("</em>", "")[:60]
                print(f"{i:2d}. [{v['bvid']}] 播放:{v.get('play', 0):>8,} | "
                      f"UP: {v['author'][:20]:<20} | {title}")
        else:
            print(f"  [未找到结果]")

    # 去重 + 按播放量排序
    if all_videos:
        unique_dict = {v["bvid"]: v for v in all_videos}
        top_videos = sorted(
            unique_dict.values(),
            key=lambda x: int(x.get("play", 0)) if x.get("play") else 0,
            reverse=True
        )[:5]

        print("\n【TOP 5 高播放量视频】")
        print("=" * 80)
        for i, v in enumerate(top_videos, 1):
            title = v["title"].replace("<em class='keyword'>", "").replace("</em>", "")
            print(f"\n{i}. [{v['bvid']}]")
            print(f"   标题: {title}")
            print(f"   UP主: {v['author']}")
            print(f"   播放: {v.get('play', 0):,} | 弹幕: {v.get('danmaku', 0):,} | 时长: {v.get('duration', '')}")

        # 保存结果
        with open("top_videos.json", "w", encoding="utf-8") as f:
            json.dump(top_videos, f, ensure_ascii=False, indent=2)

        print("\n[OK] 已保存结果到 top_videos.json")
        return top_videos
    else:
        print("\n[失败] 所有搜索都无结果")
        return []

if __name__ == "__main__":
    main()
