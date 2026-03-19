# RAG 知识库构建 — 操作手册

> **目标**：将教材 PDF/DOCX 转换为 RAG 检索友好的 Markdown，图片以本地路径 + Vision 描述形式保留
> **当前状态**：图片描述质量优化中（book2 截断修复 + OCR 公式乱码修复）；王永春一本通流水线已搭建
> **最后更新**：2026-03-19

---

## 流水线总览

```
TextIn OCR
    │
    ▼
原始 MD（含 textin.com 外部图片链接）
    │
    ▼
fix_md_headings.py ── 标题层级 + OCR 噪音 + 课名标准化 + 面包屑前缀
    │
    ▼
*_RAG优化.md（结构化 MD，图片仍是外链）
    │
    ▼
process_images.py --phase download  ── 下载图片到本地
    │
    ▼
process_images.py --phase describe  ── Vision API 生成描述（需网络+代理）
    │
    ▼
process_images.py --phase update    ── 替换外链为本地路径，描述写入 alt text
    │
    ▼
process_images.py --phase report    ── 生成质量审核报告
    │
    ▼
process_images.py --phase fix_alt   ── 修复垃圾 alt text
    │
    ▼
*_RAG优化.md  ←【最终产出，备课时按行范围截取给 AI】
```

| 步骤 | 状态 | 脚本 | 需要网络 |
|:---:|:---:|------|:---:|
| 1. OCR 转换 | ✅ | TextIn 云服务 | 是 |
| 2. RAG 结构优化 | ✅ | `fix_md_headings.py` | 否 |
| 3. 图片下载 | ✅ | `process_images.py --phase download` | 是 |
| 4. Vision 描述 | 🔄 | `process_images.py --phase describe` | 是 |
| 5. 更新 MD | 🔄 | `process_images.py --phase update` | 否 |
| 6. 审核报告 | 🔄 | `process_images.py --phase report` | 否 |
| 7. 修复 alt | 🔄 | `process_images.py --phase fix_alt` | 否 |
| ~~8. Base64 内嵌~~ | ❌ 已砍掉 | ~~`process_images.py --phase embed`~~ | — |
| ~~9. 语义切分~~ | ❌ 已砍掉 | ~~`split_by_lesson.py`~~ | — |

> **为什么砍掉步骤 8-9**：base64 内嵌导致文件从 850KB 膨胀到 9.6MB，迫使后续必须做语义切分以避免 base64 被切断。改用本地路径方案后，图片描述保留在 alt text 中（AI 可读），图片文件保留在本地（Claude Code 可读），文件体积不膨胀，无需切分。备课时按行范围截取相关课时内容即可。

---

## 步骤 1：OCR 转换

### 做了什么
用 TextIn 云服务将 PDF 教材 OCR 为 Markdown。图片以 `https://web-api.textin.com/ocr_image/external/xxx.jpg` 外链形式嵌入。

### 输入 → 输出
| 输入 | 输出 |
|------|------|
| PDF 教材文件 | 原始 `.md` 文件 |

---

## 步骤 2：RAG 结构优化

### 做了什么
4 阶段一次运行：修标题层级（字号→H1~H4 映射）→ 清 OCR 噪音（页码、水印、重复标题）→ 标准化课名 → 补面包屑前缀（`# 第一单元 > 小数的意义 > 练一练`）。

### 运行方式
```bash
cd "C:\Users\b886855456ly\Desktop\claude终端代码"
python fix_md_headings.py
```

### 输入 → 输出
| 输入 | 输出 |
|------|------|
| `C:\Users\b886855456ly\Desktop\Claude结果\北师大版4年级数学下册教师用书(1).md` | `..._RAG优化.md` |
| `C:\Users\b886855456ly\Desktop\Claude结果\四年级+整合与拓展.md` | `..._RAG优化.md` |

---

## 步骤 3~8：图片处理流水线（`process_images.py`）

