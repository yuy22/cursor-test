"""
# ============================================================
# B站字幕批量下载器 - 北师大版四年级下册（42集）
# 合集: Season 4815902, UP主: 张静数学空间 (MID 1871763681)
# 按发布时间排序, 带标点恢复
# ============================================================
"""

import json
import os
import re
import sys
import time
import requests

# ============================================================
# 配置
# ============================================================
MID = 1871763681
SEASON_ID = 4815902
OUTPUT_DIR = r"C:\Users\b886855456ly\Desktop\张静老师的空间"
SESSDATA_FILE = os.path.join(os.path.dirname(__file__), ".bili_sessdata")

API_BASE = "https://api.bilibili.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://space.bilibili.com/1871763681/",
}

# ============================================================
# 标点恢复
# ============================================================
QUESTION_TAILS = re.compile(
    r"(吗|呢|吧|啊|呀|么|嘛|没|不|谁|什么|怎么|怎样|哪|"
    r"几|多少|为什么|为啥|是不是|对不对|好不好|能不能|"
    r"行不行|可不可以|有没有|对吗|是吧|懂了没|明白了吗|"
    r"听懂了吗|听明白了|看懂了吗)$"
)


def add_punctuation(body):
    """时间间隔 + 语境规则 → 自动标点"""
    results = []
    for i, item in enumerate(body):
        text = item["content"].strip()
        if not text:
            continue
        gap = (body[i + 1]["from"] - item["to"]) if i < len(body) - 1 else 999

        if text[-1] in "。！？，、；：…—":
            results.append(text)
            continue

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
    """字幕JSON → 带标点MD"""
    body = subtitle_json.get("body", [])
    if not body:
        return None

    punctuated = add_punctuation(body)
    paragraphs, buf = [], [punctuated[0]]

    for i in range(1, len(body)):
        gap = body[i]["from"] - body[i - 1]["to"]
        if gap >= 1.2:
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


# ============================================================
# API调用
# ============================================================
def load_sessdata():
    if os.path.exists(SESSDATA_FILE):
        with open(SESSDATA_FILE, "r") as f:
            return f.read().strip()
    raise RuntimeError("SESSDATA缓存不存在，请先运行 bilibili_subtitle.py 完成首次登录")


def fetch_season_list(sessdata):
    """获取合集全部视频"""
    url = f"{API_BASE}/x/polymer/web-space/seasons_archives_list"
    params = {"mid": MID, "season_id": SEASON_ID, "page_num": 1, "page_size": 100}
    resp = requests.get(url, params=params, headers=HEADERS, cookies={"SESSDATA": sessdata})
    data = resp.json()
    if data["code"] != 0:
        raise RuntimeError(f"合集API错误: {data['code']} {data.get('message', '')}")
    return data["data"]["archives"]


def fetch_cid(bvid, sessdata):
    """BVID → CID"""
    url = f"{API_BASE}/x/player/pagelist"
    resp = requests.get(url, params={"bvid": bvid}, headers=HEADERS, cookies={"SESSDATA": sessdata})
    data = resp.json()
    if data["code"] != 0 or not data["data"]:
        raise RuntimeError(f"pagelist错误: {bvid}")
    return data["data"][0]["cid"]


def fetch_subtitle_url(bvid, cid, sessdata):
    """获取字幕JSON的URL"""
    url = f"{API_BASE}/x/player/wbi/v2"
    params = {"bvid": bvid, "cid": cid}
    headers = {**HEADERS, "Referer": f"https://www.bilibili.com/video/{bvid}/"}
    resp = requests.get(url, params=params, headers=headers, cookies={"SESSDATA": sessdata})
    data = resp.json()
    if data["code"] != 0:
        return None

    subtitles = data["data"].get("subtitle", {}).get("subtitles", [])
    if not subtitles:
        return None

    for sub in subtitles:
        if "zh" in sub.get("lan", ""):
            return sub["subtitle_url"]
    return subtitles[0]["subtitle_url"]


def download_subtitle(sub_url):
    """下载字幕JSON"""
    if sub_url.startswith("//"):
        sub_url = "https:" + sub_url
    resp = requests.get(sub_url, headers=HEADERS)
    return resp.json()


# ============================================================
# 文件名清洗
# ============================================================
def clean_title(raw_title):
    """从原标题提取课名部分"""
    # 原标题格式: "【北师大版数学四年级下册】《XXX》 张静老师"
    m = re.search(r"[《](.+?)[》]", raw_title)
    if m:
        return m.group(1)
    # 去掉【】内容和老师名
    cleaned = re.sub(r"【.*?】", "", raw_title)
    cleaned = re.sub(r"\s*(张静老师|范亚强老师|郭永强老师)\s*", "", cleaned)
    return cleaned.strip()


def safe_filename(name):
    """移除文件名非法字符"""
    return re.sub(r'[<>:"/\\|?*]', '', name)


# ============================================================
# 主流程
# ============================================================
def main():
    sessdata = load_sessdata()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 60)
    print("B站字幕批量下载 - 北师大版四年级下册")
    print("=" * 60)

    # 获取合集列表
    print("\n[1/3] 获取合集视频列表...")
    archives = fetch_season_list(sessdata)
    # 按发布时间排序（升序）
    archives.sort(key=lambda v: v["pubdate"])
    print(f"  共 {len(archives)} 集\n")

    # 逐集处理
    success, fail, skip = 0, 0, 0
    for idx, video in enumerate(archives, 1):
        bvid = video["bvid"]
        raw_title = video["title"]
        short_title = clean_title(raw_title)
        filename = safe_filename(f"{idx:02d} {short_title}.md")
        filepath = os.path.join(OUTPUT_DIR, filename)

        # 已存在则跳过
        if os.path.exists(filepath) and os.path.getsize(filepath) > 100:
            print(f"  [{idx:02d}/42] 跳过(已存在): {filename}")
            skip += 1
            continue

        print(f"  [{idx:02d}/42] {short_title}...", end=" ", flush=True)

        try:
            # 获取CID
            cid = fetch_cid(bvid, sessdata)
            time.sleep(0.3)

            # 获取字幕URL
            sub_url = fetch_subtitle_url(bvid, cid, sessdata)
            if not sub_url:
                print("无字幕")
                fail += 1
                continue
            time.sleep(0.3)

            # 下载字幕
            sub_json = download_subtitle(sub_url)
            body = sub_json.get("body", [])
            if not body:
                print("字幕为空")
                fail += 1
                continue

            # 转MD（带标点）
            md_title = f"《{short_title}》张静老师"
            md_content = subtitle_to_markdown(sub_json, md_title)
            if not md_content:
                print("转换失败")
                fail += 1
                continue

            # 保存
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"OK ({len(body)}条, {len(md_content)}字)")
            success += 1

            # 请求间隔, 避免频率限制
            time.sleep(1)

        except Exception as e:
            print(f"错误: {e}")
            fail += 1
            time.sleep(2)

    # 汇总
    print(f"\n{'=' * 60}")
    print(f"完成! 成功: {success}, 失败: {fail}, 跳过: {skip}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
