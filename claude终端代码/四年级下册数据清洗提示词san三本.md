# 四年级下册 Word → Markdown 数据清洗提示词

## 任务概述

将以下三个 Word 文档转换为供 AI 分析的高质量 Markdown 文件，分两个阶段处理：
**第一阶段：docx → MD**，**第二阶段：图片 → 文字描述**。

---

## 待处理文件

| 文件 | 类型 | 输出目录 |
|---|---|---|
| `四年级+整合与拓展.docx` | 教研论文集（排版文档） | `Desktop\Claude结果\四年级+整合与拓展\` |
| `王永春《小学数学教材一本通》.docx` | OCR 扫描版书籍 | `Desktop\Claude结果\王永春小学数学教材一本通\` |
| `俞正强：低头找幸福.docx` | OCR 扫描版书籍 | `Desktop\Claude结果\俞正强低头找幸福\` |

---

## 第一阶段：docx → Markdown

### 使用工具

- **脚本基础**：参考 `Desktop\claude终端代码\docx_to_md.py` 的结构（图片提取逻辑）
- **技能规范**：严格遵循 `docx-to-markdown` SKILL.md v1.1.0 的 `get_para_image_names()` 写法
- **禁止**：使用任何占位符（`[IMAGE]`、`rId18` 等），必须通过关系表获取真实文件名

### 核心实现规范

#### 1. 文档遍历顺序（必须保持段落与表格的原始顺序）

```python
for child in doc.element.body:
    tag = child.tag.split('}')[-1]
    if tag == 'p':
        handle_paragraph(Paragraph(child, doc))
    elif tag == 'tbl':
        handle_table(Table(child, doc))
```

#### 2. 图片提取（用 zipfile 直接解压，不依赖 python-docx 图片 API）

```python
import zipfile
with zipfile.ZipFile(docx_path) as z:
    for name in z.namelist():
        if name.startswith('word/media/'):
            fname = os.path.basename(name)
            dest = os.path.join(images_dir, fname)
            with z.open(name) as src, open(dest, 'wb') as dst:
                dst.write(src.read())
```

#### 3. 段落图片引用获取（v1.1.0 正确写法，禁止改用其他方式）

```python
VML_NS  = 'urn:schemas-microsoft-com:vml'
RELS_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

def get_para_image_names(para):
    names = []
    rels = para.part.rels
    R_EMBED = f'{{{RELS_NS}}}embed'
    # 方式1: w:drawing → a:blip（现代图片）
    for blip in para._element.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}blip'):
        rel_id = blip.get(R_EMBED)
        if rel_id and rel_id in rels:
            names.append(os.path.basename(rels[rel_id].target_ref))
    # 方式2: VML v:imagedata（旧版 Word 图片）
    for imgdata in para._element.iter(f'{{{VML_NS}}}imagedata'):
        rel_id = imgdata.get(f'{{{RELS_NS}}}id')
        if rel_id and rel_id in rels:
            names.append(os.path.basename(rels[rel_id].target_ref))
    return names
```

#### 4. handle_paragraph 写法（文字与图片独立处理，互不干扰）

```python
img_counter = [0]  # 用列表实现闭包计数

def handle_paragraph(para):
    img_names = get_para_image_names(para)
    txt = ''.join(run.text for run in para.runs if run.text).strip()

    if not txt and not img_names:
        return  # 空段落跳过

    if txt:
        size = get_para_font_size(para)
        level = SIZE_TO_HEADING.get(size)
        if level:
            lines.append(f'\n{"#" * level} {txt}\n')
        else:
            lines.append(txt)

    # 图片引用（无论有无文字都输出，第二阶段 Vision 处理）
    for name in img_names:
        img_counter[0] += 1
        lines.append(f'\n![图{img_counter[0]}](images/{name})\n')