### 完整运行（从零开始）
```bash
cd "C:\Users\b886855456ly\Desktop\claude终端代码"
python process_images.py --phase download
python process_images.py --phase describe
python process_images.py --phase update
python process_images.py --phase report
python process_images.py --phase fix_alt
python process_images.py --phase embed
```

### 单阶段重跑
每个阶段都是幂等的：
- `download`：已存在的图片自动跳过
- `describe`：只处理 `status != "done"` 的条目
- `update`：基于 state 重新替换整个 MD
- `embed`：每次重新生成 `_base64.md`

### 各阶段详情

#### ① download — 下载图片
从 `_RAG优化.md` 中正则提取 textin.com URL，10 线程并发下载到本地。自动重试 5 次。

#### ② describe — Vision API 生成描述
逐张调用 Vision API（claude-haiku-4-5），传入图片 + 前后 5 行上下文，返回 JSON：
```json
{"description": "图片描述（含 LaTeX）", "category": "math_diagram", "quality": "clear"}
```

**category 分类**：`math_diagram`（数学图）、`exercise`（练习题）、`table`（表格）、`illustration`（教学插图）、`decorative`（装饰图）

**quality 分级**：`clear`（清晰）、`low_res`（模糊）、`unreadable`（无法辨认）

#### ③ update — 替换 MD 中的外链
- 外链 URL → `![Vision描述](本地绝对路径)`
- `decorative` 分类的图片 → 整行删除
- `unreadable` 图片 → alt 设为"图片无法辨认"
- `low_res` 图片 → 行下方加 `<!-- 低分辨率，建议人工核查 -->` 注释

#### ④ report — 审核报告
生成 `images/flagged_report.md`，列出所有 `low_res` / `unreadable` 图片及其行号、路径、描述。

