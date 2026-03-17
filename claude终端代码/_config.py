# -*- coding: utf-8 -*-
"""
跨平台路径配置
- 通过环境变量 MATH_TOOLKIT_BASE 指定工作目录（默认当前目录）
- 在 Linux/Windows 上均可运行
"""
import os
from pathlib import Path

# 脚本所在目录
SCRIPT_DIR = Path(__file__).resolve().parent

# 工作目录：环境变量 > 当前目录
BASE_DIR = Path(os.environ.get("MATH_TOOLKIT_BASE", str(Path.cwd())))

# 输出目录
OUTPUT_DIR = BASE_DIR / "output"

# B站 SESSDATA 缓存文件（放在脚本目录）
SESSDATA_FILE = SCRIPT_DIR / ".bili_sessdata"
