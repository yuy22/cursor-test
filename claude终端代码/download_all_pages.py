"""
======================================================================
  B站多P字幕批量下载 — BV11A411N7Dy (四年级数学下册 北师大版 40P)
======================================================================
"""
import requests, json, re, time, os, sys

sys.stdout.reconfigure(encoding='utf-8')

BVID = "BV11A411N7Dy"
OUTPUT_DIR = r"E:\同上一堂课"
COOKIE_DIR = r"C:\Users\b886855456ly\Desktop\claude终端代码"
BASE = "https://api.bilibili.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": f"https://www.bilibili.com/video/{BVID}/",
}

# ====================================================================
#  标点恢复
# ====================================================================
QUESTION_TAILS = re.compile(
    r"(吗|呢|吧|啊|呀|么|嘛|没|不|谁|什么|怎么|怎样|哪|"
    r"几|多少|为什么|为啥|是不是|对不对|好不好|能不能|"
    r"行不行|可不可以|有没有|对吗|是吧|懂了没|明白了吗|"
    r"听懂了吗|听明白了|看懂了吗)$"
)
EXCLAIM_TAILS = re.compile(r"(好|对|棒|厉害|漂亮|真棒)$")
HAS_PUNCT = re.compile(r"[。！？，、；：…—]$")


def add_punctuation(body):
    if not body:
        return ""
    paragraphs, cur = [], []
    for i, item in enumerate(body):
        t = item["content"].strip()
        if not t:
            continue
        gap = (body[i + 1]["from"] - item["to"]) if i + 1 < len(body) else 2.0
        if not HAS_PUNCT.search(t):
            if gap < 0.3:
                t += "，"
            elif QUESTION_TAILS.search(t):
                t += "？"
            elif EXCLAIM_TAILS.search(t) and gap >= 0.5:
                t += "！"
            elif gap >= 0.8:
                t += "。"
            else:
                t += "，"
        cur.append(t)
        if gap >= 1.2 and cur:
            paragraphs.append("".join(cur))
            cur = []
    if cur:
        paragraphs.append("".join(cur))
    return "\n\n".join(paragraphs)


def safe_name(s):
    return re.sub(r'[<>:"/\\|?*]', '', s).strip()


def req(session, url, retries=3):
    for i in range(retries):
        try:
            return session.get(url, timeout=20)
        except Exception:
            if i < retries - 1:
                time.sleep(3)
            else:
                raise


def main():
    sessdata = open(os.path.join(COOKIE_DIR, ".bili_sessdata")).read().strip()
    bili_jct = open(os.path.join(COOKIE_DIR, ".bili_jct")).read().strip()
    buvid3 = open(os.path.join(COOKIE_DIR, ".bili_buvid3")).read().strip()

    s = requests.Session()
    s.headers.update(HEADERS)
    s.cookies.set("SESSDATA", sessdata)
    s.cookies.set("bili_jct", bili_jct)
    s.cookies.set("buvid3", buvid3)

    # 验证登录
    nav = req(s, f"{BASE}/x/web-interface/nav").json()
    if not nav.get("data", {}).get("isLogin"):
        print("[错误] SESSDATA已过期！")
        return
    print(f"[登录] 成功 | {nav['data']['uname']}")

    # 获取分P
    r = req(s, f"{BASE}/x/player/pagelist?bvid={BVID}")
    pages = r.json()["data"]
    total = len(pages)
    print(f"[信息] 共 {total} 个分P\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ok, skip, fail = 0, 0, 0

    for p in pages:
        num, cid, title = p["page"], p["cid"], p["part"]
        dur = p["duration"]

        # 跳过超短视频（如知识点链接，<30秒）
        if dur < 30:
            print(f"[跳过] P{num:02d} {title} (时长{dur}秒，非课程内容)")
            skip += 1
            continue

        fname = f"{num:02d} {safe_name(title)}.md"
        fpath = os.path.join(OUTPUT_DIR, fname)

        if os.path.exists(fpath) and os.path.getsize(fpath) > 100:
            print(f"[跳过] P{num:02d} {title} (已存在)")
            skip += 1
            continue

        print(f"[下载] P{num:02d}/{total} | {dur//60:02d}:{dur%60:02d} | {title}", end="", flush=True)

        try:
            r2 = req(s, f"{BASE}/x/player/v2?bvid={BVID}&cid={cid}")
            subs = r2.json().get("data", {}).get("subtitle", {}).get("subtitles", [])

            if not subs:
                print(" → 无字幕")
                fail += 1
                time.sleep(0.5)
                continue

            sub_url = next((x["subtitle_url"] for x in subs if "zh" in x.get("lan", "")), subs[0]["subtitle_url"])
            if not sub_url:
                print(" → 字幕URL为空")
                fail += 1
                continue
            if sub_url.startswith("//"):
                sub_url = "https:" + sub_url

            body = req(s, sub_url).json().get("body", [])
            if not body:
                print(" → 字幕内容为空")
                fail += 1
                continue

            text = add_punctuation(body)
            preview = text[:30].replace('\n', ' ')

            md = (f"# {title}\n\n"
                  f"**视频链接**: https://www.bilibili.com/video/{BVID}/?p={num}\n\n"
                  f"**时长**: {dur//60}分{dur%60}秒\n\n---\n\n"
                  f"{text}\n")

            with open(fpath, "w", encoding="utf-8") as f:
                f.write(md)

            print(f" → {len(text)}字 | {preview}...")
            ok += 1

        except Exception as e:
            print(f" → 错误: {e}")
            fail += 1

        time.sleep(1)

    print(f"\n{'='*50}")
    print(f"[完成] 总计 {total} P")
    print(f"  成功: {ok}")
    print(f"  跳过: {skip}")
    print(f"  无字幕: {fail}")
    print(f"  输出: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
