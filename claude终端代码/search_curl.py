#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用curl + 代理池方式搜索B站视频
"""
import subprocess
import re
import json

def search_with_curl(keyword):
    """用curl搜索，加上完整的伪装头"""
    
    url = f"https://api.bilibili.com/x/web-interface/search/type"
    
    # 模拟完整的浏览器请求
    cmd = [
        'curl',
        '-s',
        '-X', 'GET',
        f'{url}?search_type=video&keyword={keyword}&order=click&page=1&pagesize=20',
        '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        '-H', 'Accept: application/json',
        '-H', 'Accept-Language: zh-CN,zh;q=0.9,en;q=0.8',
        '-H', 'Accept-Encoding: gzip, deflate, br',
        '-H', 'DNT: 1',
        '-H', 'Connection: keep-alive',
        '-H', 'Upgrade-Insecure-Requests: 1',
        '-H', 'Sec-Fetch-Dest: document',
        '-H', 'Sec-Fetch-Mode: navigate',
        '--compressed',
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data.get("code") == 0:
                return data.get("data", {}).get("result", [])
    except:
        pass
    
    return []

if __name__ == "__main__":
    keywords = ["歌手大赛", "第八课", "音乐比赛课程"]
    
    all_videos = []
    
    for kw in keywords:
        print(f"[搜] {kw}...")
        results = search_with_curl(kw)
        all_videos.extend(results)
        if results:
            break
    
    if all_videos:
        # 按播放量排序
        sorted_vids = sorted(
            all_videos,
            key=lambda x: int(x.get("play", 0)) if x.get("play") else 0,
            reverse=True
        )
        
        print("\n[高播放量视频]")
        for i, vid in enumerate(sorted_vids[:5], 1):
            title = vid.get("title", "").replace('<em class="keyword">', "").replace("</em>", "")
            play = vid.get("play", 0)
            bvid = vid.get("bvid", "")
            author = vid.get("author", "")
            print(f"{i}. BV: {bvid} | UP: {author} | 播放: {play}")
            print(f"   {title}\n")
    else:
        print("[失败] 搜索API仍被限流")
