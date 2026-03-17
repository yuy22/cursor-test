# AGENTS.md

## 项目概述

本仓库是一个小学数学教学辅助工具集，包含：
- **B站字幕下载器**（`claude终端代码/bilibili_subtitle.py` 等）：下载B站教学视频的AI字幕并转为Markdown
- **RAG知识库构建工具**（`claude终端代码/docx_to_md.py`、`fix_md_headings.py`、`process_images.py` 等）：将教师用书Word文档转为结构化Markdown，优化RAG检索
- **AI教学助手提示词**（`math-teaching-assistant.mdc`、`要求.md`）：Cursor规则文件，不是可运行的代码

所有Python脚本位于 `claude终端代码/` 目录，均为独立CLI脚本，无Web服务、无数据库、无长驻进程。

## Cursor Cloud specific instructions

### 开发环境

- Python 3.12+，依赖通过 pip 安装：`requests`、`python-docx`、`Pillow`、`pytesseract`、`lxml`、`PyMuPDF`
- 无 `requirements.txt` 或 `pyproject.toml`，依赖从脚本 import 推断
- 无 lint/test/build 配置，无自动化测试框架

### 重要注意事项

- **所有脚本包含硬编码的Windows路径**（如 `C:\Users\b886855456ly\...`），在Linux环境下 `main()` 入口无法直接运行，但内部函数可正常导入和调用
- `bilibili_subtitle.py` 和 `bilibili_batch.py` 需要B站 `SESSDATA` cookie 才能访问API
- `docx_to_md.py` 依赖 Tesseract OCR 二进制文件（`pytesseract`），Linux下需 `apt install tesseract-ocr`
- `process_images.py` 使用外部 Vision API（API Key 硬编码在脚本中）和HTTP代理

### 验证脚本可用性

可通过导入并调用内部函数来验证环境，例如：
```bash
python3 -c "
import sys; sys.path.insert(0, 'claude终端代码')
from fix_md_headings import fix_book2, stat_headings
from bilibili_subtitle import add_punctuation
print('Imports OK')
"
```
