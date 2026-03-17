# 跨平台配置说明

本仓库已适配 **Linux** 与 **Windows**，所有脚本可在两种系统上运行。

## 环境变量

| 变量名 | 说明 | 默认值 |
|-------|------|--------|
| `MATH_TOOLKIT_BASE` | 工作目录（输入/输出文件根路径） | 当前工作目录 `Path.cwd()` |
| `BILI_OUTPUT` | B站字幕单集下载输出路径 | `{cwd}/output/xxx.md` |
| `TESSERACT_CMD` | Tesseract 可执行文件路径（Windows） | `C:\Program Files\Tesseract-OCR\tesseract.exe` |
| `TESSDATA_PREFIX` | Tesseract 数据目录 | Windows 默认路径 |
| `MATH_PDF_PATH` | PDF 文件路径（export_lowres_for_review） | `{cwd}/input/四年级+整合与拓展(OCR).pdf` |

## 目录结构建议

在 `MATH_TOOLKIT_BASE` 下建议：

```
.
├── input/          # 输入文件（docx、md 等）
├── output/         # 输出文件
└── images/         # 图片资源（部分脚本使用）
```

## 运行示例

```bash
# 设置工作目录（可选）
export MATH_TOOLKIT_BASE=/path/to/your/data

# 运行 fix_md_headings
cd /workspace
python3 claude终端代码/fix_md_headings.py

# 运行 bilibili_subtitle（需先配置 SESSDATA）
python3 claude终端代码/bilibili_subtitle.py
```

## 依赖安装

```bash
pip install -r requirements.txt
```

## 开发工具

- **Linter**: `ruff check claude终端代码/`
- **测试**: `pytest tests/ -v`