#### ⑤ fix_alt — 修复垃圾 alt text
某些 Vision API 返回了 JSON 碎片或 markdown 代码块作为描述，导致 alt text 是垃圾。此阶段检测 alt 中含 ` ``` `、`{`、`\u` 等垃圾特征，用 state 中的正确描述替换。

#### ⑥ embed — Base64 内嵌（最终阶段）
将 `![alt](C:\...\book1_001.jpg)` 替换为 `![alt](data:image/jpeg;base64,...)`。

- 原文件不动，输出到 `*_RAG优化_base64.md`
- 图片文件不存在 → 保留原路径，打印警告
- alt text 保留 Vision 描述 → AI 做 RAG 检索时能读到

### 输入 → 输出
| 输入 | 输出 |
|------|------|
| `..._RAG优化.md`（850 KB / 610 KB） | 同文件原地更新（图片外链 → 本地路径 + Vision 描述 alt text） |
| textin.com 图片 URL（1083 张） | `images/book1/` (625 张) + `images/book2/` (458 张) |
| — | `images/descriptions.json`（状态文件） |
| — | `images/flagged_report.md`（审核报告） |

### 处理统计

| 指标 | Book1 | Book2 | 合计 |
|------|:-----:|:-----:|:----:|
| 唯一图片 | 625 | 458 | 1083 |
| Vision 描述完成 | 625 | 398 | 1023 |
| 装饰图（已删除） | 85 | 46 | 131 |
| 低分辨率 | 52 | 65 | 117 |
| 无法辨认 | 0 | 0 | 0 |
| book2 截断待修复 | — | 60 | 60 |

### 使用方式

备课时按行范围截取相关课时内容：
1. 在 `_RAG优化.md` 中搜索课时名（如"小数的意义（三）"）
2. 截取该课时的行范围内容给 Claude
3. Claude 读取：文字全可见 + alt text 包含图片的详细描述
4. 图片文件保留在本地 `images/` 目录，Claude Code 可直接读取

> **已砍掉的步骤**：base64 内嵌（步骤 8）和语义切分（步骤 9）不再需要。原因：base64 内嵌导致文件从 850KB 膨胀到 9.6MB，迫使后续必须做语义切分。改用本地路径方案后，图片描述在 alt text 中（AI 可读），文件体积不膨胀，备课时按行范围截取即可。

---

## 关键设计决策

### 图片描述放在 alt text 里
```markdown
![正方形被平均分成10份，其中3份涂色，表示 $\frac{3}{10}=0.3$](C:\Users\...\images\book1\book1_042.jpg)
```

- **AI 做 RAG 检索**：读原始文本，alt text 完全可见、可检索
- **Claude Code CLI**：可直接读取本地图片文件
- **网页版 Claude**：看不到图片文件，但 alt text 描述足够理解图片内容
- **不在图片下方另加描述正文**：会干扰标题/段落的语义结构

### 为什么不做 base64 内嵌和语义切分

| 方案 | 文件大小 | 问题 |
|------|----------|------|
| base64 内嵌 + 语义切分 | 9.6MB → 56 个文件 | 流程复杂，base64 有被切断风险 |
| **本地路径 + 按行范围截取** | **850KB 单文件** | **简单直接，备课时手动指定行范围** |

### descriptions.json 状态文件结构
```json
{
  "book1": {
    "https://web-api.textin.com/ocr_image/external/xxx.jpg": {
      "filename": "book1_001.jpg",
      "local_path": "C:\\Users\\...\\images\\book1\\book1_001.jpg",
      "status": "done",
      "description": "描述文本（含 LaTeX）",
      "category": "math_diagram",
      "quality": "clear"
    }
  },
  "book2": { }
}
```

---

## 全部文件清单

### 脚本 `C:\Users\b886855456ly\Desktop\claude终端代码\`

| 文件 | 用途 | 状态 |
|------|------|:---:|
| `fix_md_headings.py` | RAG 结构优化（4 阶段） | 当前方案 |
| `process_images.py` | 图片处理（7 步：download→describe→update→report→fix_alt，已砍掉 embed） | 当前方案 |
| `clean_ocr_formulas.py` | OCR 公式乱码修复 | 当前方案，需扩展 |
| `analyze_boundaries.py` | 辅助工具：打印标题位置 | 辅助 |
| `match_lessons.py` | 辅助工具：课时名匹配分析 | 辅助 |

> 已废弃：`split_by_lesson.py`、`docx_to_md.py`、`clean_docx.py`、`clean_docx_v2.py`、`rag_postprocess.py`、`fix_rag.py`、`analyze_font_sizes.py`、`parse_ppt.py`、`find_missing.py`

### 产出 `C:\Users\b886855456ly\Desktop\Claude结果\`

| 文件 | 说明 |
|------|------|
| `北师大版4年级数学下册教师用书(1)_RAG优化.md` (850 KB) | **最终产出（book1）** |
| `四年级+整合与拓展_RAG优化.md` (610 KB) | **最终产出（book2）** |
| `images/book1/` (625 张) + `images/book2/` (458 张) | 本地图片文件 |
| `images/descriptions.json` (697 KB) | 状态文件 |
| `images/flagged_report.md` | 低分辨率图片审核清单 |
| `lessons/` (56 个文件, 9 MB) | 历史产物（base64 切分版，不再维护） |
| `*_RAG优化_base64.md` | 历史产物（base64 内嵌版，不再维护） |

---

## API 配置

| 项 | 值 |
|---|---|
| 中转站 | 待定（见下方测试记录） |
| Key | 脚本 `API_KEY` 常量 |
| 模型 | `claude-opus-4-6` |
| 格式 | OpenAI 兼容（base64 image_url） |
| 代理 | `http://127.0.0.1:7890`（Clash，必须开启） |

### 中转站 Vision API 测试记录（2026-03-16）

| 中转站 | 结果 | 原因 |
|--------|:---:|------|
| `78code.cc` | ✅ 可用 | 之前跑通 1023 张，但网络中断导致 60 张截断 |
| `anyrouter.top` | ❌ | 模型列表有 claude-opus-4-6 但 Vision 请求返回 404 |
| `ai.121628.xyz` | ❌ | 假 Claude，后端是 qwen3 蒸馏模型 |
| `aidrouter.qzz.io` | ❌ | 服务器 panic 500（nil map bug） |
| `elysiver.h-e.top` | ❌ | cookie 池空，返回 500 "No cookie available" |

---

## 技术环境

| 项目 | 值 |
|------|------|
| OS | Windows 10 Home |
| Python | 3.13 |
| 依赖库 | `requests`（HTTP）、标准库（`base64`, `json`, `re`, `pathlib`, `concurrent.futures`） |

---

## 验证命令

```bash
cd "C:\Users\b886855456ly\Desktop"

# 1. 描述完成度（期望 625/625 + 458/458）
python -c "
import json
d = json.load(open('Claude结果/images/descriptions.json', encoding='utf-8'))
for book in ['book1','book2']:
    done = sum(1 for v in d[book].values() if v.get('status')=='done')
    print(f'{book}: {done}/{len(d[book])}')
"

# 2. 无 textin.com 残留（期望 0）
grep -c "textin.com" "Claude结果/北师大版4年级数学下册教师用书(1)_RAG优化.md"
grep -c "textin.com" "Claude结果/四年级+整合与拓展_RAG优化.md"

# 3. 图片本地路径完整性（所有 ![alt](path) 的 path 文件存在）
python -c "
import re
from pathlib import Path
for name in ['北师大版4年级数学下册教师用书(1)_RAG优化.md', '四年级+整合与拓展_RAG优化.md']:
    text = Path(f'Claude结果/{name}').read_text(encoding='utf-8')
    paths = re.findall(r'!\[[^\]]*\]\(([A-Za-z]:[^)]+)\)', text)
    missing = [p for p in paths if not Path(p).exists()]
    print(f'{name}: 图片引用={len(paths)}, 缺失={len(missing)}')
    for m in missing[:5]: print(f'  缺失: {m}')
"

# 4. OCR 乱码残留检查
python -c "
import re
from pathlib import Path
for name in ['北师大版4年级数学下册教师用书(1)_RAG优化.md', '四年级+整合与拓展_RAG优化.md']:
    text = Path(f'Claude结果/{name}').read_text(encoding='utf-8')
    sdiv = len(re.findall(r'\\\\sdiv', text))
    ring = len(re.findall(r'∘', text))
    line_cmd = len(re.findall(r'\\\\line', text))
    print(f'{name}: \\sdiv={sdiv}, ∘={ring}, \\line={line_cmd}')
"
```

---

## 问题记录

| # | 问题 | 发现日期 | 状态 |
|---|------|----------|:---:|
| 1 | 中转站 `ai.huan666.de` 不稳定，13 张图片失败 | 03-10 | ✅ 已解决 → 换 `78code.cc`，全部 1083 张完成 |
| 2 | Windows 反斜杠路径在 MD 渲染器中不显示图片 | 03-10 | ✅ 不影响 → 改用本地路径方案，AI 读 alt text 即可 |
| 3 | 部分 Vision API 返回垃圾 alt text（JSON 碎片） | 03-10 | ✅ 已解决 → 步骤 7 fix_alt 阶段 |
| 4 | `chunk_size=1024` 切块导致 base64 被切成乱码碎片 | 03-14 | ✅ 不再适用 → 已砍掉 base64 内嵌和语义切分 |
| 5 | H3 盲切产出 217 个碎片文件 | 03-14 | ✅ 不再适用 → 已砍掉语义切分 |
| 6 | 教师用书结构 ≠ PPT课时 | 03-14 | ✅ 不再适用 → 已砍掉语义切分 |
| 7 | base64 图片在部分 MD 渲染器中不显示 | 03-14 | ✅ 不再适用 → 已砍掉 base64 内嵌 |
| 8 | Vision 描述质量差（Haiku 误判、废话、截断） | 03-15 | ✅ 已解决 → 换 Opus 4-6 重跑，详见下方「图片描述质量优化」 |
| 9 | OCR 数学公式乱码（`∘` 代替 `°`） | 03-15 | ✅ 已解决 → `clean_ocr_formulas.py` 修复 109 处 |
| 10 | 低分辨率图片无法自动替换 | 03-15 | ✅ 已解决 → 55 张导出人工审查，43 张已回写描述，12 张标注模糊 |
| 11 | 描述被网络中断截断（Connection aborted） | 03-16 | 🔄 修复中 → book2 截断 60 张待重跑（中转站问题，见下方） |
| 12 | OCR 碎片（"作品1""方法一"等孤立短行） | 03-15 | ❌ 待处理 → 约 1011 处 |
| 13 | `\sdiv` OCR 乱码（竖式除法） | 03-16 | ❌ 待处理 → 47 处，应为 `\div` |
| 14 | `\line` OCR 乱码（竖式横线） | 03-16 | ❌ 待处理 → 90 处，TextIn 伪 LaTeX |
| 15 | 残留 `∘` 符号（温度/角度） | 03-16 | ❌ 待处理 → 4+ 处，clean_ocr_formulas.py 未覆盖 |
| 16 | `\\` 过度转义导致 LaTeX 渲染问题 | 03-16 | ❌ 待处理 → 100+ 处 |
| 17 | 中转站 Vision API 不可用 | 03-16 | 🔄 → anyrouter/121628/aidrouter/elysiver 均失败，需换站或回 78code |

---

## 图片描述质量优化（2026-03-15 ~ 03-16）

### 一、发现的问题

用户审查 `四年级+整合与拓展_RAG优化.md` 后发现 Haiku Vision 生成的图片描述存在 5 类严重问题：

| # | 问题 | 典型案例 |
|---|------|----------|
| 1 | 图片被根本性误判 | 计数器被识别为"分数模型" |
| 2 | 上下文未被利用 | 明确写了"二进制计数器"，描述却猜成别的 |
| 3 | 文字/数值缺失留空 | "一个 度的角" → 应为"一个60度的角" |
| 4 | OCR 碎片散落 | "作品1""方法一"等脱离图片独立成行 |
| 5 | 数学公式 OCR 乱码 | `1∘=1=5⋅1∘`（∘ 代替 °） |

### 二、造成的原因

| 原因 | 说明 |
|------|------|
| Vision 模型能力不足 | Haiku 看不懂计数器 vs 分数模型，看不清小字，不会主动利用上下文 |
| Prompt 指导不够精确 | 没有要求"先看图再对照上下文"，没有禁止猜测看不清的内容 |
| max_tokens 不够 | 原 1024，描述写到一半被截断（如 `$\frac{1` 后面没了） |
| OCR 符号误识别 | TextIn 把 `°` 识别为 `∘`（Unicode 环运算符 U+2218） |

### 三、执行过程

#### 步骤 1：修改 process_images.py

| 修改项 | 原值 | 新值 |
|--------|------|------|
| 模型 | `claude-haiku-4-5-20251001` | `claude-opus-4-6` |
| max_tokens | 1024 | 2048 |
| VISION_PROMPT | 基础描述规则 | 新增三条核心规则（见下） |

**新增 Prompt 规则：**

- **规则 A（先看图再看上下文）**：先独立观察图片内容，再对照上下文判断是否相关，相关才融入。禁止脱离上下文单独猜测。
- **规则 B（图片文字必须融入）**：图片中所有文字必须说明位置和含义，禁止留空白。
- **规则 C（看不清就说看不清）**：看不清的写"（此处文字模糊，请参看原图）"，禁止猜测。

#### 步骤 2：低分辨率图片人工审查

**背景**：55 张图片被 Vision 标记为 `low_res`，尝试从 DOCX/PDF 获取清晰版本替换，但发现：
- DOCX 是 OCR 产物，图片分辨率更低
- PDF 是全页扫描（2866×4046），无独立小图可裁剪
- 现有 book2 图片已是 TextIn 从 PDF 高清页面裁剪的，低分辨率是**原书图片本身不清晰**（学生手写作品、手绘思维导图等）

**处理方案**：
1. 导出 55 张低分辨率图片到 `images/低分辨率_待人工审查/`
2. 同时导出对应 PDF 页面截图作为参考
3. 生成 `人工审查清单.md`，用户填写正确描述
4. 用户审查后回写：35 张人工新描述 + 8 张沿用 AI + 12 张标注模糊

**脚本**：`export_lowres_for_review.py`、`apply_human_descriptions.py`

#### 步骤 3：OCR 公式乱码修复

**脚本**：`clean_ocr_formulas.py`

| 修复规则 | 数量 |
|----------|:---:|
| `∘°` → `°`（双符号） | 1 |
| `∘C` → `°C`（温度） | 10 |
| `数字∘` → `数字°`（角度） | 96 |
| `1°=1=5⋅1°` → `1°`（乱码公式） | 1 |
| `演示1180°` → `演示：180°`（OCR粘连） | 1 |
| **合计** | **109** |

修复后 `∘` 符号零残留。

**重要**：OCR 清洗必须在 Vision 描述全部完成之后再做最终一轮，因为 Vision 描述可能引入新的公式符号。

#### 步骤 4：Opus 重跑 Vision 描述（book2）

```bash
cd "C:\Users\b886855456ly\Desktop\claude终端代码"

# 重置 descriptions.json 中非人工审查的条目
# （脚本自动跳过 quality=human_reviewed 的 43 张）

# 用 Opus 重跑
python process_images.py --phase describe
```

**结果**：415 张 Opus 描述完成，0 错误。但发现 60 张因网络中断（Clash 代理 Connection aborted）导致描述被截断。

#### 步骤 5：截断描述修复（进行中）

检测逻辑：描述少于 10 字，或以 `，、（的是和与为了在` 等连接词结尾。

```bash
# 只重置截断的 60 张，重跑
python process_images.py --phase describe
```

#### 步骤 6：回写 alt text 到 MD

```bash
# 自定义脚本，将 descriptions.json 中的新描述写入 MD 的 alt text
# 跳过 human_reviewed 和标注模糊的图片
```

修复了 127 条嵌套 JSON 描述（Opus 返回了 JSON 字符串而非纯文本）。

### 四、待完成

| # | 项目 | 说明 | 优先级 |
|---|------|------|:---:|
| 1 | book2 截断修复 | 60 张 pending，需找到可用的 Vision API 中转站 | 🔴 P0 |
| 2 | book1 Opus 重跑 | 625 张，尚未开始 | 🔴 P0 |
| 3 | `\sdiv` → `\div` | 47 处，竖式除法公式完全破坏 | 🔴 P0 |
| 4 | `\line` 清理 | 90 处，竖式横线显示错误 | 🔴 P0 |
| 5 | 残留 `∘` 符号 | 4+ 处，温度/角度显示错误 | 🟠 P1 |
| 6 | `\\` 过度转义 | 100+ 处，LaTeX 渲染问题 | 🟠 P1 |
| 7 | OCR 碎片处理 | ~1011 处，"作品N""方法一"等孤立短行 | 🟡 P2 |
| 8 | 最终 OCR 清洗 | Vision 全部完成后再跑一遍 `clean_ocr_formulas.py` | 🟡 P2 |
| 9 | 后续流水线 | update → fix_alt（需 Vision 全部完成后执行） | 🟡 P2 |

> **依赖关系**：#1 #2 → #8 #9 → 最终产出。#3~#7 可与 #1 #2 并行。

### 五、关键文件

| 文件 | 用途 | 状态 |
|------|------|:---:|
| `process_images.py` | 七步图片处理（已改模型/token/Prompt，已砍掉 embed） | 当前方案 |
| `clean_ocr_formulas.py` | OCR 公式乱码修复（`∘`→`°`） | 当前方案，需扩展 |
| `export_lowres_for_review.py` | 导出低分辨率图片供人工审查 | 已完成 |
| `apply_human_descriptions.py` | 回写人工描述到 MD 和 state | 已完成 |
| `split_by_lesson.py` | 语义切分（已砍掉，不再使用） | 废弃 |
| `match_and_replace_images.py` | 图片哈希匹配替换（已验证不可行） | 废弃 |

---

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v1~v5 | 03-10 ~ 03-13 | 九阶段流水线搭建 |
| v6 | 03-14 | 语义切分完成，操作手册成型 |
| v7 | 03-15 ~ 03-16 | 图片描述质量优化：Opus 重跑 + OCR 修复 + 低分辨率人工审查 |
| v8 | 03-16 | 砍掉 base64 内嵌（步骤8）和语义切分（步骤9），改用本地路径方案；新增 OCR 公式乱码问题清单（`\sdiv`/`\line`/`\\`转义） |
| v9 | 03-19 | 新增王永春一本通（DOCX→MD）图片描述流水线，脚本 `describe_wangyongchun.py` |

---

## 王永春一本通 — 图片描述流水线（v9 新增）

> **来源**：DOCX 扫描版，通过 `clean_docx_v2.py` 清洗后生成 `王永春一本通_cleaned.md`
> **图片格式**：本地文件 `images/rId*.jpeg/png`（随 `images.zip` 一起交付）
> **当前状态**：`describe` 阶段待执行（需 Vision API 代理）

### 与 book1/book2 流水线的区别

| 对比项 | book1/book2 | 王永春一本通 |
|--------|-------------|-------------|
| 图片来源 | textin.com 外部 URL | DOCX 提取的本地 rId*.jpeg |
| 是否需要下载 | 是（`--phase download`） | 否（`--phase extract` 解压 zip） |
| 图片占位符 | textin URL 直接嵌入 | `[待描述图片]` 行 |
| 描述写入位置 | alt text（`![描述](路径)`） | 独立描述行（`[图片描述：...]`） |
| 状态文件 | `images/descriptions.json` | `images/descriptions_wangyongchun.json` |

### 脚本

```
claude终端代码/describe_wangyongchun.py
```

### 完整运行流程

```bash
cd "C:\Users\b886855456ly\Desktop"

# 环境变量（可选，不设则用脚本内默认值）
set WYC_BASE_DIR=C:\Users\b886855456ly\Desktop
set VISION_API_BASE=https://www.78code.cc/v1
set VISION_API_KEY=sk-xxx
set VISION_MODEL=claude-opus-4-6
set HTTPS_PROXY=http://127.0.0.1:7890

# 步骤 1：解压图片（只需一次）
python claude终端代码/describe_wangyongchun.py --phase extract

# 步骤 2：Vision 描述（可断点续跑，已完成的自动跳过）
python claude终端代码/describe_wangyongchun.py --phase describe

# 步骤 3：写回 MD（幂等，可重复执行）
python claude终端代码/describe_wangyongchun.py --phase update

# 步骤 4：生成审核报告
python claude终端代码/describe_wangyongchun.py --phase report

# 随时查看进度
python claude终端代码/describe_wangyongchun.py --phase status
```

### 输入 → 输出

| 输入 | 输出 |
|------|------|
| `王永春一本通_cleaned.md`（1895 张 `[待描述图片]`） | 同文件原地更新（占位符替换为图片描述） |
| `images.zip`（2064 张图片） | `images/rId*.jpeg/png`（解压到本地） |
| — | `images/descriptions_wangyongchun.json`（状态文件） |
| — | `images/flagged_report_wangyongchun.md`（审核报告） |

### 处理统计（待完成）

| 指标 | 数量 |
|------|:----:|
| 总图片数 | 1895 |
| 图片文件数（zip） | 2064 |
| Vision 描述完成 | 0（待运行） |

### 描述写入格式

```markdown
[图片描述：正方形被平均分成4份，其中1份涂色，表示 $\frac{1}{4}=0.25$]
![图片](images/rId42.jpeg)
```

- `decorative` 分类：整个图片块（占位符行 + 图片行）删除
- `unreadable` 图片：描述改为"图片无法辨认，请参看原图"
- `low_res` 图片：描述行写入，图片行下方加 `<!-- 低分辨率，建议人工核查 -->`

---

*操作手册 v9 — 2026-03-19*
