# -*- coding: utf-8 -*-
"""rag_postprocess 模块单元测试"""
import sys
from pathlib import Path

# 将父目录加入路径以便导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "claude终端代码"))

from rag_postprocess import int_to_cn, den_to_cn, frac_to_semantic


def test_int_to_cn():
    """测试数字转中文"""
    assert int_to_cn(0) == "零"
    assert int_to_cn(1) == "一"
    assert int_to_cn(10) == "十"
    assert int_to_cn(15) == "十五"
    assert int_to_cn(99) == "九十九"
    assert int_to_cn(100) == "一百"
    assert int_to_cn(123) == "一百二十三"


def test_den_to_cn():
    """测试分母转中文"""
    assert den_to_cn(10) == "十分之"
    assert den_to_cn(100) == "百分之"
    assert den_to_cn(1000) == "千分之"


def test_frac_to_semantic():
    """测试分数转语义"""
    assert "十分之一" in frac_to_semantic("1", "10")
    assert "1/10" in frac_to_semantic("1", "10")
