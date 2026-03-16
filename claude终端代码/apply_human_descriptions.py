"""
回写人工审查后的图片描述到 MD 和 descriptions.json
"""

import json
import re
from pathlib import Path

BASE = Path(r"C:\Users\b886855456ly\Desktop\Claude结果")
STATE_FILE = BASE / "images" / "descriptions.json"
MD_PATH = BASE / "四年级+整合与拓展_RAG优化.md"

# =========================================================================
#  人 工 描 述 + AI 描 述 合 并
# =========================================================================

# 格式: filename -> 最终描述
# "same" = 沿用AI原描述，"unclear" = 用户看不清/无法描述，保留模糊提示
FINAL_DESCRIPTIONS = {
    "book2_019.jpg": "面积单位从小到大排列的示意图，依次为：平方毫米、平方厘米、平方分米、平方米、公顷和平方千米，展示面积单位的进率关系和大小排序",

    "book2_040.jpg": "same",  # 用户确认AI描述正确

    "book2_041.jpg": "一个计数器示意图，展示计数器的基本结构，上部为横梁和立柱，下部为底座，立柱上可以拨动珠子进行计数，用于教学数位和位值概念",

    "book2_042.jpg": "same",  # 用户确认AI描述正确

    "book2_048.jpg": "same",  # 未提供新描述，保留AI描述

    "book2_070.jpg": "一位同学正在使用量角器量角的步骤演示图，展示了量角器放置在角上进行角度测量的操作过程",

    "book2_071.jpg": "量角器量角的错误示范图：量角器的中心点没有对准角的顶点，用于教学中对比正确和错误的量角方法",

    "book2_073.jpg": "一个半圆形被平均分割成180份的示意图，每一份对应 $1°$，展示角的度量单位的由来和量角器的原理",

    "book2_095.jpg": "线段图应用题：共有四段路程，每段 $60$ 千米/小时，问一共行驶了多少千米。用线段模型表示行程问题中的数量关系",

    "book2_099.jpg": "线段图应用题：有四袋大米，每袋 $60$ 元，问一共多少元。用线段模型展示 $60 \\times 4$ 的乘法应用场景",

    "book2_138.jpg": "两条平行线，用于展示平行线的基本概念和特征",

    "book2_156.jpg": "在点子图上画一个平行四边形的操作过程演示，展示如何利用点阵构造平行四边形",

    "book2_164.jpg": "两条直线如果无限延伸能够相交的示意图，展示相交直线的位置关系特征",

    "book2_175.jpg": "四边形分类的韦恩图（集合关系图）：最内层是正方形，外一层是长方形，再外层是平行四边形（包含正方形和长方形），梯形与平行四边形并列，最外层是四边形（包含梯形、平行四边形、长方形和正方形），展示各类四边形之间的包含与并列关系",

    "book2_196.jpg": "两条相交的直线，展示直线相交的位置关系",

    "book2_198.jpg": "两条平行线，展示直线平行的位置关系",

    "book2_199.jpg": "两条平行线和两条相交的直线组合图形，展示直线之间的两种基本位置关系：平行与相交",

    "book2_207.jpg": "一个长方形，标注长为 $4cm$，宽为 $3cm$，用于教学长方形的周长或面积计算",

    "book2_213.jpg": "平行线间的距离处处相等的演示图，展示平行线之间任意位置的垂直距离都相同的几何性质",

    "book2_224.jpg": "unclear",  # 用户不确定

    "book2_225.jpg": "unclear",  # 用户不确定

    "book2_243.jpg": "商的变化规律示意图：展示 $480 \\div 60 = 8$，当被除数 $480$ 乘以 $2$ 变为 $960$，除数 $60$ 也乘以 $2$ 变为 $120$ 时，商仍为 $8$，说明被除数和除数同时乘以相同的数，商不变的规律",

    "book2_257.jpg": "长除法竖式计算：$199 \\div 20$ 的正确竖式做法，展示规范的除法竖式书写格式和计算步骤",

    "book2_264.jpg": "unclear",  # 用户说自己看，无法描述

    "book2_265.jpg": "same",  # 统计图，保留AI描述

    "book2_267.jpg": "same",  # 统计图，保留AI描述

    "book2_271.jpg": "same",  # 统计图，保留AI描述

    "book2_276.jpg": "same",  # 统计图，保留AI描述

    "book2_322.jpg": "same",  # 用户确认AI描述正确

    "book2_323.jpg": "unclear",  # 用户无法描述

    "book2_325.jpg": "运用乘法结合律和乘法分配律的计算题目，展示如何利用运算定律进行简便计算",

    "book2_327.jpg": "unclear",  # 用户无法描述

    "book2_337.jpg": "计数器与正方体模型的对应关系图：计数器上的一个 $1$ 对应一个完整正方体（表示 $1$），计数器上十分位的珠子对应把一个正方体平均分成 $10$ 份取其中若干份，展示整数和小数的位值概念与实物模型的联系",

    "book2_338.jpg": "十进制计数原理的教学图示：通过正方体模型展示个位、十位、百位、十分位、百分位等不同数位的分拆表示，说明十进制计数系统中相邻数位之间十倍的进率关系",

    "book2_340.jpg": "小数的计数单位与位值教学图示：展示十分之一（$\\frac{1}{10}$）、百分之一（$\\frac{1}{100}$）、千分之一（$\\frac{1}{1000}$）等小数计数单位，以及对应的数位顺序",

    "book2_341.jpg": "正方体模型展示小数 $0.27$ 的含义：将一个 $10 \\times 10$ 的正方形中涂色 $27$ 个小格，表示 $\\frac{27}{100} = 0.27$，配合数位顺序表说明各数位上数字的意义",

    "book2_342.jpg": "不同高度的条状模型示意图，用于对比大小和表示数值，帮助学生理解小数的大小关系",

    "book2_343.jpg": "unclear",  # 看不清

    "book2_344.jpg": "unclear",  # 看不清

    "book2_345.jpg": "unclear",  # 看不清

    "book2_355.jpg": "一个计数器示意图，展示 $0$ 到 $9$ 各数字的排列刻度，上方有竖直线段分别标注数字位置，用于理解数字与计数单位的对应关系",

    "book2_357.jpg": "unclear",  # 用户看不懂

    "book2_381.jpg": "三角形知识单元的思维导图，以树状结构展示三角形的定义、分类、性质等知识要点",

    "book2_382.jpg": "三角形分类的思维导图/知识结构图，按角度和边长两种方式对三角形进行分类：按角分为锐角三角形、直角三角形、钝角三角形；按边分为等腰三角形、等边三角形、不等边三角形",

    "book2_383.jpg": "三角形知识的思维导图，以叶片状标注展示三角形的各项知识点，包括定义、分类、性质等，用于单元知识梳理",

    "book2_385.jpg": "四年级数学思维导图，中心主题为'三角形'，分支展示三角形的分类（按角分类和按边分类）、性质（内角和、稳定性、两边之和大于第三边）等知识结构",

    "book2_386.jpg": "小学四年级数学教材的思维导图式学习总结图，展示三角形和四边形的知识体系，通过连线形成知识脉络结构",

    "book2_387.jpg": "小数单元知识的思维导图/知识梳理图，展示小数的基本概念、加减法运算、与分数的对应关系等核心知识点",

    "book2_388.jpg": "三角形知识结构思维导图，核心节点为'三角形'，展示定义（由三条线段围成的图形）、分类、性质（稳定性、两边之和大于第三边）等主要分支",

    "book2_422.jpg": "小数减法竖式计算：$$8.3 - 6.18 = 2.12$$，展示小数减法竖式的规范书写格式，注意小数点对齐",

    "book2_433.jpg": "unclear",  # 用户看不懂

    "book2_435.jpg": "unclear",  # 用户看不懂

    "book2_440.jpg": "unclear",  # 用户看不懂

    "book2_454.jpg": "鸡兔同笼问题的解题过程：假设全是2人桌，$2 \\times 8 = 16$（人），$26 - 16 = 10$（人），$4 - 2 = 2$（人），$10 \\div 2 = 5$（张4人桌），$8 - 5 = 3$（张2人桌）",

    "book2_457.jpg": "鸡兔同笼类型题的列式解答过程：$38 \\div 6 = 6$（条）余 $2$（人），$6 - 1 = 5$（条），$38 - 5 \\times 6 = 8$（人），$8 \\div 4 = 2$（条）",
}

