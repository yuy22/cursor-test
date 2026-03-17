"""
RAG 后处理：将 _v3.md 优化为 RAG 检索友好格式

两个核心变换：
1. LaTeX 分数 $\frac{num}{den}$ → 中文语义（num/den）
2. 图片描述引用块 > **[图N]** ... → 拍平为普通段落

输入:  北师大版4年级数学下册教师用书_v3.md
输出:  北师大版4年级数学下册教师用书_rag.md
"""
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# ── 路径（跨平台）────────────────────────────────────────────────────
_base = Path(os.environ.get("MATH_TOOLKIT_BASE", str(Path.cwd())))
SRC = _base / "input" / "北师大版4年级数学下册教师用书_v3.md"
if not SRC.exists():
    SRC = _base / "北师大版4年级数学下册教师用书_v3.md"
DEST = _base / "output" / "北师大版4年级数学下册教师用书_rag.md"
if not DEST.parent.exists():
    DEST.parent.mkdir(parents=True, exist_ok=True)

# ── 中文数字转换 ─────────────────────────────────────────────────
_DIGITS = '零一二三四五六七八九'

def int_to_cn(n: int) -> str:
    """正整数 → 中文，支持 1-9999"""
    if n == 0:
        return '零'
    if n < 10:
        return _DIGITS[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        prefix = '' if tens == 1 else _DIGITS[tens]
        suffix = _DIGITS[ones] if ones else ''
        return prefix + '十' + suffix
    if n < 1000:
        h, rest = divmod(n, 100)
        s = _DIGITS[h] + '百'
        if rest == 0:
            return s
        return s + ('零' if rest < 10 else '') + int_to_cn(rest)
    if n < 10000:
        k, rest = divmod(n, 1000)
        s = _DIGITS[k] + '千'
        if rest == 0:
            return s
        return s + ('零' if rest < 100 else '') + int_to_cn(rest)
    return str(n)


# ── 专门针对分母的中文表达 ────────────────────────────────────────
_DEN_MAP = {10: '十', 100: '百', 1000: '千', 10000: '万'}

def den_to_cn(d: int) -> str:
    return _DEN_MAP.get(d, int_to_cn(d)) + '分之'


# ── 分数 → 中文语义 ──────────────────────────────────────────────
def frac_to_semantic(num_str: str, den_str: str) -> str:
    """
    \frac{1}{10} → 十分之一（1/10）
    \frac{59}{1000} → 千分之五十九（59/1000）
    非整数分子/分母 → 原始 num/den
    """
    try:
        n, d = int(num_str), int(den_str)
        return f'{den_to_cn(d)}{int_to_cn(n)}（{n}/{d}）'
    except ValueError:
        return f'{num_str}/{den_str}'


# ── LaTeX 处理 ───────────────────────────────────────────────────

# 单个分数（单 $ 或双 $$）
_FRAC1_RE = re.compile(r'\$\$\\frac\{([^}]+)\}\{([^}]+)\}\$\$')   # $$\frac{a}{b}$$
_FRAC2_RE = re.compile(r'\$\\frac\{([^}]+)\}\{([^}]+)\}\$')        # $\frac{a}{b}$

# 块级 LaTeX $$...$$ （含内容，非空）
_BLOCK_RE  = re.compile(r'\$\$([^\n$]+)\$\$')

# 行内 LaTeX $...$ （不含 $）
_INLINE_RE = re.compile(r'\$([^\n$]+)\$')

# 清理 LaTeX 命令：\text{内容} → 内容，其余 \cmd → 删除
_TEXT_RE = re.compile(r'\\text\{([^}]*)\}')
_CMD_RE  = re.compile(r'\\[a-zA-Z]+')
# 裸 \frac{a}{b}（内部使用，内容已去掉外层美元符）
_FRAC_RAW_RE = re.compile(r'\\frac\{([^}]+)\}\{([^}]+)\}')


def clean_latex_text(s: str) -> str:
    """把 LaTeX 命令转为可读文本（输入已去掉外层美元符）"""
    # 先展开常见符号
    s = s.replace(r'\times', '×').replace(r'\cdots', '...')
    # \text{内容} → 内容
    s = _TEXT_RE.sub(r'\1', s)
    # 裸 \frac{a}{b} → 中文语义
    s = _FRAC_RAW_RE.sub(lambda m: frac_to_semantic(m.group(1), m.group(2)), s)
    # 剩余 \cmd 删除（花括号保留内容）
    s = _CMD_RE.sub('', s)
    # 清理多余的花括号
    s = re.sub(r'[{}]', '', s)
    return s.strip()


def process_latex(line: str) -> str:
    stripped = line.rstrip()

    # 空的块级定界符 $$ 独立成行 → 删除整行
    if stripped == '$$':
        return ''

    # 先处理分数（两种定界符）
    line = _FRAC1_RE.sub(lambda m: frac_to_semantic(m.group(1), m.group(2)), line)
    line = _FRAC2_RE.sub(lambda m: frac_to_semantic(m.group(1), m.group(2)), line)

    # $$...$$ 块级：清理剩余 LaTeX，剥去外层 $$
    line = _BLOCK_RE.sub(lambda m: clean_latex_text(m.group(1)), line)

    # $...$ 行内：剥去美元符，清理内部 LaTeX
    line = _INLINE_RE.sub(lambda m: clean_latex_text(m.group(1)), line)

    return line


# ── 残留图片引用清理 ─────────────────────────────────────────────
_IMG_RE = re.compile(r'!\[图(\d+)\]\(images/[^)]+\)')


def strip_img_refs(line: str) -> str:
    """把 API 失败保留的图片引用转为文字占位，去掉 markdown 图片语法"""
    return _IMG_RE.sub(r'[图\1（图片）]', line)


# ── 引用块拍平 ───────────────────────────────────────────────────
def flatten_blockquotes(lines: list[str]) -> list[str]:
    """
    > content  →  content
    >          →  （空行）
    """
    result = []
    for line in lines:
        if line.startswith('> '):
            result.append(line[2:])
        elif line.rstrip() == '>':
            result.append('\n')
        else:
            result.append(line)
    return result


# ── 主流程 ───────────────────────────────────────────────────────
def main():
    with open(SRC, encoding='utf-8') as f:
        lines = f.readlines()

    before_latex  = sum(1 for l in lines if '$' in l)
    before_blocks = sum(1 for l in lines if l.startswith('>'))

    lines = [process_latex(l) for l in lines]
    lines = [strip_img_refs(l) for l in lines]
    lines = flatten_blockquotes(lines)

    after_latex  = sum(1 for l in lines if '$' in l)
    after_blocks = sum(1 for l in lines if l.startswith('>'))

    with open(DEST, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f'LaTeX 行:  {before_latex} → {after_latex}（剩余含美元符）')
    print(f'引用块行:  {before_blocks} → {after_blocks}')
    print(f'输出: {DEST}')


if __name__ == '__main__':
    main()
