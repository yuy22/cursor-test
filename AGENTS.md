# AGENTS.md

## Cursor Cloud specific instructions

### 项目概述

这是一个纯 Python CLI 工具集（小学数学教学辅助工具集），没有 Web 服务、数据库或 Docker 容器。所有脚本都是一次性命令行工具，位于 `claude终端代码/` 目录下。

### 开发命令

- **Lint**: `ruff check claude终端代码/`
- **测试**: `pytest tests/ -v`
- **运行脚本**: `python3 claude终端代码/<script_name>.py`

详见 `README_配置说明.md` 了解环境变量和目录结构。

### 注意事项

- `ruff` 和 `pytest` 安装在 `~/.local/bin`，已添加到 PATH（通过 `~/.bashrc`）。如果命令找不到，运行 `export PATH="$HOME/.local/bin:$PATH"`。
- Tesseract OCR（含中文简体语言包 `chi_sim`）已作为系统依赖安装，`docx_to_md.py` 需要它。
- 部分脚本依赖外部 API（Bilibili API、Claude Vision 代理），需要网络访问和对应凭据才能运行。这些脚本在没有凭据时会报错，不影响其他脚本的使用。
- ruff lint 存在一些预先存在的 E701 警告（多条语句写在同一行），这是仓库原有代码风格，不是环境问题。