# =========================================================================
#  加 载 状 态
# =========================================================================

state = json.load(open(STATE_FILE, encoding="utf-8"))
md_text = MD_PATH.read_text(encoding="utf-8")

# 建立 filename -> (url, entry) 映射
fname_map = {}
for url, entry in state["book2"].items():
    fname = entry.get("filename", "")
    if fname:
        fname_map[fname] = (url, entry)

# =========================================================================
#  处 理 每 张 图 片
# =========================================================================

updated_md = 0
updated_state = 0

for fname, new_desc in FINAL_DESCRIPTIONS.items():
    if fname not in fname_map:
        print(f"  WARN: {fname} 不在 state 中，跳过")
        continue

    url, entry = fname_map[fname]
    local_path = entry.get("local_path", "")
    old_desc = entry.get("description", "")

    if not local_path:
        continue

    # 确定最终描述
    if new_desc == "same":
        final_desc = old_desc
    elif new_desc == "unclear":
        # 保留模糊提示，不改
        continue
    else:
        final_desc = new_desc

    # 更新 descriptions.json
    entry["description"] = final_desc
    entry["quality"] = "human_reviewed"
    updated_state += 1

    # 更新 MD 中的 alt text
    escaped_path = re.escape(local_path)
    pattern = re.compile(r"!\[[^\]]*\]\(" + escaped_path + r"\)")
    replacement = f"![{final_desc}]({local_path})"
    new_md, n = pattern.subn(lambda _: replacement, md_text)
    if n > 0:
        md_text = new_md
        updated_md += n

# =========================================================================
#  保 存
# =========================================================================

# 保存 state
tmp = STATE_FILE.with_suffix(".tmp")
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
tmp.replace(STATE_FILE)

# 保存 MD
MD_PATH.write_text(md_text, encoding="utf-8")

# =========================================================================
#  统 计
# =========================================================================

same_count = sum(1 for v in FINAL_DESCRIPTIONS.values() if v == "same")
unclear_count = sum(1 for v in FINAL_DESCRIPTIONS.values() if v == "unclear")
human_count = len(FINAL_DESCRIPTIONS) - same_count - unclear_count

print(f"{'=' * 50}")
print(f"  人工新描述回写: {human_count} 张")
print(f"  沿用AI描述:     {same_count} 张")
print(f"  保留模糊提示:   {unclear_count} 张（需后续处理）")
print(f"  MD更新:          {updated_md} 处")
print(f"  State更新:       {updated_state} 条")
print(f"{'=' * 50}")

# 列出仍为模糊的图片
print(f"\n仍标记为模糊的图片（{unclear_count}张）:")
for fname, desc in FINAL_DESCRIPTIONS.items():
    if desc == "unclear":
        print(f"  {fname}")