```

### 各文件字号→标题层级映射

根据字号分析结果，各文件的 `SIZE_TO_HEADING` 配置如下：

#### 文件1：四年级+整合与拓展.docx
```python
SIZE_TO_HEADING = {
    20: 2,   # 整合与拓展课例精选（21次）
    12: 3,   # 一、教学目标定位（64次）
    11: 4,   # 一、主题内容说明（59次）
}
# 正文主体：10.5pt（2012次）、10.0pt（733次）
```

#### 文件2：王永春《小学数学教材一本通》.docx
```python
SIZE_TO_HEADING = {
    16:   2,   # 第一节 小学数学是什么（22次）
    15.5: 2,   # 第一节 自然数和整数（28次）
    15:   3,   # 小学数学历史简介（109次）
    14.5: 3,   # 小学数学的本质（73次）
    14:   4,   # 如何跳出教材看数学（77次）
}
# 正文主体：12.0pt（3631次）
```

#### 文件3：俞正强：低头找幸福.docx
```python
SIZE_TO_HEADING = {
    23.5: 2,   # 教育是一门艺术（4次）
    23:   2,   # 我看名师成长（13次）
    22:   2,   # 第八章（2次）
    16:   3,   # 1998—2002 忽如一夜春风来（2次）
    15.5: 3,   # 1986—1998 平平淡淡才是真（1次）
    14.5: 4,   # 分数准备课教学设计 / ◎ 学生对我影响很大（27次）
}
# 正文主体：10.5pt（1057次）、10.0pt（254次）
```

### OCR 文本清洗（文件2、文件3 专项）

文件2（王永春）和文件3（俞正强低头）为 OCR 扫描版，需在输出前对段落文本应用以下清洗规则，参考 `Desktop\clean_docx.py` 的实现：

**噪声过滤（以下段落直接丢弃）：**
- 水印行：含「仅供个人科研教学使用」变体
- 纯页码行：`^\d{1,4}$`
- 全大写拼音行：`^[A-Z\s]{10,}$`
- 出版信息行：含「责任编辑/ISBN/CIP/出版发行/定价/印刷/经销」
- OCR 孤立人名行：`^[\u4e00-\u9fff]{1,5}(\s+[\u4e00-\u9fff]{1,5}){1,5}\s*$`
- 书名页眉/页脚：含「俞正强：低头找」重复短行（9.5pt 以下的书名行）

**文本修复：**
- 去尾部页码：`re.sub(r'\s*[\|｜]\s*\d{1,4}\s*$', '', t)`
- OCR 汉字间多余空格：若中文字符占比 >60% 且有单字间隔模式，压缩为无空格
- 多余连续空格 → 单个空格

**结构识别：**
- `一、二、三...` 开头的短行（≤30字）→ `##`（优先于字号判断）
- `（一）（二）` 括号序号行 → `####`
- `——` 开头行 → `> 引用块`

---

## 第二阶段：图片 → 文字描述

### 使用工具

- **模型**：`claude-haiku-4-5-20251001`（省钱，速度快）
- **API Key**：从调用方环境变量 `ANTHROPIC_API_KEY` 读取
- **处理范围**：MD 文件中所有 `![图N](images/xxx)` 引用，**一张都不跳过**

### Vision API 调用规范

```python
import anthropic, base64
from pathlib import Path

client = anthropic.Anthropic()

MEDIA_TYPES = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp',
}

def describe_image(img_path: str) -> dict:
    """
    返回 {'type': 'math'|'diagram'|'decorative', 'content': str}
    """
    ext = Path(img_path).suffix.lower()
    media_type = MEDIA_TYPES.get(ext)
    if not media_type:
        # WMF/EMF 等格式无法发给 Vision API，保留原引用
        return {'type': 'unsupported', 'content': ''}

    with open(img_path, 'rb') as f:
        data = base64.standard_b64encode(f.read()).decode('utf-8')

    prompt = """请分析这张图片，按以下规则回复：

1. 如果是【装饰图】（纯边框、背景色块、空白、无实际内容）：
   只回复：DECORATIVE

2. 如果是【数学公式或数学图形】（含数字、运算符、几何图形、坐标轴、表达式）：
   回复格式：MATH\n然后用 LaTeX 表示公式内容，行内公式用 $...$，块级公式用 $$...$$
   如果公式无法用 LaTeX 表达，用中文描述数学含义。

3. 如果是【教学插图、图表、照片、示意图】：
   回复格式：DIAGRAM\n用一句中文描述图片内容，以"这是"开头，不超过80字。"""

    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=300,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'base64', 'media_type': media_type, 'data': data}},
                {'type': 'text', 'text': prompt}
            ]
        }]
    )
    return parse_vision_response(msg.content[0].text.strip())


def parse_vision_response(text: str) -> dict:
    if text.startswith('DECORATIVE'):
        return {'type': 'decorative', 'content': ''}
    if text.startswith('MATH\n'):
        return {'type': 'math', 'content': text[5:].strip()}
    if text.startswith('DIAGRAM\n'):
        return {'type': 'diagram', 'content': text[8:].strip()}
    # 兜底：当作普通描述
    return {'type': 'diagram', 'content': text}
```

### 图片替换规则

| Vision 判断 | 替换内容 |
|---|---|
| `decorative`（装饰图） | **删除**该行，不留任何引用 |
| `math`（数学公式） | 替换为 LaTeX：`$公式$` 或 `$$公式$$` |
| `diagram`（教学插图） | 替换为 `> [图片内容] 这是...` |
| `unsupported`（WMF/EMF） | 保留原 `![图N](...)` 引用不动 |

### MD 文件后处理

- 替换完成后，清理因删除装饰图产生的多余空行（连续空行压缩为最多1行）
- 验证：统计替换前后 `![` 数量，确认每张图都被处理

---

## 运行方式

```bash
# 设置 API Key
export ANTHROPIC_API_KEY=你的key

# 运行主脚本（待编写，保存到 Desktop\claude终端代码\四年级下册批量转换.py）
python Desktop/claude终端代码/四年级下册批量转换.py
```

## 输出验证清单

- [ ] 三个 MD 文件无乱码
- [ ] 标题层级结构正确（`##`、`###`、`####`）
- [ ] `![图N](...)` 引用全部被替换（无残留）
- [ ] 数学公式以 LaTeX 格式呈现
- [ ] 装饰图已删除，无空白图片引用
- [ ] OCR 噪声行（水印/页码/出版信息）已清除（文件2、3）
- [ ] images 目录图片数量与 docx 内嵌图片数量一致
