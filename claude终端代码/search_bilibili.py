#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站视频搜索 - 按播放量排序查找优秀视频
"""
import requests
import json
import time
import sys
import os

# 设置UTF-8编码
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/search/",
    "Origin": "https://www.bilibili.com",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

def search_videos(keyword, order="click", page=1, page_size=30):
    """
    搜索B站视频
    order: click 播放量 | dm 弹幕数 | pubdate 发布时间
    """
    url = "https://api.bilibili.com/x/web-interface/search/type"
    params = {
        "search_type": "video",
        "keyword": keyword,
        "order": order,
        "page": page,
        "pagesize": page_size,
    }

    try:
        time.sleep(1)  # 延迟避免被限流
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data["code"] != 0:
            print(f"API错误: {data['message']}")
            return []

        results = []
        for item in data.get("data", {}).get("result", []):
            duration = int(item.get("duration", 0)) if isinstance(item.get("duration"), (int, str)) else 0
            results.append({
                "title": item.get("title", "").replace("<em class=\"keyword\">", "").replace("</em>", ""),
                "bvid": item.get("bvid", ""),
                "play": item.get("play", 0),  # 播放量
                "danmaku": item.get("danmaku", 0),  # 弹幕数
                "pubdate": item.get("pubdate", 0),  # 发布时间
                "duration": duration,  # 时长(秒)
                "desc": item.get("description", ""),
            })

        return results
    except Exception as e:
        print(f"搜索失败: {e}")
        return []

if __name__ == "__main__":
    # 搜索关键词
    keywords = [
        "北师大 第一单元 第八课 歌手大赛",
        "北师大第一单元第八课歌手大赛",
        "歌手大赛 第八课",
    ]

    all_results = []

    for kw in keywords:
        print(f"\n【搜索】{kw}")
        print("=" * 80)
        results = search_videos(kw, order="click", page=1, page_size=20)

        if not results:
            print(f"  未找到结果")
            continue

        for i, item in enumerate(results, 1):
            duration_min = item["duration"] // 60
            duration_sec = item["duration"] % 60

            print(f"{i:2d}. 【{item['bvid']}】{item['title']}")
            print(f"    播放: {item['play']:,} | 弹幕: {item['danmaku']:,} | "
                  f"时长: {duration_min:02d}:{duration_sec:02d}")
            print()

            all_results.append(item)

    # 去重 + 排序
    unique = {}
    for item in all_results:
        if item["bvid"] not in unique:
            unique[item["bvid"]] = item

    sorted_results = sorted(unique.values(), key=lambda x: x["play"], reverse=True)

    print("\n【汇总 - 按播放量排序】")
    print("=" * 80)
    for i, item in enumerate(sorted_results[:15], 1):
        duration_min = item["duration"] // 60
        duration_sec = item["duration"] % 60

        print(f"{i:2d}. {item['bvid']:12s} | 播放: {item['play']:>8,} | "
              f"弹幕: {item['danmaku']:>6,} | {duration_min:02d}:{duration_sec:02d} | "
              f"{item['title'][:50]}")

    # 保存为JSON
    with open("search_results.json", "w", encoding="utf-8") as f:
        json.dump(sorted_results[:15], f, ensure_ascii=False, indent=2)

    print(f"\n[OK] 已保存前15条结果到 search_results.json")
